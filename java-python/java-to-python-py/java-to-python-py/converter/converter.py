from __future__ import annotations

import json
import ast
import time
import collections
from collections import defaultdict
from typing import List, Dict, Any

from converter.basic_structure import ProjectConverter, FileConverter, PackageConverter, ImportConverter
from converter.classes import TopClassConverter
from converter.fields import FieldConverter
from converter.methods import MethodConverter
from converter.exprs import ExprConverter
from converter.control import ControlConverter
from converter.literals import LiteralConverter
from converter.postprocess import model_patch_code

# 为了 IDE 友好（即使未直接使用也无害）
from converter.util import children, get_attr, short_base_type
from converter.exprs import _extract_call_args, _parse_lambda, _rewrite_common_expr

ACTIONABLE_TYPES = {
    "ClassOrInterfaceDeclaration", "EnumDeclaration", "RecordDeclaration", "AnnotationDeclaration",
    "Class", "Interface",
    "Field", "FieldDeclaration", "Variable", "VariableDeclarator",
    "Method", "MethodDeclaration", "Function", "Constructor", "ConstructorDeclaration",
    "IfStmt","IfStatement","ForStmt","ForStatement","ForEachStmt","ForeachStmt","EnhancedFor",
    "WhileStmt","WhileStatement","DoStmt","DoWhileStatement","DoStatement",
    "TryStmt","TryStatement","SwitchStmt","SwitchStatement","SwitchExpr",
    "ReturnStmt","BreakStmt","ContinueStmt","ThrowStmt","ExpressionStmt","BlockStmt","CatchClause",
    "PackageDeclaration","ImportDeclaration","Package","Import",
}

COMMENT_ONLY_OK = {
    "PackageDeclaration", "ImportDeclaration", "Package", "Import",
}

