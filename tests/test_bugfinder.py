"""bugfinder.py 单元测试"""

import pytest
from reviewers.bugfinder import BugFinder


@pytest.fixture
def finder():
    return BugFinder()


class TestBugFinder:
    """BugFinder 测试集"""

    def test_mutable_default_arg_list(self, finder):
        """检测可变默认参数 (列表)"""
        code = '''
def process(items=[]):
    items.append("new")
    return items
'''
        findings = finder.review(code)
        assert any(f["type"] == "mutable_default_arg" for f in findings)

    def test_mutable_default_arg_dict(self, finder):
        """检测可变默认参数 (字典)"""
        code = '''
def update(data={}):
    data["key"] = "value"
    return data
'''
        findings = finder.review(code)
        assert any(f["type"] == "mutable_default_arg" for f in findings)

    def test_division_by_zero_literal(self, finder):
        """检测直接除零"""
        code = 'result = 10 / 0'
        findings = finder.review(code)
        assert any(f["type"] == "division_by_zero" for f in findings)

    def test_bare_except(self, finder):
        """检测裸露的 except"""
        code = '''
try:
    result = do_something()
except:
    pass
'''
        findings = finder.review(code)
        assert any(f["type"] == "bare_except" for f in findings)

    def test_modify_while_iterating(self, finder):
        """检测循环中修改列表"""
        code = '''
for item in my_list:
    if item < 0:
        my_list.remove(item)
'''
        findings = finder.review(code)
        assert any(f["type"] == "modify_while_iterating" for f in findings)

    def test_type_mismatch_str_int(self, finder):
        """检测 str + int 类型不匹配"""
        code = 'result = "Count: " + 42'
        findings = finder.review(code)
        assert any(f["type"] == "type_mismatch" for f in findings)

    def test_no_false_positive_on_good_code(self, finder):
        """良好代码不应产生误报"""
        code = '''
"""安全代码"""

from typing import Optional


def safe_process(items: Optional[list] = None) -> list:
    """安全处理"""
    if items is None:
        items = []
    result = []
    for item in items:
        if item > 0:
            result.append(item)
    return result


def safe_divide(a: float, b: float) -> float:
    """安全除法"""
    if b == 0:
        raise ValueError("除数不能为 0")
    return a / b
'''
        findings = finder.review(code)
        error_findings = [f for f in findings if f["severity"] == "error"]
        assert len(error_findings) == 0
