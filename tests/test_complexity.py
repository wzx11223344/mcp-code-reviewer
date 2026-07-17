"""complexity.py 单元测试"""

import pytest
from reviewers.complexity import ComplexityAnalyzer


@pytest.fixture
def analyzer():
    return ComplexityAnalyzer()


class TestComplexityAnalyzer:
    """ComplexityAnalyzer 测试集"""

    def test_simple_function_low_complexity(self, analyzer):
        """简单函数复杂度应低"""
        code = '''
def add(a: int, b: int) -> int:
    """加法"""
    return a + b
'''
        findings = analyzer.review(code)
        complex_findings = [f for f in findings if f["type"] == "high_complexity"]
        assert len(complex_findings) == 0

    def test_complex_function_high_complexity(self, analyzer):
        """多分支函数应检测到高复杂度"""
        code = '''
def complex_logic(x: int, y: int, z: int, flag: bool) -> int:
    """复杂逻辑"""
    result = 0
    if x > 0 and y > 0:
        if z > 0 or flag:
            result = x + y + z
        elif x > 5:
            result = x + y
        elif y > 5:
            result = y + z
        else:
            result = x
    elif y > 0:
        if z > 0:
            result = y + z
        elif x > 0:
            result = z
        else:
            result = y
    elif z > 0:
        if flag:
            result = x + y + z
        else:
            result = 0
    elif flag:
        result = 1
    else:
        result = -1

    for i in range(x):
        for j in range(y):
            result += i * j

    while result < 100:
        result *= 2

    try:
        result = result // z
    except ZeroDivisionError:
        result = 0

    assert result >= 0
    return result
'''
        findings = analyzer.review(code)
        complex_findings = [f for f in findings if f["type"] == "high_complexity"]
        assert len(complex_findings) > 0

    def test_long_function_detection(self, analyzer):
        """检测过长函数"""
        lines = ['    """doc"""']
        for i in range(65):
            lines.append(f'    x{i} = {i}')
        code = 'def long_func():\n' + '\n'.join(lines)
        findings = analyzer.review(code)
        long_func = [f for f in findings if f["type"] == "function_too_long"]
        assert len(long_func) > 0

    def test_deep_nesting_detection(self, analyzer):
        """检测深层嵌套"""
        code = '''
def deeply_nested(data: list) -> str:
    """深层嵌套"""
    result = ""
    for item in data:
        if item > 0:
            for sub in range(item):
                if sub % 2 == 0:
                    with open("test.txt") as f:
                        content = f.read()
                        if content:
                            result += content
    return result
'''
        findings = analyzer.review(code)
        nesting = [f for f in findings if f["type"] == "deep_nesting"]
        assert len(nesting) > 0

    def test_too_many_parameters(self, analyzer):
        """检测参数过多"""
        code = '''
def too_many_params(a, b, c, d, e, f, g, h, i):
    """参数过多"""
    return a + b + c + d + e + f + g + h + i
'''
        findings = analyzer.review(code)
        param_findings = [f for f in findings if f["type"] == "too_many_parameters"]
        assert len(param_findings) > 0

    def test_syntax_error_handling(self, analyzer):
        """语法错误应优雅处理"""
        code = 'def broken_function(:\n    pass\n'
        findings = analyzer.review(code)
        error_findings = [f for f in findings if f["type"] == "analysis_error"]
        assert len(error_findings) > 0
