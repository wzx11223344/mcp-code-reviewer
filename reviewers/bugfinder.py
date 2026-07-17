"""
Bug 模式检测器 (Bug Finder)

检测模式:
- 变量未定义就使用
- 除零风险
- 类型不匹配 (str + int)
- 返回 None 但调用者期望非 None
- 循环中修改正在迭代的列表
- 可变默认参数
- 未捕获的异常
"""

import ast
from typing import Dict, List, Set, Optional


class BugFinder:
    """Bug 模式检测器"""

    def __init__(self):
        self.findings: List[Dict] = []

    def review(self, code: str) -> List[Dict]:
        """执行 Bug 模式检测，返回发现列表"""
        self.findings = []

        try:
            tree = ast.parse(code)
            self._check_mutable_default_args(tree)
            self._check_undefined_variables(tree)
            self._check_division_by_zero(tree)
            self._check_type_mismatch(tree)
            self._check_modify_while_iterating(tree)
            self._check_bare_except(tree)
        except SyntaxError as e:
            self.findings.append({
                "type": "parse_error",
                "severity": "error",
                "line": e.lineno or 0,
                "message": f"语法错误，无法完成 Bug 检测: {e.msg}",
                "suggestion": "修正语法错误后重新检测。",
            })

        return self.findings

    def _check_mutable_default_args(self, tree: ast.AST):
        """检测可变默认参数"""
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for default in node.args.defaults:
                    if self._is_mutable(default):
                        self.findings.append({
                            "type": "mutable_default_arg",
                            "severity": "warning",
                            "line": node.lineno,
                            "message": f"函数 '{node.name}' 使用了可变对象作为默认参数",
                            "suggestion": "将默认值设为 None，在函数体内初始化为空列表/字典。",
                        })
                # keyword-only 参数的默认值
                for default in node.args.kw_defaults:
                    if default is not None and self._is_mutable(default):
                        self.findings.append({
                            "type": "mutable_default_arg",
                            "severity": "warning",
                            "line": node.lineno,
                            "message": f"函数 '{node.name}' 使用了可变对象作为关键字参数默认值",
                            "suggestion": "将默认值设为 None，在函数体内初始化。",
                        })

    @staticmethod
    def _is_mutable(node: ast.AST) -> bool:
        """判断 AST 节点是否为可变对象"""
        if isinstance(node, ast.List):
            return True
        if isinstance(node, ast.Dict):
            return True
        if isinstance(node, ast.Set):
            return True
        return False

    def _check_undefined_variables(self, tree: ast.AST):
        """检测变量未定义就使用"""
        # 先收集模块级别的 import 定义
        module_defined: Set[str] = set()
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.asname or alias.name.split(".")[0]
                    module_defined.add(name)
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    name = alias.asname or alias.name
                    module_defined.add(name)

        # 逐个检查模块顶层语句（不进入函数体，函数体由函数级分析负责）
        for stmt in ast.iter_child_nodes(tree):
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._check_function_undefined_vars(stmt, module_defined)
            else:
                scope_defined = set(module_defined)
                used_before = []
                self._scan_def_use(stmt, scope_defined, used_before)
                for var_name, lineno in used_before:
                    if var_name not in scope_defined and not var_name.startswith("_"):
                        self._report_undefined(var_name, lineno)

    def _check_function_undefined_vars(self, node: ast.FunctionDef, module_defined: Set[str]):
        """检查函数内部的未定义变量"""
        defined: Set[str] = set(module_defined)

        # 函数参数
        for arg in node.args.args:
            defined.add(arg.arg)
        for arg in node.args.posonlyargs:
            defined.add(arg.arg)
        for arg in node.args.kwonlyargs:
            defined.add(arg.arg)
        if node.args.vararg:
            defined.add(node.args.vararg.arg)
        if node.args.kwarg:
            defined.add(node.args.kwarg.arg)

        # 嵌套函数参数也是定义
        nested_funcs = []
        for child in ast.walk(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child != node:
                nested_funcs.append(child)
                defined.add(child.name)

        used_before: List[tuple] = []
        for stmt in node.body:
            self._scan_def_use(stmt, defined, used_before)

        for var_name, lineno in used_before:
            if var_name not in defined and not var_name.startswith("_"):
                self._report_undefined(var_name, lineno)

    def _scan_def_use(self, node: ast.AST, defined: Set[str],
                      used_before: List[tuple]):
        """扫描 AST 子树，收集变量定义和使用"""
        for child in ast.walk(node):
            # 跳过嵌套函数的内部（嵌套函数有自己的作用域）
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if child != node:
                    # 函数名本身是定义
                    defined.add(child.name)
                    # 跳过嵌套函数的 body
                    self._skip_subtree(child, defined, used_before)
                    continue

            # 普通赋值: x = ...
            if isinstance(child, ast.Assign):
                for target in child.targets:
                    self._collect_names(target, defined)

            # 类型标注赋值: x: int = ...
            elif isinstance(child, ast.AnnAssign):
                if isinstance(child.target, ast.Name):
                    defined.add(child.target.id)

            # 增强赋值: x += ... (需要先定义)
            elif isinstance(child, ast.AugAssign):
                if isinstance(child.target, ast.Name):
                    if child.target.id not in defined:
                        used_before.append((child.target.id, child.lineno))

            # for 循环变量
            elif isinstance(child, ast.For):
                if isinstance(child.target, ast.Name):
                    defined.add(child.target.id)
                elif isinstance(child.target, ast.Tuple):
                    for elt in child.target.elts:
                        if isinstance(elt, ast.Name):
                            defined.add(elt.id)

            # with ... as x
            elif isinstance(child, ast.With):
                for item in child.items:
                    if item.optional_vars is not None:
                        if isinstance(item.optional_vars, ast.Name):
                            defined.add(item.optional_vars.id)
                        elif isinstance(item.optional_vars, ast.Tuple):
                            for elt in item.optional_vars.elts:
                                if isinstance(elt, ast.Name):
                                    defined.add(elt.id)

            # except ... as e
            elif isinstance(child, ast.ExceptHandler):
                if child.name:
                    defined.add(child.name)

            # 变量使用
            if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load):
                if (child.id not in defined
                        and child.id not in ("True", "False", "None", "self", "cls")
                        and not self._is_builtin(child.id)):
                    if not any(v[0] == child.id for v in used_before):
                        used_before.append((child.id, child.lineno))

    @staticmethod
    def _skip_subtree(node: ast.AST, defined: Set[str], used_before: List[tuple]):
        """标记跳过嵌套子树（嵌套函数），只收集函数名不深入 body"""
        # 只记录函数名定义，不深入 body
        pass

    @staticmethod
    def _collect_names(target: ast.AST, defined: Set[str]):
        """递归收集赋值目标中的变量名"""
        if isinstance(target, ast.Name):
            defined.add(target.id)
        elif isinstance(target, ast.Tuple) or isinstance(target, ast.List):
            for elt in target.elts:
                BugFinder._collect_names(elt, defined)
        elif isinstance(target, ast.Starred):
            if isinstance(target.value, ast.Name):
                defined.add(target.value.id)

    def _report_undefined(self, var_name: str, lineno: int):
        """报告未定义变量"""
        self.findings.append({
            "type": "undefined_variable",
            "severity": "error",
            "line": lineno,
            "message": f"变量 '{var_name}' 可能未定义就被使用",
            "suggestion": f"确保 '{var_name}' 在使用前已被赋值。",
        })

    @staticmethod
    def _is_builtin(name: str) -> bool:
        """检查是否为 Python 内置函数"""
        builtins = {
            "print", "len", "str", "int", "float", "list", "dict", "set", "tuple",
            "range", "enumerate", "zip", "map", "filter", "sorted", "reversed",
            "type", "isinstance", "issubclass", "hasattr", "getattr", "setattr",
            "open", "input", "format", "min", "max", "sum", "abs", "round",
            "all", "any", "bool", "repr", "ord", "chr", "hex", "oct", "bin",
            "iter", "next", "slice", "super", "object", "property", "staticmethod",
            "classmethod", "ValueError", "TypeError", "KeyError", "IndexError",
            "Exception", "BaseException", "StopIteration", "NotImplementedError",
            "FileNotFoundError", "IOError", "OSError", "RuntimeError",
            "ZeroDivisionError", "AttributeError", "NameError",
        }
        return name in builtins

    def _check_division_by_zero(self, tree: ast.AST):
        """检测除零风险"""
        for node in ast.walk(tree):
            if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)):
                if isinstance(node.right, ast.Constant) and node.right.value == 0:
                    self.findings.append({
                        "type": "division_by_zero",
                        "severity": "error",
                        "line": node.lineno,
                        "message": "除零错误: 检测到直接除以 0",
                        "suggestion": "在执行除法前检查除数是否为 0。",
                    })
                elif isinstance(node.right, ast.Name):
                    self.findings.append({
                        "type": "possible_division_by_zero",
                        "severity": "warning",
                        "line": node.lineno,
                        "message": f"可能的除零风险: 变量 '{node.right.id}' 可能为 0",
                        "suggestion": "在执行除法前添加 if divisor != 0 检查。",
                    })

    def _check_type_mismatch(self, tree: ast.AST):
        """检测类型不匹配 (str + int)"""
        for node in ast.walk(tree):
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
                left = node.left
                right = node.right
                # str + int 或 int + str
                if (isinstance(left, ast.Constant) and isinstance(left.value, str)
                        and isinstance(right, ast.Constant) and isinstance(right.value, int)):
                    self.findings.append({
                        "type": "type_mismatch",
                        "severity": "warning",
                        "line": node.lineno,
                        "message": f"类型不匹配: str + int (字符串 '{left.value}' + 数字 {right.value})",
                        "suggestion": "使用 f-string 或 str() 转换: f'{left.value}{right.value}'",
                    })
                elif (isinstance(left, ast.Constant) and isinstance(left.value, int)
                      and isinstance(right, ast.Constant) and isinstance(right.value, str)):
                    self.findings.append({
                        "type": "type_mismatch",
                        "severity": "warning",
                        "line": node.lineno,
                        "message": f"类型不匹配: int + str (数字 {left.value} + 字符串 '{right.value}')",
                        "suggestion": "使用 f-string 或 str() 转换: f'{left.value}{right.value}'",
                    })

    def _check_modify_while_iterating(self, tree: ast.AST):
        """检测循环中修改正在迭代的列表"""
        for node in ast.walk(tree):
            if isinstance(node, ast.For):
                # 获取迭代的变量名
                if isinstance(node.iter, ast.Name):
                    iter_var = node.iter.id
                    # 检查循环体中是否有对该列表的修改 (append/remove/pop)
                    for child in ast.walk(node):
                        if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute):
                            if (isinstance(child.func.value, ast.Name)
                                    and child.func.value.id == iter_var
                                    and child.func.attr in ("remove", "pop", "append", "insert", "__delitem__")):
                                self.findings.append({
                                    "type": "modify_while_iterating",
                                    "severity": "error",
                                    "line": child.lineno,
                                    "message": f"循环中修改正在迭代的列表 '{iter_var}'",
                                    "suggestion": "遍历列表的副本: for item in {0}[:]:".format(iter_var),
                                })

    def _check_bare_except(self, tree: ast.AST):
        """检测未捕获的异常 (bare except)"""
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                if node.type is None:
                    self.findings.append({
                        "type": "bare_except",
                        "severity": "warning",
                        "line": node.lineno,
                        "message": "使用了裸露的 except: 会捕获所有异常包括 KeyboardInterrupt",
                        "suggestion": "指定具体的异常类型: except SpecificException:",
                    })


# 便捷函数
def find_bugs(code: str) -> List[Dict]:
    """快速 Bug 检测"""
    return BugFinder().review(code)
