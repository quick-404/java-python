from typing import Any, Dict, List, Optional, Iterable

def get_attr(node: Dict, key: str, default=None):
    """取 node['attrs'][key] 或顶层 key。"""
    attrs = node.get("attrs") or {}
    return attrs.get(key, node.get(key, default))

def children(node: Dict) -> List[Dict]:
    return node.get("children", []) or []

def get_modifiers(node: Dict) -> List[str]:
    """将 attrs.modifiers 转为小写 token 列表。兼容 '[public, static]' / 'public static'。"""
    val = get_attr(node, "modifiers")
    if not val:
        return []
    s = str(val).strip().strip("[]")
    toks = []
    for tok in s.replace(",", " ").split():
        tok = tok.strip().lower()
        if tok:
            toks.append(tok)
    return toks

def has_modifier(node: Dict, mod: str) -> bool:
    return mod.lower() in get_modifiers(node)

def first_child(node: Dict, types: Iterable[str]) -> Optional[Dict]:
    ts = set(types)
    for ch in children(node):
        if ch.get("type") in ts:
            return ch
    return None

def all_children_of_type(node: Dict, types: Iterable[str]) -> List[Dict]:
    ts = set(types)
    return [ch for ch in children(node) if ch.get("type") in ts]

def collect_doc(node: Dict) -> Optional[str]:
    """仅提取 Javadoc 作为 docstring，避免与普通注释重复。"""
    jds = []
    for ch in children(node):
        if ch.get("type") != "Javadoc":
            continue
        content = ch.get("value") or ch.get("name") or ""
        if content:
            jds.append(str(content).strip())
    if jds:
        return "\n".join(jds).strip()
    return None

def to_comment_lines(text: str, indent: int = 0) -> List[str]:
    pad = " " * indent
    text = text or ""
    if not text:
        return []
    return [pad + "# " + ln for ln in text.splitlines()]

# -------------------- 类型/参数工具 --------------------

def short_base_type(java_type: Optional[str]) -> Optional[str]:
    """提取 Java 类型短名基类：List<String> -> List；java.util.Map -> Map；int -> int。"""
    if not java_type:
        return None
    s = str(java_type)
    if "<" in s:
        s = s.split("<", 1)[0]
    if "." in s:
        s = s.split(".")[-1]
    return s.strip() or None

def split_args(argstr: str) -> List[str]:
    """
    安全切分方法实参（支持括号/引号/泛型嵌套）。
    例如: 'a, b(c,d), new ArrayList<Set<X>>(1,2), "a,b"'
    -> ['a', 'b(c,d)', 'new ArrayList<Set<X>>(1,2)', '"a,b"']
    """
    if argstr is None:
        return []
    s = str(argstr).strip()
    if not s:
        return []
    args, cur = [], []
    paren = angle = 0
    in_sq = in_dq = False
    escaped = False
    for ch in s:
        if ch == "\\" and not escaped:
            escaped = True
            cur.append(ch)
            continue
        if ch == "'" and not escaped and not in_dq:
            in_sq = not in_sq
        elif ch == '"' and not escaped and not in_sq:
            in_dq = not in_dq
        elif not in_sq and not in_dq:
            if ch == '(':
                paren += 1
            elif ch == ')':
                paren = max(0, paren - 1)
            elif ch == '<':
                angle += 1
            elif ch == '>':
                angle = max(0, angle - 1)
            elif ch == ',' and paren == 0 and angle == 0:
                part = "".join(cur).strip()
                if part:
                    args.append(part)
                cur = []
                escaped = False
                continue
        cur.append(ch)
        escaped = False
    tail = "".join(cur).strip()
    if tail:
        args.append(tail)
    return args
