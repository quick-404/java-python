import re
from typing import List, Optional, Tuple
from converter.util import get_attr, split_args

def _split_concat(expr: str) -> List[str]:
    parts = []
    cur = []
    in_sq = in_dq = False
    escaped = False
    for ch in expr:
        if ch == "\\" and not escaped:
            escaped = True
            cur.append(ch); continue
        if ch == "'" and not escaped and not in_dq: in_sq = not in_sq
        elif ch == '"' and not escaped and not in_sq: in_dq = not in_dq
        if ch == "+" and not in_sq and not in_dq:
            part = "".join(cur).strip()
            if part: parts.append(part)
            cur = []
        else:
            cur.append(ch)
        escaped = False
    tail = "".join(cur).strip()
    if tail: parts.append(tail)
    return parts

def _is_simple_ident(s: str) -> bool:
    return bool(re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", s))

def _strip_generics(s: str) -> str:
    if "<" not in s:
        return s
    out = []
    depth = 0
    for ch in s:
        if ch == "<":
            depth += 1
            continue
        if ch == ">":
            depth = max(0, depth - 1)
            continue
        if depth == 0:
            out.append(ch)
    return "".join(out)

def _strip_generics_from_types(s: str) -> str:
    if "<" not in s:
        return s
    out = []
    i = 0
    while i < len(s):
        ch = s[i]
        if ch.isalpha() or ch == "_":
            start = i
            i += 1
            while i < len(s) and (s[i].isalnum() or s[i] in "_."):
                i += 1
            if i < len(s) and s[i] == "<":
                ident = s[start:i]
                depth = 0
                while i < len(s):
                    if s[i] == "<":
                        depth += 1
                    elif s[i] == ">":
                        depth = max(0, depth - 1)
                        if depth == 0:
                            i += 1
                            break
                    i += 1
                out.append(ident)
                continue
            out.append(s[start:i])
            continue
        out.append(ch)
        i += 1
    return "".join(out)

def _map_new_full(rhs: str) -> str:
    """把右侧形如 'new X<Y>(args)' 转成 'X(args)'，常见集合转 python 等价。"""
    s = rhs.strip().rstrip(";")
    m = re.match(r"^new\s+([A-Za-z0-9_<>.\[\]]+)\s*\((.*)\)\s*$", s)
    if not m:
        return rhs
    cls = _strip_generics(m.group(1).strip())
    args = (m.group(2) or "").strip()
    if "ArrayList" in cls or cls.endswith("List") or cls.endswith("[]"):
        return f"list({args})" if args else "[]"
    if "ArrayDeque" in cls or cls.endswith("Deque") or "LinkedList" in cls:
        return f"collections.deque({args})" if args else "collections.deque()"
    if "HashSet" in cls or cls.endswith("Set"):
        return f"set({args})" if args else "set()"
    if "HashMap" in cls or cls.endswith("Map"):
        return f"dict({args})" if args else "{}"
    if "PriorityQueue" in cls:
        return f"list({args})" if args else "[]"
    cls_simple = _strip_generics(cls)
    return f"{cls_simple}({args})"

def _map_this(s: str) -> str:
    return s.replace("this.", "self.")

def _map_instanceof(s: str) -> str:
    m = re.match(r"^(.*)\s+instanceof\s+([A-Za-z0-9_.<>]+)\s*;?$", s)
    if m:
        expr = m.group(1).strip()
        t = _strip_generics(m.group(2).strip())
        return f"isinstance({expr}, {t})"
    return s

def _map_incdec(s: str) -> str:
    s_strip = s.strip().rstrip(";")
    m = re.match(r"^([A-Za-z_][A-Za-z0-9_.]*)\s*(\+\+|--)\s*$", s_strip)
    if m:
        var, op = m.group(1), m.group(2)
        var = var.replace("this.", "self.")
        return f"{var} += 1" if op == "++" else f"{var} -= 1"
    return s

def _map_logical_ops(s: str) -> str:
    out = s
    out = out.replace("&&", "and").replace("||", "or")
    out = re.sub(r"!\s*(?!=)", "not ", out)
    return out

def _map_ternary(s: str) -> Optional[str]:
    if "?" not in s or ":" not in s:
        return None
    head, rest = s.split("?", 1)
    tpart, fpart = rest.split(":", 1)
    return f"{tpart.strip()} if {head.strip()} else {fpart.strip()}"

def _replace_get_calls(s: str) -> str:
    out = s
    idx = 0
    while True:
        pos = out.find(".get(", idx)
        if pos == -1:
            break
        start = pos + 5
        depth = 0
        i = start
        while i < len(out):
            ch = out[i]
            if ch == "(":
                depth += 1
            elif ch == ")":
                if depth == 0:
                    args = out[start:i]
                    out = out[:pos] + f"[{args}]" + out[i + 1:]
                    idx = pos + 1
                    break
                depth -= 1
            i += 1
        else:
            break
    return out

def _replace_contains_calls(s: str) -> str:
    out = s
    idx = 0
    while True:
        pos = out.find(".contains(", idx)
        if pos == -1:
            break
        prefix = out[:pos]
        m = re.search(r"([A-Za-z_][A-Za-z0-9_\.]*\([^()]*\)|[A-Za-z_][A-Za-z0-9_\.]*)$", prefix)
        if not m:
            idx = pos + 1
            continue
        base = m.group(1)
        base_start = m.start(1)
        arg_start = pos + 10
        depth = 0
        i = arg_start
        while i < len(out):
            ch = out[i]
            if ch == "(":
                depth += 1
            elif ch == ")":
                if depth == 0:
                    args = out[arg_start:i]
                    out = out[:base_start] + f"{args} in {base}" + out[i + 1:]
                    idx = base_start + 1
                    break
                depth -= 1
            i += 1
        else:
            break
    return out

def _extract_call_args(s: str, marker: str) -> Optional[Tuple[str, int, int]]:
    idx = s.find(marker)
    if idx == -1:
        return None
    start = idx + len(marker)
    depth = 0
    i = start
    while i < len(s):
        ch = s[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            if depth == 0:
                return s[start:i], idx, i
            depth -= 1
        i += 1
    return None

def _rewrite_common_expr(s: str) -> str:
    out = s
    out = re.sub(r"\bnull\b", "None", out)
    out = re.sub(r"\btrue\b", "True", out, flags=re.IGNORECASE)
    out = re.sub(r"\bfalse\b", "False", out, flags=re.IGNORECASE)
    out = re.sub(r"\bthis\b", "self", out)
    out = out.replace("this.", "self.")
    out = _strip_generics_from_types(out)
    out = re.sub(r"\bnew\s+[A-Za-z_][A-Za-z0-9_<>.]*\s*\[\s*(.*?)\s*\]", r"[None] * \1", out)
    out = re.sub(r"\bnew\s+([A-Za-z_][A-Za-z0-9_<>.]*)\s*\(", r"\1(", out)
    out = re.sub(r"\bList\.of\(([^)]*)\)", r"[\1]", out)
    out = out.replace("ArrayList(", "list(")
    out = out.replace("PriorityQueue(", "list(")
    out = re.sub(r"\b([A-Za-z_][A-Za-z0-9_\.]*)\.size\(\)", r"len(\1)", out)
    out = re.sub(r"\b([A-Za-z_][A-Za-z0-9_\.]*)\.isEmpty\(\)", r"(not \1)", out)
    out = re.sub(r"([A-Za-z_][A-Za-z0-9_\.]*\([^()]*\))\.size\(\)", r"len(\1)", out)
    out = re.sub(r"([A-Za-z_][A-Za-z0-9_\.]*\([^()]*\))\.isEmpty\(\)", r"(not \1)", out)
    out = _replace_get_calls(out)
    out = _replace_contains_calls(out)
    if "Comparator.comparingInt" in out:
        extracted = _extract_call_args(out, "Comparator.comparingInt(")
        if extracted:
            args, idx, end = extracted
            var, body = _parse_lambda(args.strip())
            if var and body:
                body = _rewrite_common_expr(body)
                out = out[:idx] + f"lambda {var}: {body}" + out[end + 1:]
    if "list(" in out:
        extracted = _extract_call_args(out, "list(")
        if extracted:
            args, idx, end = extracted
            if args.strip().startswith("lambda "):
                out = out[:idx] + "list()" + out[end + 1:]
    out = _map_logical_ops(out)
    tern = _map_ternary(out)
    return tern if tern else out

def _map_method_chain_basic(s: str, is_field_ref=None) -> Optional[str]:
    base, chain = _parse_method_chain(s)
    if not base or not chain:
        return None
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_\.]*$", base):
        return None
    base = _rewrite_common_expr(base)
    if is_field_ref and _is_simple_ident(base) and is_field_ref(base):
        base = f"self.{base}"
    for idx, (name, args) in enumerate(chain):
        args = _rewrite_common_expr(args.strip())
        last = idx == len(chain) - 1
        if name == "get":
            base = f"{base}[{args}]"
            continue
        if args == "":
            base = f"{base}.{name}()"
            continue
        if name == "size" and last:
            return f"len({base})"
        if name == "isEmpty" and last:
            return f"(not {base})"
        if name == "add" and last:
            return f"{base}.append({args})"
        if name == "poll" and last:
            return f"{base}.pop(0)"
        if name == "peek" and last:
            return f"{base}[0]"
        if name == "contains" and last:
            return f"{args} in {base}"
        return None
    return base

def _is_class_like(name: str) -> bool:
    return bool(name) and name[0].isupper()

def _parse_method_chain(s: str):
    first = re.search(r"\.[A-Za-z_][A-Za-z0-9_]*\s*\(", s)
    if not first:
        return None, []
    base = s[:first.start()].strip()
    if not base:
        return None, []
    idx = first.start()
    chain = []
    while idx < len(s):
        if s[idx] != ".":
            break
        idx += 1
        m = re.match(r"[A-Za-z_][A-Za-z0-9_]*", s[idx:])
        if not m:
            break
        name = m.group(0)
        idx += len(name)
        while idx < len(s) and s[idx].isspace():
            idx += 1
        if idx >= len(s) or s[idx] != "(":
            break
        depth = 0
        arg_start = idx + 1
        idx += 1
        in_sq = in_dq = False
        escaped = False
        while idx < len(s):
            ch = s[idx]
            if ch == "\\" and not escaped:
                escaped = True
                idx += 1
                continue
            if ch == "'" and not escaped and not in_dq:
                in_sq = not in_sq
            elif ch == '"' and not escaped and not in_sq:
                in_dq = not in_dq
            if not in_sq and not in_dq:
                if ch == "(":
                    depth += 1
                elif ch == ")":
                    if depth == 0:
                        break
                    depth -= 1
            escaped = False
            idx += 1
        if idx >= len(s) or s[idx] != ")":
            break
        args = s[arg_start:idx]
        chain.append((name, args))
        idx += 1
    return base, chain

def _parse_lambda(expr: str) -> Tuple[Optional[str], Optional[str]]:
    if "->" not in expr:
        return None, None
    lhs, rhs = expr.split("->", 1)
    var = lhs.strip().strip("()")
    body = rhs.strip()
    return var, body

def _parse_method_reference(expr: str) -> Tuple[Optional[str], Optional[str]]:
    if "::" not in expr:
        return None, None
    owner, method = expr.split("::", 1)
    owner = owner.strip()
    method = method.strip()
    if not owner or not method:
        return None, None
    return owner, method

def _map_method_ref_to_lambda_body(owner: str, method: str, var: str) -> Optional[str]:
    mapping = {
        ("String", "valueOf"): f"str({var})",
        ("String", "trim"): f"{var}.strip()",
        ("Integer", "parseInt"): f"int({var})",
        ("Long", "parseLong"): f"int({var})",
        ("Double", "parseDouble"): f"float({var})",
        ("Objects", "nonNull"): f"{var} is not None",
        ("Objects", "isNull"): f"{var} is None",
    }
    if (owner, method) in mapping:
        return mapping[(owner, method)]
    if method == "toString":
        return f"str({var})"
    if method == "length":
        return f"len({var})"
    return None

def _map_stream_chain(expr: str) -> Optional[str]:
    s = expr.strip().rstrip(";")
    if ".stream()" not in s:
        return None
    base, chain = _parse_method_chain(s)
    if not base or not chain or chain[0][0] != "stream":
        return None
    base = base.replace("this.", "self.")
    filter_expr = None
    map_expr = None
    collect = None
    collect_args = ""
    distinct = False
    limit_val = None
    sorted_key = None
    for_each = None
    for name, args in chain[1:]:
        if name == "filter":
            expr_args = args.strip()
            var, body = _parse_lambda(expr_args)
            if var and body:
                filter_expr = (var, _rewrite_common_expr(body))
            else:
                owner, method = _parse_method_reference(expr_args)
                if owner and method:
                    ref_body = _map_method_ref_to_lambda_body(owner, method, "x")
                    if ref_body:
                        filter_expr = ("x", _rewrite_common_expr(ref_body))
        elif name == "map":
            expr_args = args.strip()
            var, body = _parse_lambda(expr_args)
            if var and body:
                map_expr = (var, _rewrite_common_expr(body))
            else:
                owner, method = _parse_method_reference(expr_args)
                if owner and method:
                    ref_body = _map_method_ref_to_lambda_body(owner, method, "x")
                    if ref_body:
                        map_expr = ("x", _rewrite_common_expr(ref_body))
        elif name == "mapToInt":
            expr_args = args.strip()
            var, body = _parse_lambda(expr_args)
            if var and body:
                map_expr = (var, _rewrite_common_expr(body))
            else:
                owner, method = _parse_method_reference(expr_args)
                if owner and method:
                    ref_body = _map_method_ref_to_lambda_body(owner, method, "x")
                    if ref_body:
                        map_expr = ("x", _rewrite_common_expr(ref_body))
        elif name == "sorted":
            expr_args = args.strip()
            if expr_args:
                var, body = _parse_lambda(expr_args)
                if var and body:
                    sorted_key = f"lambda {var}: {_rewrite_common_expr(body)}"
        elif name == "distinct":
            distinct = True
        elif name == "limit":
            limit_val = args.strip()
        elif name == "forEach":
            for_each = args.strip()
        elif name == "collect":
            collect = args.strip()
            collect_args = args.strip()
        else:
            return None
    if not collect and not for_each:
        # 检查是否有sum()操作
        for name, args in chain[1:]:
            if name == "sum":
                iter_var = (map_expr or filter_expr or ("x", ""))[0]
                map_body = map_expr[1] if map_expr else iter_var
                cond = None
                if filter_expr:
                    filter_var, filter_body = filter_expr
                    if filter_var != iter_var:
                        return None
                    cond = filter_body
                if cond:
                    return f"sum({map_body} for {iter_var} in {base} if {cond})"
                else:
                    return f"sum({map_body} for {iter_var} in {base})"
        iter_var = (map_expr or filter_expr or ("x", ""))[0]
    map_body = map_expr[1] if map_expr else iter_var
    cond = None
    if filter_expr:
        filter_var, filter_body = filter_expr
        if filter_var != iter_var:
            return None
        cond = filter_body
    if cond:
        iter_expr = f"({map_body} for {iter_var} in {base} if {cond})"
    else:
        iter_expr = f"({map_body} for {iter_var} in {base})"
    if distinct:
        iter_expr = f"dict.fromkeys({iter_expr})"
    if sorted_key:
        iter_expr = f"sorted({iter_expr}, key={sorted_key})"
    if limit_val:
        iter_expr = f"itertools.islice({iter_expr}, {limit_val})"
    if for_each:
        return f"list(map({for_each}, {iter_expr}))"
    if not collect:
        return None
    if "Collectors.toList" in collect:
        return f"list({iter_expr})"
    if "Collectors.toSet" in collect:
        return f"set({iter_expr})"
    if "Collectors.joining" in collect:
        sep = collect_args[collect_args.find("(") + 1:collect_args.rfind(")")] if "(" in collect_args else ""
        sep = sep.strip() or '""'
        return f"{sep}.join(str(x) for x in {iter_expr})"
    return None

class ExprConverter:
    """表达式转换（加强：声明+赋值优先；println 自带 self.；getMessage() -> str(ex) 等）"""
    def __init__(self, root=None):
        self.root = root

    def _is_field(self, name: str) -> bool:
        if not name:
            return False
        try:
            if self.root and self.root.is_local(name):
                return False
        except Exception:
            pass
        try:
            return name in getattr(self.root, "field_info", {}) or name in getattr(self.root, "field_names", set())
        except Exception:
            return False

    def _maybe_prefix_field(self, name: str) -> str:
        if _is_simple_ident(name) and self._is_field(name):
            return f"self.{name}"
        return name

    def _track_required_imports(self, expr: str) -> None:
        if not expr or not self.root:
            return
        try:
            if "collections.deque" in expr:
                self.root.required_imports.add("import collections")
            if "random." in expr:
                self.root.required_imports.add("import random")
            if "datetime." in expr:
                self.root.required_imports.add("import datetime")
            if "math." in expr:
                self.root.required_imports.add("import math")
            if "itertools." in expr:
                self.root.required_imports.add("import itertools")
        except Exception:
            pass

    def _rewrite_expr(self, expr: str) -> str:
        out = _rewrite_common_expr(expr)
        return self._qualify_nested_class_call(out)

    def _qualify_nested_class_call(self, expr: str) -> str:
        if not self.root:
            return expr
        try:
            class_stack = list(getattr(self.root, "class_stack", []))
            nested_stack = list(getattr(self.root, "nested_class_stack", []))
        except Exception:
            return expr
        if not class_stack or not nested_stack:
            return expr

        def replace(match):
            name = match.group(1)
            if not _is_class_like(name):
                return match.group(0)
            if match.start(1) > 0 and expr[match.start(1) - 1] == ".":
                return match.group(0)
            for cls_name, nested in zip(reversed(class_stack), reversed(nested_stack)):
                if name in nested:
                    return match.group(0).replace(name, f"{cls_name}.{name}", 1)
            return match.group(0)

        return re.sub(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(", replace, expr)

    # --------- 工具：在 f-string 中把字段名补 self.，并把 getMessage() -> str(obj) ----------
    def _normalize_nonliteral_expr(self, p: str) -> str:
        s = p.strip()
        # owner.getMessage() -> str(owner)
        s = re.sub(r"\b([A-Za-z_]\w*)\.getMessage\(\)", r"str(\1)", s)
        # 简单标识符且是类字段 -> 加 self.
        try:
            # 仅对类字段加 self.，避免局部变量被误判
            if _is_simple_ident(s):
                return self._maybe_prefix_field(s)
        except Exception:
            pass
        return s

    def _fstring_from_concat(self, parts: List[str]) -> str:
        out = []
        for p in parts:
            p = p.strip()
            if not p:
                continue
            m = re.match(r"^(['\"])(.*)\1$", p, re.DOTALL)
            if m:
                out.append(p)
            else:
                expr = self._normalize_nonliteral_expr(p)
                out.append(f"str({expr})")
        return " + ".join(out) if out else '""'

    def _print_from_inner(self, inner: str, newline: bool) -> str:
        suffix = "" if newline else ", end=\"\""
        if "+" in inner:
            parts = _split_concat(inner)
            fstr = self._fstring_from_concat(parts)
            return f"print({fstr}{suffix})"
        return f"print({inner}{suffix})"

    def _expr_from_child(self, node) -> str:
        lines = self.convert(node)
        return lines[0] if lines else ""

    # --------- 方法/静态调用 ----------
    def _map_method_call(self, owner: str, method: str, argstr: str) -> str:
        owner_py = owner.replace("this.", "self.")
        if _is_simple_ident(owner_py):
            owner_py = self._maybe_prefix_field(owner_py)
        owner_var = owner_py.split(".")[-1]
        args = split_args(argstr)
        pq_key = None
        try:
            pq_key = self.root.pq_keys.get(owner_var)
        except Exception:
            pq_key = None
        if pq_key and method in ("add", "offer") and len(args) >= 1:
            try:
                self.root.required_imports.add("import heapq")
            except Exception:
                pass
            item = self._rewrite_expr(args[0])
            try:
                for original, alias in getattr(self.root, "param_alias", {}).items():
                    item = re.sub(rf"\b{re.escape(original)}\b", alias, item)
            except Exception:
                pass
            return f"heapq.heappush({owner_py}, ({pq_key}({item}), {item}))"
        if pq_key and method == "poll" and len(args) == 0:
            try:
                self.root.required_imports.add("import heapq")
            except Exception:
                pass
            return f"heapq.heappop({owner_py})[1]"
        if pq_key and method == "peek" and len(args) == 0:
            return f"{owner_py}[0][1]"

        owner_base = None
        try:
            owner_base = self.root.symtab.get(owner_var)
        except Exception:
            pass

        # equals / size / equalsIgnoreCase / getMessage
        if method == "equals" and len(args) == 1:
            return f"({owner_py} == {args[0]})"
        if method in ("size", "length") and len(args) == 0:
            return f"len({owner_py})"
        if method == "equalsIgnoreCase" and len(args) == 1:
            return f"({owner_py}.lower() == {args[0]}.lower())"
        if method == "getMessage" and len(args) == 0:
            return f"str({owner_py})"
        if method == "containsAll" and len(args) == 1:
            return f"{args[0]}.issubset({owner_py})"
        if method == "addAll" and len(args) == 1:
            if owner_base and ("Set" in owner_base or "HashSet" in owner_base):
                return f"{owner_py}.update({args[0]})"
            else:
                return f"{owner_py}.extend({args[0]})"

        from converter.mappings import map_method
        if owner_base:
            mapped, _ = map_method(owner_base, method)
            if mapped:
                if mapped == "update_put" and len(args) >= 2:
                    return f"{owner_py}[{args[0]}] = {args[1]}"
                if mapped in ("__setitem__",) and len(args) >= 2:
                    return f"{owner_py}[{args[0]}] = {args[1]}"
                if mapped in ("__getitem__",) and len(args) >= 1:
                    return f"{owner_py}[{args[0]}]"
                if mapped == "__contains__" and len(args) >= 1:
                    return f"{args[0]} in {owner_py}"
                if mapped == "len" and len(args) == 0:
                    return f"len({owner_py})"
                if mapped == "not" and len(args) == 0:
                    return f"(not {owner_py})"
                if mapped == "pop0" and len(args) == 0:
                    return f"{owner_py}.pop(0)"
                if mapped == "peek" and len(args) == 0:
                    return f"{owner_py}[0]"
                if mapped == "contains_value" and len(args) >= 1:
                    return f"{args[0]} in {owner_py}.values()"
                if mapped == "contains_all" and len(args) >= 1:
                    return f"all(item in {owner_py} for item in {args[0]})"
                if mapped == "slice" and len(args) >= 2:
                    return f"{owner_py}[{args[0]}:{args[1]}]"
                if mapped == "for_each" and len(args) >= 1:
                    return f"list(map({args[0]}, {owner_py}))"
                if mapped == "len" and len(args) == 0:
                    return f"len({owner_py})"
                return f"{owner_py}.{mapped}({', '.join(args)})"
            try:
                self.root.stats["unmapped_methods"][f"{owner_base}.{method}"] += 1
            except Exception:
                pass

        return f"{owner_py}.{method}({argstr})"

    def _map_static_call(self, cls: str, method: str, argstr: str) -> str:
        args = split_args(argstr)
        if cls in ("Math", "java.lang.Math"):
            if method in ("max", "min", "abs") and len(args) >= 1:
                return f"{method}({', '.join(args)})"
            if method == "pow" and len(args) >= 2:
                return f"pow({', '.join(args[:2])})"
            if method in ("sqrt", "ceil", "floor"):
                try:
                    self.root.required_imports.add("import math")
                except Exception:
                    pass
                return f"math.{method}({', '.join(args)})"
        if cls in ("List", "java.util.List") and method == "of":
            return "[" + ", ".join(args) + "]"
        if cls in ("Comparator", "java.util.Comparator") and method == "comparingInt" and len(args) == 1:
            var, body = _parse_lambda(args[0])
            if var and body:
                body = _rewrite_common_expr(body)
                return f"lambda {var}: {body}"
        if cls in ("Collections", "java.util.Collections"):
            if method == "sort" and len(args) >= 1:
                return f"{args[0]}.sort()"
            if method == "reverse" and len(args) >= 1:
                return f"{args[0]}.reverse()"
            if method == "shuffle" and len(args) >= 1:
                try:
                    self.root.required_imports.add("import random")
                except Exception:
                    pass
                return f"random.shuffle({args[0]})"
        if cls in ("Arrays", "java.util.Arrays"):
            if method == "asList":
                return "[" + ", ".join(args) + "]"
            if method == "copyOf" and len(args) >= 1:
                return f"list({args[0]})"
            if method == "sort" and len(args) >= 1:
                return f"sorted({args[0]})"
        if cls in ("Math", "java.lang.Math"):
            if method in ("max", "min", "abs", "pow") and len(args) >= 1:
                return f"{method}({', '.join(args)})"
            if method in ("sqrt", "ceil", "floor") and len(args) >= 1:
                try:
                    self.root.required_imports.add("import math")
                except Exception:
                    pass
                return f"math.{method}({', '.join(args)})"
            if method == "random":
                try:
                    self.root.required_imports.add("import random")
                except Exception:
                    pass
                return "random.random()"
        if cls in ("Objects", "java.util.Objects"):
            if method == "requireNonNull" and len(args) >= 1:
                return f"assert {args[0]} is not None"
        if cls in ("UUID", "java.util.UUID"):
            if method == "randomUUID" and len(args) == 0:
                try:
                    self.root.required_imports.add("import uuid")
                except Exception:
                    pass
                return "uuid.uuid4()"
            if method == "fromString" and len(args) == 1:
                try:
                    self.root.required_imports.add("import uuid")
                except Exception:
                    pass
                return f"uuid.UUID('{args[0]}')"
        if cls in ("Instant", "java.time.Instant"):
            if method == "now" and len(args) == 0:
                try:
                    self.root.required_imports.add("import datetime")
                except Exception:
                    pass
                return "datetime.datetime.now()"

        from converter.mappings import map_static
        templ, _ = map_static(cls, method)
        if templ:
            rendered = templ.replace("{args}", ", ".join(args))
            self._track_required_imports(rendered)
            return rendered
        return f"{cls}.{method}({argstr})"

    # --------- 主入口 ----------
    def convert(self, node) -> List[str]:
        if not node or not isinstance(node, dict):
            return []
        s = (node.get("name") or node.get("value") or get_attr(node, "expr") or get_attr(node, "code") or "").strip()
        t = node.get("type", "")

        if "\n" in s:
            return [f"# {ln}" if ln.strip() else "#" for ln in s.splitlines()]

        if re.match(r"^-?\d+(\.\d+)?$", s):
            return [s]

        raw_s = s
        pq_call = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\.(add|offer|poll|peek)\((.*)\)\s*;?$", s)
        if pq_call:
            owner, method, argstr = pq_call.group(1), pq_call.group(2), pq_call.group(3)
            try:
                if owner in getattr(self.root, "pq_keys", {}):
                    return [self._map_method_call(owner, method, argstr)]
            except Exception:
                pass

        base, _ = _parse_method_chain(s)
        if base and _is_simple_ident(base) and self._is_field(base):
            s = re.sub(rf"^{re.escape(base)}\b", f"self.{base}", s)

        chain_mapped = _map_method_chain_basic(s)
        if chain_mapped:
            try:
                for original, alias in getattr(self.root, "param_alias", {}).items():
                    chain_mapped = re.sub(rf"\b{re.escape(original)}\b", alias, chain_mapped)
            except Exception:
                pass
            chain_mapped = self._qualify_nested_class_call(chain_mapped)
            return [chain_mapped]

        s = _rewrite_common_expr(s)
        s = self._qualify_nested_class_call(s)
        try:
            for original, alias in getattr(self.root, "param_alias", {}).items():
                s = re.sub(rf"\b{re.escape(original)}\b", alias, s)
        except Exception:
            pass

        # 0) 空
        if not s:
            if t == "BinaryExpr":
                chs = node.get("children", []) or []
                if len(chs) >= 2:
                    left = self._expr_from_child(chs[0])
                    right = self._expr_from_child(chs[1])
                    if left and right:
                        return [f"{left} + {right}"]
            code = get_attr(node, "code")
            if isinstance(code, str) and code.strip():
                return [code.strip()]
            return []
        if t in ("NameExpr", "SimpleName"):
            rewritten = _rewrite_common_expr(s)
            return [self._maybe_prefix_field(rewritten)] if rewritten else []
        if _is_simple_ident(s):
            rewritten = _rewrite_common_expr(s)
            return [self._maybe_prefix_field(rewritten)]
        if t == "ThisExpr":
            return ["self"]
        if t == "FieldAccessExpr":
            owner = None
            for ch in node.get("children", []) or []:
                ctype = ch.get("type")
                if ctype == "ThisExpr":
                    owner = "self"
                    break
                if ctype == "NameExpr":
                    owner = ch.get("name")
                    break
            if owner and node.get("name"):
                if _is_simple_ident(owner):
                    owner = self._maybe_prefix_field(owner)
                return [f"{owner}.{node['name']}"]
            return [node.get("name", "")] if node.get("name") else []

        # 1) println/print（自带 self. / getMessage() 修复）
        if s.startswith("System.out.println"):
            i1, i2 = s.find("("), s.rfind(")")
            inner = s[i1+1:i2] if (i1 != -1 and i2 != -1 and i2 > i1) else ""
            return [self._print_from_inner(inner, newline=True)]
        if s.startswith("System.out.print"):
            i1, i2 = s.find("("), s.rfind(")")
            inner = s[i1+1:i2] if (i1 != -1 and i2 != -1 and i2 > i1) else ""
            return [self._print_from_inner(inner, newline=False)]

        # 1.5) stream 链式调用（map/filter/collect）
        stream_mapped = _map_stream_chain(s)
        if stream_mapped:
            self._track_required_imports(stream_mapped)
            return [stream_mapped]

        chain_mapped = _map_method_chain_basic(s, self.root.is_field_ref)
        if chain_mapped:
            chain_mapped = self._qualify_nested_class_call(chain_mapped)
            return [chain_mapped]

        # 2) 变量声明赋值优先：Type var = rhs;
        mdecl = re.match(r"^([A-Za-z0-9_<>.\[\]]+)\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)\s*;?$", s)
        if mdecl:
            jtype, var, rhs = mdecl.group(1), mdecl.group(2), mdecl.group(3)
            # 记录符号表（用于 list.add / Map.put 映射）
            base = jtype.split(".")[-1]
            if "<" in base: base = base.split("<",1)[0]
            try:
                if hasattr(self.root, "symtab"):
                    self.root.symtab[var] = base
                self.root.add_local(var)
            except Exception:
                pass
            try:
                self.root.add_local(var)
            except Exception:
                pass
            # 右值：new -> Python 等价；字段名 -> self.<field>
            raw_decl = re.match(
                r"^([A-Za-z0-9_<>.\[\]]+)\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)\s*;?$",
                raw_s,
            )
            raw_rhs = raw_decl.group(3) if raw_decl else rhs
            if "PriorityQueue" in jtype and "Comparator.comparingInt" in raw_rhs:
                extracted = _extract_call_args(raw_rhs, "Comparator.comparingInt(")
                if extracted:
                    args, _, _ = extracted
                    lvar, body = _parse_lambda(args.strip())
                    if lvar and body:
                        key_name = f"{var}_key"
                        self.root.pq_keys[var] = key_name
                        try:
                            self.root.required_imports.add("import heapq")
                        except Exception:
                            pass
                        body = _rewrite_common_expr(body)
                        return [f"{key_name} = lambda {lvar}: {body}", f"{var} = []"]
            rhs_conv = _map_new_full(rhs) if rhs.strip().startswith("new ") else rhs.strip()
            self._track_required_imports(rhs_conv)
            if _is_simple_ident(rhs_conv):
                rhs_conv = self._maybe_prefix_field(rhs_conv)
            return [f"{var} = {rhs_conv}"]

        # 3) 赋值 + new（剩余情况）
        if " = new " in s or s.startswith("new "):
            # 如果是 "var = new ..." 也能处理；若是 "Type var = new ..." 已被上面的 mdecl 截获
            if " = new " in s:
                left, _, rhs = s.partition("=")
                rhs_conv = _map_new_full(rhs)
                self._track_required_imports(rhs_conv)
                return [f"{left.strip()} = {rhs_conv}"]
            rhs_conv = _map_new_full(s)
            self._track_required_imports(rhs_conv)
            return [rhs_conv]

        # 4) this. -> self.
        if "this." in s:
            s = _map_this(s)

        # 5) instanceof
        if " instanceof " in s:
            return [_map_instanceof(s)]

        # 6) ++ / --
        incdec = _map_incdec(s)
        if incdec != s:
            return [incdec]

        # 7) obj.method(args) / Class.static(args)
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_\.]*)\.(\w+)\((.*)\)\s*;?$", s)
        if m:
            owner, method, argstr = m.group(1), m.group(2), m.group(3)
            if _is_class_like(owner) and (owner.split(".")[-1] not in getattr(self.root, "symtab", {})):
                return [self._map_static_call(owner, method, argstr)]
            return [self._map_method_call(owner, method, argstr)]

        # 8) 裸字符串拼接 -> print(f"...")
        if "+" in s and "System.out." not in s and "(" not in s:
            parts = _split_concat(s)
            if len(parts) > 1:
                fstr = self._fstring_from_concat(parts)
                return [f"print({fstr})"]

        # 9) 赋值优先处理 RHS
        if "=" in s and "==" not in s and "!=" not in s:
            left, right = s.split("=", 1)
            rhs = right.strip().rstrip(";")
            rhs = self._rewrite_expr(rhs)
            try:
                for original, alias in getattr(self.root, "param_alias", {}).items():
                    rhs = re.sub(rf"\b{re.escape(original)}\b", alias, rhs)
            except Exception:
                pass
            if left.strip().startswith("self.") and _is_simple_ident(left.strip()[5:]):
                field_name = left.strip()[5:]
                try:
                    self.root.field_names.add(field_name)
                    self.root.field_info.setdefault(field_name, {"visibility": "unknown"})
                except Exception:
                    pass
            m = re.match(r"^([A-Za-z_][A-Za-z0-9_\.]*)\.(\w+)\((.*)\)\s*$", rhs)
            if m:
                owner, method, argstr = m.group(1), m.group(2), m.group(3)
                rhs = self._map_method_call(owner, method, argstr)
            return [f"{left.strip()} = {rhs}"]
        # 10) 普通调用/条件/索引原样
        if s.endswith(")"):
            return [s.rstrip(";")]
        if "[" in s or "]" in s:
            return [s.rstrip(";")]
        if re.search(r"\b(and|or|not)\b|[<>!=]=|[<>]", s):
            return [s.rstrip(";")]
        if "=" in s:
            return [s.rstrip(";")]

        # 10) 兜底
        return [f"# expr: {s}"]