class Converter:
    """主分发 + 统计 + 符号表 + 语法可运行性检查"""

    def __init__(self, ast):
        self.ast = ast
        self.project_conv = ProjectConverter(self)
        self.file_conv = FileConverter(self)
        self.pkg_conv = PackageConverter()
        self.imp_conv = ImportConverter()
        self.top_cls_conv = TopClassConverter(self)
        self.field_conv = FieldConverter(self)
        self.method_conv = MethodConverter(self)
        self.expr_conv = ExprConverter(self)
        self.ctrl_conv = ControlConverter(self)
        self.lit_conv = LiteralConverter()
        self.symtab = {}  # 变量/字段 -> Java 短类型
        self.field_names = set()  # 仅记录类字段名，用于 self. 注入（兼容旧逻辑）
        self.field_info = {}  # 字段名 -> 可见性等元数据
        self.param_alias = {}  # 参数重命名映射（关键字规避）
        self.required_imports = set()
        self.pq_keys = {}
        self.scope_stack = []
        self.class_stack = []
        self.nested_class_stack = []
        self.doc_comment_suppression = 0
        self.stats = {
            "actionable": 0,
            "converted_ok": 0,
            "converted_trivial": 0,
            "fallback_lines": 0,
            "unhandled_by_type": defaultdict(int),
            "unmapped_methods": defaultdict(int),
        }
        self.handlers = self._build_dispatch()
        self.ast_type_counts = collections.Counter()

        self.timing = {
            "elapsed_ms": 0.0,
            "lines": 0,
        }

    def push_scope(self, names=None):
        scope = set(names or [])
        self.scope_stack.append(scope)
        return scope

    def pop_scope(self):
        if self.scope_stack:
            self.scope_stack.pop()

    def add_local(self, name: str):
        if self.scope_stack and name:
            self.scope_stack[-1].add(name)

    def is_local(self, name: str) -> bool:
        if not name:
            return False
        return any(name in scope for scope in reversed(self.scope_stack))

    def is_field_ref(self, name: str) -> bool:
        if not name:
            return False
        return name in getattr(self, "field_names", set()) and not self.is_local(name)

    # ---------------- Dispatch helpers ----------------

    def _build_dispatch(self):
        handlers = {}

        def bind(types, fn):
            for tp in types:
                handlers[tp] = fn

        bind(("Project", "CompilationUnit"), self.project_conv.convert)
        bind(("File",), self.file_conv.convert)
        bind(("Package", "PackageDeclaration"), self._convert_package)
        bind(("Import", "ImportDeclaration"), self._convert_import)
        bind(("Javadoc", "LineComment", "BlockComment", "OrphanComment"), self._convert_comment)
        bind(("ClassOrInterfaceDeclaration", "EnumDeclaration", "RecordDeclaration", "AnnotationDeclaration",
              "Class", "Interface"), self.top_cls_conv.convert)
        bind(("Field", "FieldDeclaration"), self.field_conv.convert)
        bind(("Variable", "VariableDeclarator"), self._convert_variable)
        bind(("Method", "MethodDeclaration", "Function", "Constructor", "ConstructorDeclaration"), self.method_conv.convert)
        bind(("IfStmt", "IfStatement", "ForStmt", "ForStatement", "ForEachStmt", "ForeachStmt", "EnhancedFor",
              "WhileStmt", "WhileStatement", "DoStmt", "DoWhileStatement", "DoStatement",
              "TryStmt", "TryStatement", "SwitchStmt", "SwitchStatement", "SwitchExpr", "ReturnStmt",
              "BreakStmt", "ContinueStmt", "ThrowStmt", "ExpressionStmt", "BlockStmt", "CatchClause"),
             self.ctrl_conv.convert)
        bind(("Block",), self._convert_block)
        bind(("StringLiteralExpr", "IntegerLiteralExpr", "BooleanLiteralExpr", "Constant"), self.lit_conv.convert)
        return handlers

    def _convert_comment(self, node):
        if node.get("type") == "Javadoc":
            return []
        content = node.get("value") or node.get("name") or ""
        if not content:
            return []
        if getattr(self, "doc_comment_suppression", 0):
            stripped = content.strip()
            if stripped.startswith("*") or stripped.startswith("@") or "@param" in stripped or "@return" in stripped:
                return []
        lines = content.splitlines() or [content]
        return [f"# {ln}" if ln.strip() else "#" for ln in lines]

    def push_scope(self, names=None):
        scope = set()
        if names:
            scope.update(names)
        self.scope_stack.append(scope)

    def pop_scope(self):
        if self.scope_stack:
            self.scope_stack.pop()

    def add_local(self, name: str):
        if not name:
            return
        if not self.scope_stack:
            self.scope_stack.append(set())
        self.scope_stack[-1].add(name)

    def is_local(self, name: str) -> bool:
        if not name:
            return False
        return any(name in scope for scope in reversed(self.scope_stack))

    def push_class(self, name: str, nested_names=None):
        self.class_stack.append(name)
        self.nested_class_stack.append(set(nested_names or []))

    def pop_class(self):
        if self.class_stack:
            self.class_stack.pop()
        if self.nested_class_stack:
            self.nested_class_stack.pop()

    def _convert_package(self, node):
        node2 = {"type": "Package", "name": node.get("name", "")}
        return self.pkg_conv.convert(node2)

    def _convert_import(self, node):
        node2 = {"type": "Import", "name": node.get("name", "")}
        return self.imp_conv.convert(node2)

    def _convert_variable(self, node):
        name = node.get("name")
        vtype = node.get("value")
        init = get_attr(node, "initializer")
        if name:
            try:
                self.add_local(name)
            except Exception:
                pass
        if name:
            base = short_base_type(vtype) if vtype else None
            if base:
                self.symtab[name] = base
            self.add_local(name)
        if name and init is not None:
            init_str = str(init).strip()
            if vtype and "PriorityQueue" in str(vtype) and "Comparator.comparingInt" in init_str:
                extracted = _extract_call_args(init_str, "Comparator.comparingInt(")
                if extracted:
                    args, _, _ = extracted
                    lvar, body = _parse_lambda(args.strip())
                    if lvar and body:
                        key_name = f"{name}_key"
                        self.pq_keys[name] = key_name
                        self.required_imports.add("import heapq")
                        body = _rewrite_common_expr(body)
                        return [f"{key_name} = lambda {lvar}: {body}", f"{name} = []"]
            init_expr = self.expr_conv.convert({"type": "Inline", "name": init_str})
            init_val = init_expr[0] if init_expr else init_str
            return [f"{name} = {init_val}"]
        return []

    def _convert_block(self, node):
        out = []
        for ch in children(node):
            out.extend(self.convert_node(ch))
        return out

    # ---------------- Conversion (existing) ----------------

    def _is_actionable_type(self, t: str) -> bool:
        return t in ACTIONABLE_TYPES

    def _record_stats(self, t: str, lines: List[str]):
        if not self._is_actionable_type(t):
            return
        self.stats["actionable"] += 1
        code_lines = [ln for ln in lines if ln.strip() and not ln.lstrip().startswith("#")]
        if code_lines:
            if all(ln.strip() in ("pass", "raise NotImplementedError") for ln in code_lines):
                self.stats["converted_trivial"] += 1
            else:
                self.stats["converted_ok"] += 1
        else:
            if t in COMMENT_ONLY_OK and lines:
                self.stats["converted_trivial"] += 1
                return
            for ln in lines:
                s = ln.strip()
                if s.startswith("# Unhandled node type:") or s.startswith("# expr:") or s.startswith("# control:"):
                    self.stats["fallback_lines"] += 1
                self.stats["unhandled_by_type"][t] += 1

    def _snapshot_stats(self) -> Dict[str, Any]:
        return {
            "actionable": self.stats["actionable"],
            "converted_ok": self.stats["converted_ok"],
            "converted_trivial": self.stats["converted_trivial"],
            "fallback_lines": self.stats["fallback_lines"],
            "unhandled_by_type": dict(self.stats["unhandled_by_type"]),
            "unmapped_methods": dict(self.stats["unmapped_methods"]),
        }

    def _apply_handler(self, t: str, handler, node: dict) -> List[str]:
        lines = handler(node)
        self._record_stats(t, lines)
        return lines

    def convert_node(self, node) -> List[str]:
        if not node or not isinstance(node, dict):
            return []
        t = node.get("type", "")

        handler = self.handlers.get(t)
        if handler:
            return self._apply_handler(t, handler, node)

        if t.endswith("Expression") or t.endswith("Expr") or t == "Expression":
            return self._apply_handler(t, self.expr_conv.convert, node)

        lines = [f"# Unhandled node type: {t}"]
        self._record_stats(t, lines)
        return lines

    def _report(self):
        act = max(1, self.stats["actionable"])
        score = (self.stats["converted_ok"] + 0.25 * self.stats["converted_trivial"]) / act
        print("------ 转换报告 ------")
        print(f"可处理节点数:            {self.stats['actionable']}")
        print(f"有效转换:                {self.stats['converted_ok']}")
        print(f"空洞/占位转换:           {self.stats['converted_trivial']}")
        print(f"回退注释行数:            {self.stats['fallback_lines']}")
        print(f"转换效率(目标≥0.8):      {score:.3f}")
        if self.stats["unhandled_by_type"]:
            top = sorted(self.stats["unhandled_by_type"].items(), key=lambda x: -x[1])[:8]
            print("未处理节点类型(Top):")
            for k, v in top:
                print(f"  {k}: {v}")
            print("未处理节点类型(全量):")
            for k, v in sorted(self.stats["unhandled_by_type"].items(), key=lambda x: (-x[1], x[0])):
                print(f"  {k}: {v}")
        if self.stats["unmapped_methods"]:
            topm = sorted(self.stats["unmapped_methods"].items(), key=lambda x: -x[1])[:8]
            print("未映射方法(Top):")
            for k, v in topm:
                print(f"  {k}: {v}")
        print("-------------------------------")
        return score

    def _collect_ast_type_counts(self, node):
        counts = collections.Counter()

        def walk(n):
            if isinstance(n, dict):
                t = n.get("type")
                if t:
                    counts[t] += 1
                for v in n.values():
                    walk(v)
            elif isinstance(n, list):
                for item in n:
                    walk(item)

        walk(node)
        return counts

    def _handler_name_for_type(self, t: str) -> str:
        handler = self.handlers.get(t)
        if handler:
            return getattr(handler, "__qualname__", getattr(handler, "__name__", str(handler)))
        if t.endswith("Expression") or t.endswith("Expr") or t == "Expression":
            return "ExprConverter.convert"
        return "UNHANDLED"

    def _report_ast_type_coverage(self):
        if not self.ast_type_counts:
            return
        print("------ AST 节点覆盖率 ------")
        print("说明: UNHANDLED 表示未绑定处理器或未进入表达式兜底规则。")
        for t, count in sorted(self.ast_type_counts.items(), key=lambda x: (-x[1], x[0])):
            handler = self._handler_name_for_type(t)
            print(f"{t}: {count} -> {handler}")
        print("-------------------------------")

    # ---------------- Syntax check (new) ----------------

    def _extract_top_blocks(self, lines: List[str]):
        """
        把代码按顶层块切分：class、def（含前置装饰器）、main-guard。
        返回 [{name, start_line, code}, ...]
        """
        n = len(lines)
        starts = []
        i = 0
        while i < n:
            line = lines[i]
            stripped = line.lstrip()
            if not stripped or stripped.startswith("#"):
                i += 1
                continue
            # 仅考虑顶层（无缩进）
            if line.startswith("class "):
                name = stripped.split()[1]
                name = name.split("(")[0].split(":")[0]
                starts.append((f"class {name}", i + 1))
            elif line.startswith("@"):
                # 顶层装饰器 + def
                deco_i = i
                j = i
                while j < n and lines[j].startswith("@"):
                    j += 1
                if j < n and lines[j].startswith("def "):
                    defline = lines[j]
                    dname = defline.split("def ", 1)[1].split("(", 1)[0].strip()
                    starts.append((f"def {dname}", deco_i + 1))
                    i = j  # 跳到 def 行，后面会 i+=1
            elif line.startswith("def "):
                dname = line.split("def ", 1)[1].split("(", 1)[0].strip()
                starts.append((f"def {dname}", i + 1))
            elif line.startswith("if __name__") and "__main__" in line:
                starts.append(("main-guard", i + 1))
            i += 1

        blocks = []
        for idx, (name, start) in enumerate(starts):
            end = starts[idx + 1][1] - 1 if idx + 1 < len(starts) else n
            code = "\n".join(lines[start - 1:end])
            blocks.append({"name": name, "start_line": start, "code": code})
        return blocks

    def _syntax_check(self, content: str):
        """
        返回：
          {
            'module_ok': bool,
            'module_error': {msg, lineno, offset, text} | None,
            'blocks': [{name, start_line, ok, error?}, ...],
            'blocks_total': int,
            'blocks_ok': int,
            'rate': float,
          }
        """
        info = {}
        lines = content.splitlines()

        # 1) 模块级
        try:
            ast.parse(content)
            info["module_ok"] = True
            info["module_error"] = None
        except SyntaxError as e:
            info["module_ok"] = False
            info["module_error"] = {
                "msg": e.msg,
                "lineno": e.lineno,
                "offset": e.offset,
                "text": (e.text or "").rstrip("\n") if hasattr(e, "text") else ""
            }

        # 2) 分块
        blocks = self._extract_top_blocks(lines)
        results = []
        ok = 0
        for blk in blocks:
            code = blk["code"]
            try:
                ast.parse(code)
                blk["ok"] = True
                blk["error"] = None
                ok += 1
            except SyntaxError as e:
                glineno = blk["start_line"] + (e.lineno or 1) - 1
                line_text = ""
                if 1 <= glineno <= len(lines):
                    line_text = lines[glineno - 1]
                blk["ok"] = False
                blk["error"] = {
                    "msg": e.msg,
                    "lineno_global": glineno,
                    "lineno_local": e.lineno,
                    "offset": e.offset,
                    "line": (line_text or (e.text or "")).rstrip("\n"),
                }
            results.append(blk)

        info["blocks"] = results
        info["blocks_total"] = len(blocks)
        info["blocks_ok"] = ok
        info["rate"] = (ok / len(blocks)) if blocks else (1.0 if info["module_ok"] else 0.0)
        return info

    def _report_syntax(self, syntax, content: str):
        print("------ 语法检查(ast.parse) ------")
        mod_ok = syntax.get("module_ok", False)
        print(f"模块解析: {'OK' if mod_ok else 'FAIL'}")
        if not mod_ok and syntax.get("module_error"):
            e = syntax["module_error"]
            print(f"  行 {e.get('lineno')}:{e.get('offset')} {e.get('msg')}")
            if e.get("text"):
                print(f"    > {e['text']}")
        total = syntax.get("blocks_total", 0)
        ok = syntax.get("blocks_ok", 0)
        rate = syntax.get("rate", 0.0)
        print(f"块检查: {total}  OK: {ok}  可解析度: {rate:.3f}")
        # 打印部分错误详情
        if total - ok > 0:
            shown = 0
            for blk in syntax.get("blocks", []):
                if blk.get("ok"):
                    continue
                err = blk.get("error") or {}
                gl = err.get("lineno_global")
                msg = err.get("msg")
                line_text = err.get("line", "").rstrip()
                print(f"  - [{blk['name']}] 行 {gl}: {msg}")
                if line_text:
                    print(f"    > {line_text}")
                shown += 1
                if shown >= 5:
                    break
        print("-------------------------------")

    def _format_report_comment(self, score, syntax) -> str:
        lines = []
        lines.append("")
        lines.append("# --- 转换测试报告 ---")
        lines.append(f"# 转换效率: {score:.3f}")
        blocks_total = syntax.get("blocks_total", 0)
        blocks_ok = syntax.get("blocks_ok", 0)
        rate = syntax.get("rate", 0.0)
        lines.append(f"# 可解析度: {rate:.3f} ({blocks_ok}/{blocks_total})")
        if not syntax.get("module_ok", False) and syntax.get("module_error"):
            e = syntax["module_error"]
            lines.append("# 语法问题: 模块无法解析")
            lines.append(f"#  - 行 {e.get('lineno')}:{e.get('offset')} {e.get('msg')}")
            if e.get("text"):
                lines.append(f"#    > {e['text']}")
        for blk in syntax.get("blocks", []):
            if blk.get("ok"):
                continue
            err = blk.get("error") or {}
            gl = err.get("lineno_global")
            msg = err.get("msg")
            line_text = (err.get("line") or "").rstrip()
            lines.append(f"# 语法问题: [{blk.get('name', 'block')}] 行 {gl} {msg}")
            if line_text:
                lines.append(f"#    > {line_text}")
        unhandled = self.stats.get("unhandled_by_type", {})
        if unhandled:
            lines.append("# 未处理节点类型(Top):")
            top = sorted(unhandled.items(), key=lambda x: -x[1])[:8]
            for k, v in top:
                lines.append(f"#  - {k}: {v}")
        unmapped = self.stats.get("unmapped_methods", {})
        if unmapped:
            lines.append("# 未映射方法(Top):")
            topm = sorted(unmapped.items(), key=lambda x: -x[1])[:8]
            for k, v in topm:
                lines.append(f"#  - {k}: {v}")
        lines.append("# --- 报告结束 ---")
        return "\n".join(lines) + "\n"

    # ---------------- Driver ----------------

    def run(self, in_json="ast_Demo.json", out_py="converted.py", postprocess=True):
        start = time.perf_counter()
        data = self.ast if isinstance(self.ast, dict) else json.load(open(in_json, encoding="utf-8"))
        self.ast_type_counts = self._collect_ast_type_counts(data)
        lines = self.convert_node(data)
        content = "\n".join(lines).rstrip() + "\n"
        if self.required_imports:
            imports = "\n".join(sorted(self.required_imports)) + "\n\n"
            content = imports + content
        if postprocess:
            try:
                content = model_patch_code(content)
            except Exception:
                pass
        with open(out_py, "w", encoding="utf-8") as f:
            f.write(content)

        elapsed_ms = (time.perf_counter() - start) * 1000
        self.timing["elapsed_ms"] = elapsed_ms
        self.timing["lines"] = len(lines)
        print("✅ 完成 →", out_py)

        # 原有效率报告
        score = self._report()
        self._report_ast_type_coverage()

        # 新增：语法可运行性报告
        syntax = self._syntax_check(content)
        self._report_syntax(syntax, content)

        quick_rate = syntax.get("rate", 0.0)
        print(
            f"概要 → 效率: {score:.3f} | 可解析度: {quick_rate:.3f} | "
            f"行数: {len(lines)} | 用时: {elapsed_ms:.1f} ms"
        )

        report_comment = self._format_report_comment(score, syntax)
        with open(out_py, "a", encoding="utf-8") as f:
            f.write(report_comment)

        return {
            "content": content,
            "stats": self._snapshot_stats(),
            "syntax": syntax,
            "efficiency": score,
            "timing": dict(self.timing),
        }
