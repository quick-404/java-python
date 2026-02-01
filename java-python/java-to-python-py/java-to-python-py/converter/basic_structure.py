from typing import List
from converter.util import children  # ✅ 改为从 util 导入，避免循环导入

class ProjectConverter:
    """Project / CompilationUnit 入口：扁平递归"""
    def __init__(self, root):
        self.root = root

    def convert(self, node) -> List[str]:
        lines = []
        for ch in children(node):
            lines.extend(self.root.convert_node(ch))
        return lines

class FileConverter:
    """File 节点：输出文件头注释然后处理子节点"""
    def __init__(self, root):
        self.root = root

    def convert(self, node) -> List[str]:
        name = node.get("name", "<file>")
        lines = [f"# --- File: {name} ---", ""]
        for ch in children(node):
            lines.extend(self.root.convert_node(ch))
        lines.append("")
        return lines

class PackageConverter:
    """package -> 注释行"""
    def convert(self, node) -> List[str]:
        return [f"# package: {node.get('name','')}", ""]

class ImportConverter:
    """import -> 注释行（不直接引入 Java 包）"""
    def convert(self, node) -> List[str]:
        name = node.get("name", "")
        return [f"# import: {name}", ""]
