#!/usr/bin/env python3
# python_ast_generator.py

import os
import ast
import json
import sys
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

# 兼容 ast.unparse
try:
    from ast import unparse
except ImportError:
    import astunparse
    unparse = astunparse.unparse

@dataclass
class ASTNode:
    type: str
    name: Optional[str] = None
    lineno: int = -1
    col_offset: int = -1
    children: List[Any] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "type": self.type,
            "name": self.name,
            "lineno": self.lineno,
            "col_offset": self.col_offset,
            "children": [child.to_dict() for child in self.children]
        }

class ExtendedASTVisitor(ast.NodeVisitor):
    def __init__(self):
        self.root: Optional[ASTNode] = None
        self.current: Optional[ASTNode] = None

    def generic_visit(self, node):
        node_name = getattr(node, 'name', None) or getattr(node, 'id', None) or type(node).__name__
        ast_node = ASTNode(
            type=type(node).__name__,
            name=str(node_name),
            lineno=getattr(node, 'lineno', -1),
            col_offset=getattr(node, 'col_offset', -1)
        )
        if self.root is None:
            self.root = ast_node
            self.current = ast_node
        else:
            self.current.children.append(ast_node)
        parent = self.current
        self.current = ast_node
        super().generic_visit(node)
        self.current = parent

    # 你已有的各种 visit_xxx() 不变，这里省略
    # 重点：把 ast.unparse 改为 unparse()
    def visit_Assign(self, node: ast.Assign):
        targets = [unparse(t).strip() for t in node.targets]
        ast_node = ASTNode("Assign", name=",".join(targets), lineno=node.lineno, col_offset=node.col_offset)
        self.current.children.append(ast_node)
        self.visit(node.value)

    def visit_Expr(self, node: ast.Expr):
        ast_node = ASTNode("Expr", name=unparse(node.value).strip(), lineno=node.lineno)
        self.current.children.append(ast_node)

    def visit_AugAssign(self, node: ast.AugAssign):
        target = unparse(node.target).strip()
        op = type(node.op).__name__
        ast_node = ASTNode("AugAssign", name=f"{target}{op}", lineno=node.lineno)
        self.current.children.append(ast_node)
        self.visit(node.value)

    # ... 其他visit方法一样

def parse_file(path: str) -> ASTNode:
    with open(path, 'r', encoding='utf-8') as f:
        source = f.read()
    tree = ast.parse(source, filename=path)
    visitor = ExtendedASTVisitor()
    visitor.visit(tree)
    return visitor.root

def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <path-to-python-file-or-dir>")
        sys.exit(1)

    target = sys.argv[1]
    os.makedirs("../output", exist_ok=True)

    if os.path.isdir(target):
        all_asts: List[Dict] = []
        for root, _, files in os.walk(target):
            for file in files:
                if file.endswith(".py"):
                    path = os.path.join(root, file)
                    node = parse_file(path)
                    all_asts.append(node.to_dict())
        with open("output/all_python_ast.json", "w", encoding="utf-8") as f:
            json.dump(all_asts, f, indent=2, ensure_ascii=False)
        print("✅ Generated AST for directory")
    elif os.path.isfile(target) and target.endswith(".py"):
        node = parse_file(target)
        with open("../output/python_ast.json", "w", encoding="utf-8") as f:
            json.dump(node.to_dict(), f, indent=2, ensure_ascii=False)
        print("✅ Generated AST for single file")
    else:
        print("Error: Not a .py file or directory.")
        sys.exit(1)

if __name__ == "__main__":
    main()
