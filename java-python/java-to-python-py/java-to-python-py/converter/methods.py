import keyword
from typing import List
from converter.util import children, get_modifiers, collect_doc

_IGNORE_IN_BODY = {
    "Parameter", "Modifier", "SimpleName", "VoidType", "PrimitiveType",
    "ClassOrInterfaceType", "TypeParameter", "ReferenceType", "Name",
    "ReturnType",
}

class MethodConverter:
    def __init__(self, root):
        self.root = root

    def _is_static(self, node):
        return "static" in get_modifiers(node)

    def _collect_parameters(self, node):
        names = [p.get("name") for p in children(node) if p.get("type") == "Parameter"]
        return [self._sanitize_param(n) for n in names if n]

    def _sanitize_param(self, name: str) -> str:
        if not name:
            return name
        if keyword.iskeyword(name):
            alias = f"{name}_"
            try:
                self.root.param_alias[name] = alias
            except Exception:
                pass
            return alias
        return name

    def _collect_body_children(self, node):
        return [ch for ch in children(node) if ch.get("type") not in _IGNORE_IN_BODY]

    def _maybe_doc(self, node):
        doc = collect_doc(node)
        if not doc:
            return []
        safe = doc.replace('"""', '\\"""')
        return ['"""' + safe + '"""']

    def _uses_self(self, body: List[str]) -> bool:
        return any("self." in ln for ln in body if ln)

    def _toggle_doc_comment_suppression(self, enabled: bool):
        try:
            if enabled:
                self.root.doc_comment_suppression += 1
            else:
                self.root.doc_comment_suppression = max(0, self.root.doc_comment_suppression - 1)
        except Exception:
            pass

    def _ctor_condition(self, params, all_params):
        if not all_params:
            return None
        if not params:
            conds = [f"{p} is None" for p in all_params]
        else:
            conds = [f"{p} is not None" for p in params]
        return " and ".join(conds) if conds else None

    def _method_condition(self, params, all_params):
        return self._ctor_condition(params, all_params)

    def convert_overloads(self, nodes) -> List[str]:
        if not nodes:
            return []
        if len(nodes) == 1:
            return self.convert(nodes[0])

        name = nodes[0].get("name", "<method>")
        static = self._is_static(nodes[0])
        all_params = []
        overload_infos = []
        for mnode in nodes:
            params = self._collect_parameters(mnode)
            for p in params:
                if p not in all_params:
                    all_params.append(p)
            body = []
            try:
                self.root.push_scope(params)
            except Exception:
                pass
            for ch in self._collect_body_children(mnode):
                body.extend(self.root.convert_node(ch))
            try:
                self.root.pop_scope()
            except Exception:
                pass
            overload_infos.append((params, body))

        sig_params = [f"{p}=None" for p in all_params]
        if static and self._uses_self([ln for _, body in overload_infos for ln in body]):
            static = False
        if static:
            head = ["@staticmethod"]
            sig = f"def {name}({', '.join(sig_params)}):" if sig_params else f"def {name}():"
        else:
            sig = f"def {name}(self{', ' + ', '.join(sig_params) if sig_params else ''}):"
            head = []
        lines = head + [sig]
        doc_lines = self._maybe_doc(nodes[0])
        lines.extend(["    " + l for l in doc_lines])

        if static and name == "main" and all_params:
            guard_var = all_params[0]
            lines.append(f"    if {guard_var} is None:")
            lines.append(f"        {guard_var} = []")

        self._toggle_doc_comment_suppression(bool(doc_lines))
        for idx, (params, body) in enumerate(overload_infos):
            cond = self._method_condition(params, all_params)
            if idx == 0:
                branch = f"if {cond}:" if cond else "if True:"
            elif idx == len(overload_infos) - 1 and not cond:
                branch = "else:"
            else:
                branch = f"elif {cond}:" if cond else "else:"
            lines.append("    " + branch)
            body = body or ["pass"]
            lines.extend(["        " + l if l.strip() else "        " for l in body])
        self._toggle_doc_comment_suppression(False)
        return lines

    def convert_constructors(self, nodes) -> List[str]:
        if not nodes:
            return []
        if len(nodes) == 1:
            return self.convert(nodes[0])

        all_params = []
        ctor_infos = []
        for ct in nodes:
            params = self._collect_parameters(ct)
            for p in params:
                if p not in all_params:
                    all_params.append(p)
            body = []
            try:
                self.root.push_scope(params)
            except Exception:
                pass
            for ch in self._collect_body_children(ct):
                body.extend(self.root.convert_node(ch))
            try:
                self.root.pop_scope()
            except Exception:
                pass
            ctor_infos.append((params, body))

        sig_params = [f"{p}=None" for p in all_params]
        sig = f"def __init__(self{', ' + ', '.join(sig_params) if sig_params else ''}):"
        lines = [sig]
        lines.extend(["    " + l for l in self._maybe_doc(nodes[0])])

        for idx, (params, body) in enumerate(ctor_infos):
            cond = self._ctor_condition(params, all_params)
            if idx == 0:
                branch = f"if {cond}:" if cond else "if True:"
            elif idx == len(ctor_infos) - 1 and not cond:
                branch = "else:"
            else:
                branch = f"elif {cond}:" if cond else "else:"
            lines.append("    " + branch)
            body = body or ["pass"]
            lines.extend(["        " + l if l.strip() else "        " for l in body])

        try:
            self.root.field_conv.mark_has_ctor()
        except Exception:
            pass
        return lines

    def convert(self, node) -> List[str]:
        t = node.get("type", "")
        name = node.get("name", "<method>")

        if t in ("Constructor", "ConstructorDeclaration"):
            params = self._collect_parameters(node)
            sig = f"def __init__(self{', ' + ', '.join(params) if params else ''}):"
            body = []
            doc_lines = self._maybe_doc(node)
            body.extend(doc_lines)
            try:
                self.root.push_scope(params)
            except Exception:
                pass
            for ch in self._collect_body_children(node):
                body.extend(self.root.convert_node(ch))
            try:
                self.root.pop_scope()
            except Exception:
                pass
            self._toggle_doc_comment_suppression(bool(doc_lines))
            body = ["    " + l if l.strip() else "" for l in (body or ["pass"])]
            self._toggle_doc_comment_suppression(False)
            try:
                self.root.field_conv.mark_has_ctor()
            except Exception:
                pass
            return [sig] + body

        if t in ("Method", "MethodDeclaration", "Function"):
            static = self._is_static(node)
            params = self._collect_parameters(node)
            head = []
            if static:
                head.append("@staticmethod")
                if name == "main" and params:
                    param_sig = ", ".join([f"{p}=None" for p in params])
                else:
                    param_sig = ", ".join(params)
                sig = f"def {name}({param_sig}):" if param_sig else f"def {name}():"
            else:
                sig = f"def {name}(self{', ' + ', '.join(params) if params else ''}):"
            body = []
            doc_lines = self._maybe_doc(node)
            body.extend(doc_lines)
            if static and name == "main" and params:
                guard_var = params[0]
                body.append(f"if {guard_var} is None:")
                body.append(f"    {guard_var} = []")
            try:
                self.root.push_scope(params)
            except Exception:
                pass
            for ch in self._collect_body_children(node):
                body.extend(self.root.convert_node(ch))
            try:
                self.root.pop_scope()
            except Exception:
                pass
            self._toggle_doc_comment_suppression(bool(doc_lines))
            if static and self._uses_self(body):
                static = False
            if static:
                head = ["@staticmethod"]
                sig = f"def {name}({param_sig}):" if param_sig else f"def {name}():"
            else:
                head = []
                sig = f"def {name}(self{', ' + ', '.join(params) if params else ''}):"
            body = ["    " + l if l.strip() else "" for l in (body or ["pass"])]
            self._toggle_doc_comment_suppression(False)
            return head + [sig] + body

        return [f"# method: unhandled {t}"]
