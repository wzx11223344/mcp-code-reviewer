"""
复杂度分析器 (Complexity Analyzer)

指标:
- 圈复杂度 (McCabe): if/for/while/and/or/case/except 计数
- 函数长度 (行数)
- 嵌套深度
- 参数数量
- 返回语句数量
"""

import ast
from typing import Dict, List


class ComplexityAnalyzer:
    """复杂度分析器"""

    # 圈复杂度阈值
    COMPLEXITY_WARN = 10
    COMPLEXITY_ERROR = 20

    # 函数长度阈值
    FUNC_LENGTH_WARN = 30
    FUNC_LENGTH_ERROR = 60

    # 嵌套深度阈值
    NESTING_WARN = 3
    NESTING_ERROR = 5

    # 参数数量阈值
    PARAM_WARN = 5
    PARAM_ERROR = 8

    def __init__(self):
        self.findings: List[Dict] = []

    def review(self, code: str) -> List[Dict]:
        """执行复杂度分析，返回发现列表"""
        self.findings = []

        try:
            tree = ast.parse(code)
            self._analyze_functions(tree)
        except SyntaxError as e:
            self.findings.append({
                "type": "analysis_error",
                "severity": "error",
                "line": e.lineno or 0,
                "message": f"无法分析: 语法错误 - {e.msg}",
                "suggestion": "修正语法错误后重试分析。",
            })

        return self.findings

    def _analyze_functions(self, tree: ast.AST):
        """分析所有函数的复杂度"""
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._analyze_single_function(node)

    def _analyze_single_function(self, node: ast.FunctionDef):
        """分析单个函数的各项复杂度指标"""
        func_name = node.name
        func_lines = node.end_lineno - node.lineno + 1 if node.end_lineno else 0

        # 1. 圈复杂度
        cyclomatic = self._calc_cyclomatic_complexity(node)

        # 2. 函数长度
        if func_lines >= self.FUNC_LENGTH_ERROR:
            severity = "error"
        elif func_lines >= self.FUNC_LENGTH_WARN:
            severity = "warning"
        else:
            severity = None

        if severity:
            self.findings.append({
                "type": "function_too_long",
                "severity": severity,
                "line": node.lineno,
                "message": f"函数 '{func_name}' 过长 ({func_lines} 行)",
                "suggestion": f"将函数拆分为多个小函数，每个不超过 {self.FUNC_LENGTH_WARN} 行。",
                "metric": {"name": "function_length", "value": func_lines},
            })

        # 3. 圈复杂度评分
        if cyclomatic >= self.COMPLEXITY_ERROR:
            severity = "error"
            suggestion = "强烈建议重构此函数。"
        elif cyclomatic >= self.COMPLEXITY_WARN:
            severity = "warning"
            suggestion = "建议简化此函数的逻辑。"
        else:
            severity = None
            suggestion = None

        if severity:
            rating = "高" if cyclomatic >= self.COMPLEXITY_ERROR else "中"
            self.findings.append({
                "type": "high_complexity",
                "severity": severity,
                "line": node.lineno,
                "message": f"函数 '{func_name}' 圈复杂度 {cyclomatic} ({rating})",
                "suggestion": f"{suggestion} 提取条件分支为独立函数。",
                "metric": {"name": "cyclomatic_complexity", "value": cyclomatic},
            })

        # 4. 嵌套深度
        max_depth = self._calc_max_nesting(node)
        if max_depth >= self.NESTING_ERROR:
            severity = "error"
        elif max_depth >= self.NESTING_WARN:
            severity = "warning"
        else:
            severity = None

        if severity:
            self.findings.append({
                "type": "deep_nesting",
                "severity": severity,
                "line": node.lineno,
                "message": f"函数 '{func_name}' 最大嵌套深度 {max_depth}",
                "suggestion": "使用提前返回 (early return) 或提取内层逻辑为独立函数。",
                "metric": {"name": "nesting_depth", "value": max_depth},
            })

        # 5. 参数数量
        param_count = len(node.args.args)
        if param_count >= self.PARAM_ERROR:
            severity = "error"
        elif param_count >= self.PARAM_WARN:
            severity = "warning"
        else:
            severity = None

        if severity:
            self.findings.append({
                "type": "too_many_parameters",
                "severity": severity,
                "line": node.lineno,
                "message": f"函数 '{func_name}' 参数过多 ({param_count} 个)",
                "suggestion": "将参数封装为数据类或使用 **kwargs。",
                "metric": {"name": "parameter_count", "value": param_count},
            })

        # 6. 返回语句数量
        return_count = self._count_returns(node)
        if return_count > 3:
            self.findings.append({
                "type": "too_many_returns",
                "severity": "info",
                "line": node.lineno,
                "message": f"函数 '{func_name}' 有 {return_count} 个返回语句",
                "suggestion": "多个返回点可能导致逻辑混乱，考虑合并。",
                "metric": {"name": "return_count", "value": return_count},
            })

    def _calc_cyclomatic_complexity(self, node: ast.AST) -> int:
        """计算圈复杂度 (McCabe)"""
        complexity = 1  # 基准为 1

        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.AsyncFor)):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                # and/or 每个操作数增加复杂度
                complexity += len(child.values) - 1
            elif isinstance(child, ast.ExceptHandler):
                complexity += 1
            elif isinstance(child, ast.Try):
                complexity += 1
            elif isinstance(child, ast.Assert):
                complexity += 1

        return complexity

    def _calc_max_nesting(self, node: ast.AST) -> int:
        """计算最大嵌套深度"""
        max_depth = 0
        current_depth = 0

        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.For, ast.AsyncFor, ast.While,
                                  ast.Try, ast.ExceptHandler, ast.With, ast.AsyncWith)):
                current_depth = self._get_nesting_depth(child, node)
                max_depth = max(max_depth, current_depth)

        return max_depth

    def _get_nesting_depth(self, target: ast.AST, root: ast.AST) -> int:
        """计算目标节点在根节点中的嵌套深度"""
        depth = 0
        parent_map = {child: parent for parent in ast.walk(root) for child in ast.iter_child_nodes(parent)}

        current = target
        while current in parent_map:
            parent = parent_map[current]
            if isinstance(parent, (ast.If, ast.For, ast.AsyncFor, ast.While,
                                   ast.Try, ast.ExceptHandler, ast.With, ast.AsyncWith)):
                depth += 1
            current = parent

        return depth

    def _count_returns(self, node: ast.AST) -> int:
        """统计函数中的 return 语句数量"""
        count = 0
        for child in ast.walk(node):
            if isinstance(child, ast.Return):
                count += 1
        return count


# 便捷函数
def analyze_complexity(code: str) -> List[Dict]:
    """快速复杂度分析"""
    return ComplexityAnalyzer().review(code)
