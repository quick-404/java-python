import ast
import json
from typing import Any, Dict

# 示例代码包含多种语法结构
SAMPLE_CODE = """
import sys
from typing import List

@debug_logger
def fibonacci(n: int) -> List[int]:
    result = []
    a, b = 0, 1
    for _ in range(n):
        if a % 2 == 0:
            result.append(a)
        a, b = b, a + b
    return result

class MathOperations:
    PI = 3.1415926

    @classmethod
    def circle_area(cls, r: float) -> float:
        return cls.PI * r ** 2
"""


def ast_to_dict(node: ast.AST) -> Dict[str, Any]:
    """递归将AST节点转换为字典"""
    if not isinstance(node, ast.AST):
        if isinstance(node, list):
            return [ast_to_dict(item) for item in node]
        return node

    node_dict = {
        '_type': node.__class__.__name__,
        **{
            attr: ast_to_dict(getattr(node, attr))
            for attr in node._fields
        }
    }

    # 添加行号信息
    if hasattr(node, 'lineno'):
        node_dict['lineno'] = node.lineno
    if hasattr(node, 'col_offset'):
        node_dict['col_offset'] = node.col_offset

    return node_dict


def main():
    # 生成AST
    tree = ast.parse(SAMPLE_CODE)

    # 转换为字典结构
    ast_dict = ast_to_dict(tree)

    # 保存为JSON文件
    with open('python_ast.json', 'w', encoding='utf-8') as f:
        json.dump(ast_dict, f, indent=2, ensure_ascii=False)

    print("AST已保存为python_ast.json")


if __name__ == "__main__":
    main()