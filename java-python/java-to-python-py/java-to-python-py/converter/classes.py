# converter/classes.py
from typing import List
from converter.util import children, collect_doc, get_attr
from converter.mappings import map_type

class TopClassConverter:
    """
    处理 Class / Interface / Enum / Record 四类顶层或嵌套类型。
    - JSON 里若出现 "ClassOrInterfaceDeclaration"：
        * 通过 node.get("value") == "interface" 判定为 interface，否则按 class 处理
    - 也兼容直接出现 "Class" / "Interface" / "EnumDeclaration" / "RecordDeclaration"
    """

    def __init__(self, root):
        self.root = root

    # ---------- docstring ----------
    def _doc_lines(self, node) -> List[str]:
        """
        收集 Javadoc/注释，安全处理三连引号。返回【不带缩进】的行，由调用侧按需要加 4 空格。
        """
        doc = collect_doc(node)
        if not doc:
            return []
        safe = doc.replace('"""', '\\"""')
        return ['"""' + safe + '"""']

    # ---------- Enum ----------
    def convert_enum(self, node) -> List[str]:
        out = ["import enum", ""]
        name = node.get("name", "Enum")
        out.append(f"class {name}(enum.Enum):")
        # doc
        for dl in self._doc_lines(node):
            out.append("    " + dl)
        # constants
        constants = [ch.get("name") for ch in children(node)
                     if ch.get("type") in ("EnumConstantDeclaration", "EnumConstant")]
        if not constants:
            out.append("    pass")
        else:
            for i, c in enumerate(constants):
                out.append(f"    {c} = {i}")
        out.append("")
        return out

    # ---------- Record ----------
    def convert_record(self, node) -> List[str]:
        out = ["from dataclasses import dataclass", ""]
        name = node.get("name", "Record")
        out.append("@dataclass")
        out.append(f"class {name}:")
        for dl in self._doc_lines(node):
            out.append("    " + dl)
        # record 参数（方案B里通常把参数作为 Parameter 子节点，类型在 attrs.type）
        params = [ch for ch in children(node) if ch.get("type") in ("Parameter", "RecordComponent", "Component")]
        if not params:
            # 兼容：有的 JSON 把字段作为 Field/FieldDeclaration
            fields = [ch for ch in children(node) if ch.get("type") in ("Field", "FieldDeclaration")]
            if not fields:
                out.append("    pass")
            else:
                for f in fields:
                    vars_ = [v for v in children(f) if v.get("type") in ("VariableDeclarator", "Variable")]
                    etype = f.get("value")
                    for v in vars_:
                        p_name = v.get("name", "field")
                        p_type = v.get("value") or etype
                        mapped = map_type(p_type) if p_type else None
                        out.append(f"    {p_name}: {mapped or 'object'} = None")
        else:
            for p in params:
                p_name = p.get("name", "field")
                p_type = get_attr(p, "type") or p.get("value")
                mapped = map_type(p_type) if p_type else None
                out.append(f"    {p_name}: {mapped or 'object'} = None")
        out.append("")
        return out

    # ---------- Interface ----------
    def convert_interface(self, node) -> List[str]:
        out = ["import abc", ""]
        name = node.get("name", "Interface")
        out.append(f"class {name}(abc.ABC):")
        for dl in self._doc_lines(node):
            out.append("    " + dl)
        methods = [ch for ch in children(node) if ch.get("type") in ("Method", "MethodDeclaration", "Function")]
        if not methods:
            out.append("    pass")
        else:
            for m in methods:
                mname = m.get("name","method")
                params = [ch.get("name") for ch in children(m) if ch.get("type") == "Parameter"]
                params_s = ", ".join(params)
                out.append("    @abc.abstractmethod")
                out.append(f"    def {mname}(self{', ' + params_s if params_s else ''}):")
                out.append("        raise NotImplementedError")
        out.append("")
        return out

    # ---------- Class ----------
    def convert_class(self, node) -> List[str]:
        # reset per-class field state
        try:
            self.root.field_conv.reset_for_class()
        except Exception:
            pass
        # 仅为当前类维护字段集合，供表达式转换判定 self.
        try:
            self.root.field_names = set()
        except Exception:
            pass
        try:
            self.root.field_info = {}
        except Exception:
            pass

        nested_names = [
            ch.get("name") for ch in children(node)
            if ch.get("type") in (
                "ClassOrInterfaceDeclaration", "EnumDeclaration", "RecordDeclaration", "AnnotationDeclaration",
                "Class", "Interface"
            ) and ch.get("name")
        ]
        try:
            self.root.push_class(node.get("name", "Class"), nested_names)
        except Exception:
            pass

        name = node.get("name", "Class")
        out = [f"class {name}:"]
        for dl in self._doc_lines(node):
            out.append("    " + dl)

        # fields
        for ch in children(node):
            if ch.get("type") in ("Field", "FieldDeclaration"):
                fl = self.root.field_conv.convert(ch)
                for l in fl:
                    out.append(f"    {l}")

        # constructors
        constructors = [ch for ch in children(node) if ch.get("type") in ("Constructor", "ConstructorDeclaration")]
        has_init = bool(constructors)
        if constructors:
            mlines = self.root.method_conv.convert_constructors(constructors)
            for ml in mlines:
                out.append(f"    {ml}")

        # methods (handle overloads)
        method_nodes = [ch for ch in children(node) if ch.get("type") in ("Method", "MethodDeclaration", "Function")]
        if method_nodes:
            grouped = {}
            order = []
            for mnode in method_nodes:
                name = mnode.get("name", "<method>")
                is_static = self.root.method_conv._is_static(mnode)
                key = (name, is_static)
                if key not in grouped:
                    grouped[key] = []
                    order.append(key)
                grouped[key].append(mnode)
            for key in order:
                nodes = grouped[key]
                if len(nodes) > 1:
                    mlines = self.root.method_conv.convert_overloads(nodes)
                else:
                    mlines = self.root.method_conv.convert(nodes[0])
                for ml in mlines:
                    out.append(f"    {ml}")

        # synthesize __init__ if needed
        if not has_init:
            init_lines = self.root.field_conv.emit_init_if_needed()
            if init_lines:
                out.append("")
                for ml in init_lines:
                    out.append(f"    {ml}")

        # nested types
        for ch in children(node):
            if ch.get("type") in (
                "ClassOrInterfaceDeclaration", "EnumDeclaration", "RecordDeclaration", "AnnotationDeclaration",
                "Class", "Interface"  # 兼容备用
            ):
                nested = self.root.convert_node(ch)
                out.append("")
                for line in nested:
                    out.append("    " + line if line.strip() else "")

        # empty-body -> pass
        body_non_comments = [ln for ln in out[1:] if ln.strip() and not ln.strip().startswith("#")]
        if not body_non_comments:
            out.append("    pass")
        out.append("")
        try:
            self.root.pop_class()
        except Exception:
            pass
        return out

    # ---------- Dispatcher ----------
    def convert(self, node) -> List[str]:
        t = (node.get("type") or "").strip()
        # 明确枚举
        if t in ("Enum", "EnumDeclaration"):
            return self.convert_enum(node)
        # 记录
        if t in ("Record", "RecordDeclaration"):
            return self.convert_record(node)
        # 直接 Interface 类型
        if t in ("Interface", "InterfaceDeclaration"):
            return self.convert_interface(node)
        # ClassOrInterfaceDeclaration -> 进一步判定
        if t == "ClassOrInterfaceDeclaration":
            if (node.get("value") or "").strip().lower() == "interface":
                return self.convert_interface(node)
            return self.convert_class(node)
        # 回退：凡是能当成类的都当类
        return self.convert_class(node)
