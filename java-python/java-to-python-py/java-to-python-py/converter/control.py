import re
from typing import List
from converter.util import children, get_attr

_EXC_MAP = {
    "IllegalArgumentException": "ValueError",
    "NullPointerException": "TypeError",
    "IOException": "OSError",
    "RuntimeException": "Exception",
}

def _map_exc_name(java_name: str) -> str:
    short = (java_name or "").split(".")[-1]
    return _EXC_MAP.get(short, short or "Exception")

class ControlConverter:
    def __init__(self, root):
        self.root = root

    def _emit_block(self, node) -> List[str]:
        lines: List[str] = []
        for ch in children(node):
            lines.extend(self.root.convert_node(ch))
        return lines

    def _indent(self, lines: List[str], n: int = 1) -> List[str]:
        pad = "    " * n
        return [pad + l if l.strip() else "" for l in lines] or [pad + "pass"]

    def _expr(self, expr: str) -> str:
        if not expr:
            return ""
        try:
            converted = self.root.expr_conv.convert({"type": "Inline", "name": expr})
            return converted[0] if converted else expr
        except Exception:
            return expr

    def convert_if(self, node) -> List[str]:
        cond = self._expr(get_attr(node, "condition") or node.get("name", "True"))
        chs = children(node)
        block_children = [ch for ch in chs if ch.get("type") == "BlockStmt"]
        if block_children:
            then_part = block_children[0]
            else_part = block_children[1] if len(block_children) > 1 else None
        else:
            then_part = chs[1] if len(chs) >= 2 else None
            else_part = chs[2] if len(chs) >= 3 else None
        lines = [f"if {cond}:"] + self._indent(self._emit_block(then_part) if then_part else [])
        if else_part:
            lines.append("else:")
            lines += self._indent(self._emit_block(else_part))
        return lines

    def convert_for(self, node) -> List[str]:
        cmp_s = self._expr((get_attr(node, "compare") or "").strip())
        init_s = (get_attr(node, "init") or "").strip()
        update_s = (get_attr(node, "update") or "").strip()
        if init_s.startswith("[") and init_s.endswith("]"):
            init_s = init_s[1:-1].strip()
        if update_s.startswith("[") and update_s.endswith("]"):
            update_s = update_s[1:-1].strip()
        header = None
        if cmp_s and ("<" in cmp_s or "<=" in cmp_s or ">" in cmp_s or ">=" in cmp_s) and " in " not in cmp_s:
            if "<=" in cmp_s:
                op = "<="
            elif "<" in cmp_s:
                op = "<"
            elif ">=" in cmp_s:
                op = ">="
            else:
                op = ">"
            left, _, right = cmp_s.partition(op)
            var = left.strip()
            limit = right.strip()
            start = "0"
            step = "1"
            m_init = re.search(r"(?:\w+\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)", init_s)
            if m_init:
                var = m_init.group(1).strip()
                start = self._expr(m_init.group(2).strip())
            m_update = re.search(r"([A-Za-z_][A-Za-z0-9_]*)\s*\+\+", update_s)
            if m_update:
                step = "1"
            m_update = re.search(r"([A-Za-z_][A-Za-z0-9_]*)\s*--", update_s)
            if m_update:
                step = "-1"
            m_update = re.search(r"([A-Za-z_][A-Za-z0-9_]*)\s*\+=\s*(.+)", update_s) or re.search(
                r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\1\s*\+\s*(.+)", update_s
            )
            if m_update:
                step = self._expr(m_update.group(2).strip())
            m_update = re.search(r"([A-Za-z_][A-Za-z0-9_]*)\s*-\=\s*(.+)", update_s) or re.search(
                r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\1\s*-\s*(.+)", update_s
            )
            if m_update:
                step = f"-{self._expr(m_update.group(2).strip())}"
            try:
                if limit and hasattr(self.root, "field_info") and limit in getattr(self.root, "field_info", {}) and not self.root.is_local(limit):
                    limit = f"self.{limit}"
            except Exception:
                pass
            if op == "<=" and not step.startswith("-"):
                limit = f"({limit}) + 1"
            if op == ">=" and step.startswith("-"):
                limit = f"({limit}) - 1"
            if var:
                try:
                    self.root.add_local(var)
                except Exception:
                    pass
                range_args = [start, limit] if step == "1" else [start, limit, step]
                if start == "0" and step == "1":
                    range_args = [limit]
                header = f"for {var} in range({', '.join(range_args)}):"
        if not header:
            header = f"# for({get_attr(node,'init')}; {cmp_s}; {get_attr(node,'update')})"
        chs = children(node)
        body_stmt = chs[-1] if chs else None
        body = self._emit_block(body_stmt) if body_stmt else []
        return [header] + self._indent(body)

    def convert_foreach(self, node) -> List[str]:
        var = (get_attr(node, "var") or "").strip()
        iterable = self._expr((get_attr(node, "iterable") or "").strip())
        if var:
            toks = var.replace("(", " ").replace(")", " ").split()
            var = toks[-1] if toks else "item"
        else:
            var = "item"
        try:
            self.root.add_local(var)
        except Exception:
            pass
        header = f"for {var} in {iterable}:" if iterable else f"# foreach {node.get('name','')}"
        try:
            self.root.add_local(var)
        except Exception:
            pass
        chs = children(node)
        body_stmt = chs[-1] if chs else None
        body = self._emit_block(body_stmt) if body_stmt else []
        return [header] + self._indent(body)

    def convert_while(self, node) -> List[str]:
        cond = self._expr(get_attr(node, "condition") or node.get("name", "True"))
        chs = children(node)
        body_stmt = chs[-1] if chs else None
        body = self._emit_block(body_stmt) if body_stmt else []
        return [f"while {cond}:"] + self._indent(body)

    def convert_do(self, node) -> List[str]:
        cond = self._expr(get_attr(node, "condition") or node.get("name", "False"))
        chs = children(node)
        body_stmt = chs[0] if chs else None
        body = self._emit_block(body_stmt) if body_stmt else []
        lines = ["while True:"] + self._indent(body)
        lines.append(f"    if not ({cond}):")
        lines.append("        break")
        return lines

    def _extract_catch_type(self, node) -> str:
        t = get_attr(node, "paramType")
        if t:
            return _map_exc_name(t)
        name = node.get("name") or ""
        m = re.search(r"catch\s*\(\s*([A-Za-z0-9_.]+)", name)
        if m:
            return _map_exc_name(m.group(1))
        return "Exception"

    def convert_try(self, node) -> List[str]:
        chs = children(node)
        try_body = None
        catchers = []
        finally_body = None
        for ch in chs:
            tp = ch.get("type")
            if tp == "CatchClause":
                catchers.append(ch)
            elif tp == "BlockStmt":
                if try_body is None:
                    try_body = ch
                else:
                    finally_body = ch

        lines = ["try:"]
        lines += self._indent(self._emit_block(try_body) if try_body else [])
        for c in catchers:
            ex_type = self._extract_catch_type(c)
            lines.append(f"except {ex_type} as ex:")
            # 只取 catch 的块体，避免 Parameter 被当作注释输出
            block = None
            for cc in children(c):
                if cc.get("type") == "BlockStmt":
                    block = cc
                    break
            lines += self._indent(self._emit_block(block) if block else [])
        if finally_body is not None:
            lines.append("finally:")
            lines += self._indent(self._emit_block(finally_body))
        return lines

    def convert_simple(self, node) -> List[str]:
        t = node.get("type")
        if t == "ReturnStmt":
            expr = self._expr(get_attr(node, "expr") or "")
            return [f"return {expr}".rstrip()]
        if t == "BreakStmt":
            return ["break"]
        if t == "ContinueStmt":
            return ["continue"]
        if t == "ThrowStmt":
            expr = (get_attr(node, "expr") or node.get("name") or "").strip()
            m = re.match(r"^new\s+([A-Za-z0-9_$.<>]+)\s*\((.*)\)\s*$", expr)
            if m:
                exc = _map_exc_name(m.group(1))
                args = m.group(2)
                return [f"raise {exc}({args})"]
            return [f"raise {expr or 'Exception()'}"]
        return [f"# control: {t}"]

    def convert_expr_stmt(self, node) -> List[str]:
        code = get_attr(node, "code") or node.get("name") or node.get("value")
        if isinstance(code, str) and code.strip():
            return self.root.expr_conv.convert({"type": "Inline", "name": code.strip()})
        chs = children(node)
        out: List[str] = []
        for ch in chs:
            out.extend(self.root.convert_node(ch))
        return out or [f"# expr-stmt"]

    def convert(self, node) -> List[str]:
        t = node.get("type", "")
        if t in ("IfStmt", "IfStatement"):
            return self.convert_if(node)
        if t in ("ForStmt", "ForStatement"):
            return self.convert_for(node)
        if t in ("ForEachStmt", "ForeachStmt", "EnhancedFor"):
            return self.convert_foreach(node)
        if t in ("WhileStmt", "WhileStatement"):
            return self.convert_while(node)
        if t in ("DoStmt", "DoWhileStatement", "DoStatement"):
            return self.convert_do(node)
        if t in ("TryStmt", "TryStatement"):
            return self.convert_try(node)
        if t in ("SwitchStmt", "SwitchStatement"):
            return [f"# switch {get_attr(node,'selector') or node.get('name','')}"] + self._indent(self._emit_block(node))
        if t == "SwitchExpr":
            return [f"# switch-expr"] + self._indent(self._emit_block(node))
        if t in ("ReturnStmt", "BreakStmt", "ContinueStmt", "ThrowStmt"):
            return self.convert_simple(node)
        if t == "ExpressionStmt":
            return self.convert_expr_stmt(node)
        if t == "BlockStmt":
            return self._emit_block(node)
        return [f"# control: {t}"]
