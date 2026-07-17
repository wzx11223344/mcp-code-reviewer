"""
代码风格检查器 (Style Reviewer)

检查项:
- 行过长 (>120 字符)
- 函数/类缺少 docstring
- 变量命名不符合规范
- 魔法数字
- 多余的 import
- 尾随空格
"""

import ast
import re
from typing import Dict, List, Set


class StyleReviewer:
    """代码风格检查器"""

    MAX_LINE_LENGTH = 120

    # 命名规范检测
    SNAKE_CASE_RE = re.compile(r'^[a-z][a-z0-9_]*$')
    CAMEL_CASE_RE = re.compile(r'^[a-z][a-zA-Z0-9]*$')
    CONSTANT_RE = re.compile(r'^[A-Z][A-Z0-9_]*$')
    CLASS_NAME_RE = re.compile(r'^[A-Z][a-zA-Z0-9]*$')

    # 常见魔法数字（排除常见值）
    MAGIC_NUMBERS = {0, 1, -1, 0.0, 1.0, -1.0, 100, 60, 24, 7, 365}

    def __init__(self, language: str = "python"):
        self.language = language.lower()
        self.findings: List[Dict] = []
        self.imported_names: Set[str] = set()
        self.used_names_in_scope: Set[str] = set()

    def review(self, code: str) -> List[Dict]:
        """执行代码风格检查，返回发现列表"""
        self.findings = []

        # 行级检查
        self._check_line_length(code)
        self._check_trailing_whitespace(code)

        try:
            tree = ast.parse(code)
            self._check_docstrings(tree)
            self._check_naming(tree)
            self._check_magic_numbers(tree)
            self._check_unused_imports(tree)
        except SyntaxError:
            # AST 检查失败时，行级检查仍在
            pass

        return self.findings

    def _check_line_length(self, code: str):
        """检查行过长"""
        lines = code.split("\n")
        for i, line in enumerate(lines, 1):
            if len(line) > self.MAX_LINE_LENGTH:
                self.findings.append({
                    "type": "line_too_long",
                    "severity": "warning",
                    "line": i,
                    "message": f"行过长 ({len(line)} > {self.MAX_LINE_LENGTH} 字符)",
                    "suggestion": "将长行拆分为多行，或使用括号隐式换行。",
                })

    def _check_trailing_whitespace(self, code: str):
        """检查尾随空格"""
        lines = code.split("\n")
        for i, line in enumerate(lines, 1):
            if line != line.rstrip() and line.strip():
                self.findings.append({
                    "type": "trailing_whitespace",
                    "severity": "info",
                    "line": i,
                    "message": "行尾存在多余空格",
                    "suggestion": "删除行尾空格。",
                })

    def _check_docstrings(self, tree: ast.AST):
        """检查组和函数缺少 docstring"""
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("__") and node.name.endswith("__"):
                    continue  # 魔术方法可以没有 docstring
                if not ast.get_docstring(node):
                    self.findings.append({
                        "type": "missing_docstring",
                        "severity": "warning",
                        "line": node.lineno,
                        "message": f"函数 '{node.name}' 缺少 docstring",
                        "suggestion": "为函数添加文档字符串，说明功能、参数和返回值。",
                    })
            elif isinstance(node, ast.ClassDef):
                if not ast.get_docstring(node):
                    self.findings.append({
                        "type": "missing_docstring",
                        "severity": "warning",
                        "line": node.lineno,
                        "message": f"类 '{node.name}' 缺少 docstring",
                        "suggestion": "为类添加文档字符串，说明类的功能和用法。",
                    })
            elif isinstance(node, ast.Module):
                if not ast.get_docstring(node):
                    self.findings.append({
                        "type": "missing_module_docstring",
                        "severity": "info",
                        "line": 1,
                        "message": "模块缺少 docstring",
                        "suggestion": "在文件开头添加模块级别的文档字符串。",
                    })

    def _check_naming(self, tree: ast.AST):
        """检查命名规范"""
        for node in ast.walk(tree):
            # 函数和变量名: snake_case
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = node.name
                if name.startswith("__") and name.endswith("__"):
                    continue
                if not self.SNAKE_CASE_RE.match(name) and not self.CONSTANT_RE.match(name):
                    self.findings.append({
                        "type": "naming_convention",
                        "severity": "warning",
                        "line": node.lineno,
                        "message": f"函数名 '{name}' 不符合 snake_case 命名规范",
                        "suggestion": f"建议重命名为 '{self._to_snake_case(name)}'",
                    })

            # 类名: PascalCase
            elif isinstance(node, ast.ClassDef):
                name = node.name
                if not self.CLASS_NAME_RE.match(name):
                    self.findings.append({
                        "type": "naming_convention",
                        "severity": "warning",
                        "line": node.lineno,
                        "message": f"类名 '{name}' 不符合 PascalCase 命名规范",
                        "suggestion": f"建议重命名为 '{name.capitalize()}'",
                    })

            # 变量名: snake_case
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        name = target.id
                        if name.startswith("_"):
                            continue
                        if not self.SNAKE_CASE_RE.match(name) and not self.CONSTANT_RE.match(name):
                            self.findings.append({
                                "type": "naming_convention",
                                "severity": "info",
                                "line": node.lineno,
                                "message": f"变量名 '{name}' 不符合 snake_case 命名规范",
                                "suggestion": f"建议重命名为 '{self._to_snake_case(name)}'",
                            })

    def _check_magic_numbers(self, tree: ast.AST):
        """检查魔法数字"""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for child in ast.walk(node):
                    if isinstance(child, ast.Constant) and isinstance(child.value, (int, float)):
                        if child.value not in self.MAGIC_NUMBERS:
                            # 确保在函数体内，并且不是默认参数值
                            parent = getattr(child, "parent", None)
                            self.findings.append({
                                "type": "magic_number",
                                "severity": "info",
                                "line": child.lineno,
                                "message": f"魔法数字: {child.value}",
                                "suggestion": f"将 {child.value} 定义为命名常量。",
                            })

    def _check_unused_imports(self, tree: ast.AST):
        """检查未使用的 import"""
        imported = {}
        used = set()

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                # 收集 import
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        name = alias.asname or alias.name
                        imported[name] = node.lineno
                else:  # ImportFrom
                    for alias in node.names:
                        name = alias.asname or alias.name
                        imported[name] = node.lineno

        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                used.add(node.id)
            elif isinstance(node, ast.Attribute):
                if isinstance(node.value, ast.Name):
                    used.add(node.value.id)

        for name, line in imported.items():
            base_name = name.split(".")[0]
            if base_name not in used:
                self.findings.append({
                    "type": "unused_import",
                    "severity": "warning",
                    "line": line,
                    "message": f"未使用的 import: '{name}'",
                    "suggestion": f"删除 import '{name}'。",
                })

    @staticmethod
    def _to_snake_case(name: str) -> str:
        """将 camelCase 或 PascalCase 转换为 snake_case"""
        s1 = re.sub(r'(.)([A-Z][a-z]+)', r'\1_\2', name)
        return re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


# 便捷函数
def check_style(code: str, language: str = "python") -> List[Dict]:
    """快速代码风格检查"""
    return StyleReviewer(language).review(code)
