"""style.py 单元测试"""

import pytest
from reviewers.style import StyleReviewer


@pytest.fixture
def reviewer():
    return StyleReviewer()


class TestStyleReviewer:
    """StyleReviewer 测试集"""

    def test_detect_long_line(self, reviewer):
        """检测行过长"""
        code = 'x = ' + 'a' * 121  # 超过120字符
        findings = reviewer.review(code)
        assert any(f["type"] == "line_too_long" for f in findings)

    def test_detect_missing_function_docstring(self, reviewer):
        """检测函数缺少 docstring"""
        code = '''
def my_function():
    pass
'''
        findings = reviewer.review(code)
        assert any(f["type"] == "missing_docstring" for f in findings)

    def test_detect_missing_class_docstring(self, reviewer):
        """检测类缺少 docstring"""
        code = '''
class MyClass:
    def method(self):
        pass
'''
        findings = reviewer.review(code)
        assert any(f["type"] == "missing_docstring" for f in findings)

    def test_detect_bad_function_name(self, reviewer):
        """检测不规范的函数命名"""
        code = '''
def badFunctionName():
    """doc"""
    pass
'''
        findings = reviewer.review(code)
        naming = [f for f in findings if f["type"] == "naming_convention"]
        assert any("badFunctionName" in str(f) for f in naming)

    def test_detect_trailing_whitespace(self, reviewer):
        """检测尾随空格"""
        code = 'print("hello")   \n'
        findings = reviewer.review(code)
        assert any(f["type"] == "trailing_whitespace" for f in findings)

    def test_detect_unused_import(self, reviewer):
        """检测未使用的 import"""
        code = '''
import os
import sys

x = 1
'''
        findings = reviewer.review(code)
        unused = [f for f in findings if f["type"] == "unused_import"]
        assert len(unused) > 0

    def test_no_issues_on_good_code(self, reviewer):
        """良好代码不应产生问题"""
        code = '''
"""模块文档字符串"""


def calculate_sum(a: int, b: int) -> int:
    """计算两个数的和"""
    return a + b


class MathOperations:
    """数学操作类"""

    @staticmethod
    def multiply(x: int, y: int) -> int:
        """乘法运算"""
        return x * y
'''
        findings = reviewer.review(code)
        # 良好代码不应有 docstring 或命名问题
        critical = [f for f in findings if f["type"] in ("missing_docstring", "naming_convention")]
        assert len(critical) == 0
