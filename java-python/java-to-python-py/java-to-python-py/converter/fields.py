# converter/fields.py
from typing import List, Tuple, Optional
from converter.mappings import map_type                 # ✅ 正确：从 mappings 导入
from converter.util import children, get_attr, has_modifier, short_base_type, get_modifiers

class FieldConverter:
    """
    处理 FieldDeclaration：
      - static 字段 -> 直接类变量赋值
      - 非 static 字段 -> 累积；若类内无构造器，最后合成 __init__
      - 同时更新 root.symtab 用于后续表达式映射（list.add / map.put 等）
    """
    def __init__(self, root):
        self.root = root
        self._pending: List[Tuple[str, Optional[str], Optional[str]]] = []
        self._class_has_ctor: bool = False

    def reset_for_class(self):
        self._pending.clear()
        self._class_has_ctor = False

    def mark_has_ctor(self):
        self._class_has_ctor = True

    def convert(self, node) -> List[str]:
        out: List[str] = []
        is_static = has_modifier(node, "static")
        modifiers = set(get_modifiers(node))
        visibility = "public"
        if "private" in modifiers:
            visibility = "private"
        elif "protected" in modifiers:
            visibility = "protected"
        elif "public" in modifiers:
            visibility = "public"
        else:
            visibility = "package"
        field_type = node.get("value")  # Java 公共类型（elementType）
        vars = [ch for ch in children(node) if ch.get("type") in ("VariableDeclarator", "Variable")]
        if not vars:
            name = node.get("name") or ""
            if is_static:
                out.append(f"{name} = None  # static field")
            else:
                self._pending.append((name or "field", map_type(field_type) if field_type else None, None))
            return out

        for v in vars:
            vname = v.get("name", "field")
            vtype = v.get("value") or field_type
            py_t = map_type(vtype) if vtype else None
            init = get_attr(v, "initializer")

            # 更新符号表（按 Java 短名基类）
            try:
                base = short_base_type(vtype)
                if base:
                    self.root.symtab[vname] = base
            except Exception:
                pass

            if is_static:
                if init is None:
                    init = "None"
                if py_t:
                    out.append(f"{vname}: {py_t} = {init}")
                else:
                    out.append(f"{vname} = {init}")
            else:
                try:
                    self.root.field_names.add(vname)
                    self.root.field_info[vname] = {"visibility": visibility}
                except Exception:
                    pass
                self._pending.append((vname, py_t, init))
        return out

    def emit_init_if_needed(self) -> List[str]:
        if self._class_has_ctor or not self._pending:
            return []
        lines = ["def __init__(self):"]
        for (name, _py_t, init) in self._pending:
            rhs = init if init is not None else "None"
            lines.append(f"    self.{name} = {rhs}")
        return lines
