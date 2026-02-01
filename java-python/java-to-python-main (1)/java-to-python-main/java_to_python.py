#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Java to Python Converter

This script converts Java code (via AST JSON) to Python code, addressing common conversion issues:
1. Syntax层面错误（self参数、关键字转换、方法定义格式）
2. 方法和函数调用错误（数学方法、集合方法、流操作）
3. 数据结构和类型错误（数组/列表、哈希表、集合类型）
4. Pythonic实践问题（类变量/实例变量、异常处理、构造函数调用）
5. 其他常见错误（UUID、日期时间、Lambda表达式）
"""

import json
import os
import sys

class JavaToPythonConverter:
    """Java to Python converter based on AST JSON"""
    
    def __init__(self):
        # 关键字映射
        self.keyword_mapping = {
            'this': 'self',
            'null': 'None',
            'true': 'True',
            'false': 'False',
            'System.out.println': 'print'
        }
        
        # 数学方法映射
        self.math_methods = {
            'Math.max': 'max',
            'Math.min': 'min',
            'Math.abs': 'abs',
            'Math.sqrt': 'math.sqrt',
            'Math.pow': 'math.pow',
            'Math.sin': 'math.sin',
            'Math.cos': 'math.cos',
            'Math.tan': 'math.tan',
            'Math.PI': 'math.pi',
            'Math.E': 'math.e'
        }
        
        # 集合方法映射
        self.collection_methods = {
            'contains': 'in',
            'containsAll': 'issubset',
            'addAll': 'update',
            'size': '__len__',
            'isEmpty': '__bool__',
            'get': '__getitem__',
            'set': '__setitem__'
        }
        
        # 类型映射
        self.type_mapping = {
            'int': 'int',
            'long': 'int',
            'float': 'float',
            'double': 'float',
            'boolean': 'bool',
            'char': 'str',
            'String': 'str',
            'List': 'list',
            'ArrayList': 'list',
            'LinkedList': 'list',
            'Set': 'set',
            'HashSet': 'set',
            'LinkedHashSet': 'set',
            'Map': 'dict',
            'HashMap': 'dict',
            'LinkedHashMap': 'dict'
        }
        
        # 需要导入的模块
        self.imports = set()
    
    def load_ast(self, ast_file):
        """Load AST from JSON file"""
        with open(ast_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def convert(self, ast_file, output_dir=None):
        """Convert Java AST to Python code"""
        # 加载AST
        ast = self.load_ast(ast_file)
        
        # 处理每个文件
        for file_node in ast.get('children', []):
            if file_node['type'] == 'File':
                file_name = file_node['name']
                python_file_name = file_name.replace('.java', '.py')
                
                # 生成Python代码
                python_code = self.convert_file(file_node)
                
                # 写入文件
                if output_dir:
                    os.makedirs(output_dir, exist_ok=True)
                    output_path = os.path.join(output_dir, python_file_name)
                else:
                    output_path = python_file_name
                
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(python_code)
                
                print(f"Converted {file_name} to {python_file_name}")
    
    def convert_file(self, file_node):
        """Convert a single file node"""
        code_parts = []
        
        # 处理导入
        imports = self.extract_imports(file_node)
        if imports:
            code_parts.extend(imports)
            code_parts.append('')
        
        # 处理文件内容
        for child in file_node.get('children', []):
            if child['type'] == 'CompilationUnit':
                code_parts.extend(self.convert_compilation_unit(child))
        
        return '\n'.join(code_parts)
    
    def extract_imports(self, file_node):
        """Extract and convert imports"""
        imports = []
        
        # 检查是否需要导入math模块
        if 'math' in self.imports:
            imports.append('import math')
        
        # 检查是否需要导入其他模块
        for imp in ['uuid', 'datetime']:
            if imp in self.imports:
                imports.append(f'import {imp}')
        
        return imports
    
    def convert_compilation_unit(self, cu_node):
        """Convert compilation unit"""
        code_parts = []
        
        for child in cu_node.get('children', []):
            if child['type'] == 'ClassOrInterfaceDeclaration':
                code_parts.extend(self.convert_class(child))
            elif child['type'] == 'ImportDeclaration':
                # 处理导入
                pass
        
        return code_parts
    
    def convert_class(self, class_node):
        """Convert class declaration"""
        code_parts = []
        
        # 获取类名
        class_name = class_node['name']
        
        # 构建类定义
        class_def = f'class {class_name}:'
        code_parts.append(class_def)
        
        # 处理类成员
        for child in class_node.get('children', []):
            if child['type'] == 'FieldDeclaration':
                code_parts.extend(self.convert_field(child))
            elif child['type'] == 'ConstructorDeclaration':
                code_parts.extend(self.convert_constructor(child))
            elif child['type'] == 'MethodDeclaration':
                code_parts.extend(self.convert_method(child))
        
        return code_parts
    
    def convert_field(self, field_node):
        """Convert field declaration"""
        code_parts = []
        
        # 获取修饰符
        modifiers = field_node.get('attrs', {}).get('modifiers', '[]')
        modifiers = modifiers.strip('[]').replace(' ', '').split(',')
        
        # 获取类型
        field_type = field_node.get('value', '')
        
        # 处理变量声明
        for child in field_node.get('children', []):
            if child['type'] == 'VariableDeclarator':
                var_name = child['name']
                initializer = child.get('attrs', {}).get('initializer', '')
                
                # 转换初始化器
                if initializer:
                    initializer = self.convert_expression(initializer)
                    code_parts.append(f'    {var_name} = {initializer}')
                else:
                    code_parts.append(f'    {var_name} = None')
        
        return code_parts
    
    def convert_constructor(self, constructor_node):
        """Convert constructor to __init__ method"""
        code_parts = []
        
        # 获取参数
        params = []
        for child in constructor_node.get('children', []):
            if child['type'] == 'Parameter':
                param_name = child['name']
                params.append(param_name)
        
        # 构建__init__方法
        params_str = ', '.join(['self'] + params)
        init_method = f'    def __init__({params_str}):'
        code_parts.append(init_method)
        
        # 处理方法体
        for child in constructor_node.get('children', []):
            if child['type'] == 'BlockStmt':
                code_parts.extend(self.convert_block(child))
        
        return code_parts
    
    def convert_method(self, method_node):
        """Convert method declaration"""
        code_parts = []
        
        # 获取方法名
        method_name = method_node['name']
        
        # 获取返回类型
        return_type = method_node.get('value', '')
        
        # 获取参数
        params = []
        for child in method_node.get('children', []):
            if child['type'] == 'Parameter':
                param_name = child['name']
                params.append(param_name)
        
        # 构建方法定义
        params_str = ', '.join(['self'] + params)
        method_def = f'    def {method_name}({params_str}):'
        code_parts.append(method_def)
        
        # 处理方法体
        for child in method_node.get('children', []):
            if child['type'] == 'BlockStmt':
                code_parts.extend(self.convert_block(child))
        
        return code_parts
    
    def convert_block(self, block_node):
        """Convert block statement"""
        code_parts = []
        
        for child in block_node.get('children', []):
            if child['type'] == 'ExpressionStmt':
                code_parts.extend(self.convert_expression_stmt(child))
            elif child['type'] == 'IfStmt':
                code_parts.extend(self.convert_if_stmt(child))
            elif child['type'] == 'ForStmt':
                code_parts.extend(self.convert_for_stmt(child))
            elif child['type'] == 'WhileStmt':
                code_parts.extend(self.convert_while_stmt(child))
            elif child['type'] == 'DoStmt':
                code_parts.extend(self.convert_do_stmt(child))
            elif child['type'] == 'TryStmt':
                code_parts.extend(self.convert_try_stmt(child))
            elif child['type'] == 'ReturnStmt':
                code_parts.extend(self.convert_return_stmt(child))
        
        return code_parts
    
    def convert_expression_stmt(self, expr_stmt_node):
        """Convert expression statement"""
        code_parts = []
        
        # 获取表达式
        expr = expr_stmt_node.get('attrs', {}).get('code', '')
        if expr:
            # 转换表达式
            converted_expr = self.convert_expression(expr)
            code_parts.append(f'        {converted_expr}')
        
        return code_parts
    
    def convert_if_stmt(self, if_stmt_node):
        """Convert if statement"""
        code_parts = []
        
        # 获取条件
        condition = if_stmt_node.get('attrs', {}).get('condition', '')
        converted_condition = self.convert_expression(condition)
        
        # 构建if语句
        if_stmt = f'        if {converted_condition}:'
        code_parts.append(if_stmt)
        
        # 处理then分支
        then_block = None
        else_block = None
        
        for child in if_stmt_node.get('children', []):
            if child['type'] == 'BlockStmt' and then_block is None:
                then_block = child
            elif child['type'] == 'BlockStmt' and then_block is not None:
                else_block = child
        
        if then_block:
            code_parts.extend(self.convert_block(then_block))
        
        if else_block:
            code_parts.append('        else:')
            code_parts.extend(self.convert_block(else_block))
        
        return code_parts
    
    def convert_for_stmt(self, for_stmt_node):
        """Convert for statement"""
        code_parts = []
        
        # 获取初始化、条件和更新
        init = for_stmt_node.get('attrs', {}).get('init', '[]')
        condition = for_stmt_node.get('attrs', {}).get('compare', '')
        update = for_stmt_node.get('attrs', {}).get('update', '[]')
        
        # 构建Python的for循环
        code_parts.append('        # For loop converted to while loop')
        code_parts.append(f'        {init}')
        code_parts.append(f'        while {condition}:')
        code_parts.append('            pass')
        code_parts.append(f'        {update}')
        
        # 处理循环体
        for child in for_stmt_node.get('children', []):
            if child['type'] == 'BlockStmt':
                code_parts.extend(self.convert_block(child))
        
        return code_parts
    
    def convert_while_stmt(self, while_stmt_node):
        """Convert while statement"""
        code_parts = []
        
        # 获取条件
        condition = while_stmt_node.get('attrs', {}).get('condition', '')
        converted_condition = self.convert_expression(condition)
        
        # 构建while语句
        while_stmt = f'        while {converted_condition}:'
        code_parts.append(while_stmt)
        
        # 处理循环体
        for child in while_stmt_node.get('children', []):
            if child['type'] == 'BlockStmt':
                code_parts.extend(self.convert_block(child))
        
        return code_parts
    
    def convert_do_stmt(self, do_stmt_node):
        """Convert do-while statement"""
        code_parts = []
        
        # 获取条件
        condition = do_stmt_node.get('attrs', {}).get('condition', '')
        converted_condition = self.convert_expression(condition)
        
        # 构建Python的while循环（模拟do-while）
        code_parts.append('        # Do-while loop converted to while loop')
        code_parts.append('        while True:')
        
        # 处理循环体
        for child in do_stmt_node.get('children', []):
            if child['type'] == 'BlockStmt':
                code_parts.extend(self.convert_block(child))
        
        # 添加条件检查
        code_parts.append(f'            if not ({converted_condition}):')
        code_parts.append('                break')
        
        return code_parts
    
    def convert_try_stmt(self, try_stmt_node):
        """Convert try statement"""
        code_parts = []
        
        # 构建try语句
        code_parts.append('        try:')
        
        # 处理try块
        for child in try_stmt_node.get('children', []):
            if child['type'] == 'BlockStmt':
                code_parts.extend(self.convert_block(child))
            elif child['type'] == 'CatchClause':
                # 处理catch块
                code_parts.append('        except Exception as e:')
                # 这里简化处理，实际需要更复杂的逻辑
                code_parts.append('            pass')
        
        return code_parts
    
    def convert_return_stmt(self, return_stmt_node):
        """Convert return statement"""
        code_parts = []
        
        # 获取返回表达式
        expr = return_stmt_node.get('attrs', {}).get('expr', '')
        if expr:
            converted_expr = self.convert_expression(expr)
            code_parts.append(f'        return {converted_expr}')
        else:
            code_parts.append('        return')
        
        return code_parts
    
    def convert_expression(self, expr):
        """Convert expression"""
        # 替换关键字
        for java_keyword, python_keyword in self.keyword_mapping.items():
            expr = expr.replace(java_keyword, python_keyword)
        
        # 替换数学方法
        for java_method, python_method in self.math_methods.items():
            if java_method in expr:
                expr = expr.replace(java_method, python_method)
                if 'math.' in python_method:
                    self.imports.add('math')
        
        # 替换集合方法
        for java_method, python_method in self.collection_methods.items():
            if java_method in expr:
                expr = expr.replace(java_method, python_method)
        
        # 替换类型
        for java_type, python_type in self.type_mapping.items():
            expr = expr.replace(f'new {java_type}', python_type)
        
        # 处理数组初始化
        expr = expr.replace('new int[', '[0] * ')
        expr = expr.replace('new String[', '[]')
        
        # 处理Lambda表达式
        if '->' in expr:
            # 转换Lambda表达式为Python lambda
            expr = expr.replace('->', ':')
            expr = 'lambda ' + expr
        
        # 处理流操作
        if 'stream()' in expr:
            # 简化处理流操作
            expr = expr.replace('.stream().forEach', 'for item in')
            expr = expr.replace('System.out::println', 'print(item)')
        
        return expr

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python java_to_python.py <ast_file> [output_dir]')
        sys.exit(1)
    
    ast_file = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None
    
    converter = JavaToPythonConverter()
    converter.convert(ast_file, output_dir)
