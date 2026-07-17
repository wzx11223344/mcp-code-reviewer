"""
安全检查器 (Security Reviewer)

使用 AST + 正则检测代码中的安全风险模式:
- exec/eval 使用
- SQL 拼接
- os.system/subprocess shell=True
- pickle.loads
- 硬编码密码/token/API key
- SSRF 风险
- yaml.load 未指定 Loader
"""

import ast
import re
from typing import Dict, List


class SecurityReviewer:
    """安全检查器"""

    # 硬编码敏感信息正则
    SENSITIVE_PATTERNS = [
        (re.compile(r'(?i)(password|passwd|pwd)\s*[=:]\s*[\'\"][^\'\"]+[\'\"]'), "硬编码密码"),
        (re.compile(r'(?i)(api[_-]?key|apikey)\s*[=:]\s*[\'\"][^\'\"]+[\'\"]'), "硬编码 API Key"),
        (re.compile(r'(?i)(secret|token|auth_token|access_token)\s*[=:]\s*[\'\"][^\'\"]+[\'\"]'), "硬编码 Secret/Token"),
        (re.compile(r'(?i)aws_access_key_id|aws_secret_access_key'), "AWS 密钥硬编码"),
    ]

    # SQL 拼接正则
    SQL_PATTERNS = [
        re.compile(r'(?i)(SELECT|INSERT|UPDATE|DELETE)\s+.+?\+\s*[\'\"]', re.DOTALL),
        re.compile(r'(?i)f[\'\"]?(SELECT|INSERT|UPDATE|DELETE)', re.DOTALL),
        re.compile(r'(?i)execute\s*\(\s*[\'\"].*?(SELECT|INSERT|UPDATE|DELETE)', re.DOTALL),
    ]

    def __init__(self):
        self.findings: List[Dict] = []

    def review(self, code: str) -> List[Dict]:
        """对代码执行安全检查，返回发现列表"""
        self.findings = []

        # AST 检查
        try:
            tree = ast.parse(code)
            self._check_ast(tree)
        except SyntaxError as e:
            self.findings.append({
                "type": "syntax_error",
                "severity": "error",
                "line": e.lineno or 0,
                "message": f"代码语法错误: {e.msg}",
                "suggestion": "修正语法错误后重新检查",
            })

        # 正则检查
        self._check_regex(code)

        return self.findings

    def _check_ast(self, tree: ast.AST):
        """通过 AST 遍历检查安全风险"""
        for node in ast.walk(tree):
            # exec/eval 检测
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                    if func_name in ("exec", "eval", "compile"):
                        self.findings.append({
                            "type": "dangerous_function",
                            "severity": "critical",
                            "line": node.lineno,
                            "message": f"危险函数调用: {func_name}(). 可导致任意代码执行。",
                            "suggestion": f"避免使用 {func_name}()，改用安全的替代方案。",
                        })

                # pickle.loads 检测
                if isinstance(node.func, ast.Attribute):
                    if (isinstance(node.func.value, ast.Name)
                            and node.func.value.id == "pickle"
                            and node.func.attr == "loads"):
                        self.findings.append({
                            "type": "unsafe_deserialization",
                            "severity": "critical",
                            "line": node.lineno,
                            "message": "不安全的反序列化: pickle.loads(). 可导致任意代码执行。",
                            "suggestion": "改用 json.loads() 或安全序列化库。",
                        })

                    # yaml.load 未指定 Loader
                    if (isinstance(node.func.value, ast.Name)
                            and node.func.value.id == "yaml"
                            and node.func.attr == "load"):
                        # 检查是否指定了 Loader
                        has_loader = any(
                            kw.arg == "Loader" for kw in node.keywords
                        )
                        if not has_loader:
                            self.findings.append({
                                "type": "unsafe_yaml_load",
                                "severity": "high",
                                "line": node.lineno,
                                "message": "不安全的 yaml.load() 调用: 未指定 Loader。",
                                "suggestion": "改用 yaml.safe_load() 或指定 yaml.Loader=yaml.SafeLoader。",
                            })

            # subprocess shell=True 检测
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if (isinstance(node.func.value, ast.Name)
                            and node.func.value.id == "subprocess"
                            and node.func.attr in ("call", "Popen", "run", "check_call", "check_output")):
                        for kw in node.keywords:
                            if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                                self.findings.append({
                                    "type": "command_injection",
                                    "severity": "critical",
                                    "line": node.lineno,
                                    "message": "命令注入风险: subprocess.{0}(shell=True)".format(node.func.attr),
                                    "suggestion": "设置 shell=False，使用参数列表形式传递命令。",
                                })

            # os.system 检测
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if (isinstance(node.func.value, ast.Name)
                            and node.func.value.id == "os"
                            and node.func.attr == "system"):
                        self.findings.append({
                            "type": "command_injection",
                            "severity": "critical",
                            "line": node.lineno,
                            "message": "命令注入风险: os.system(). 使用 subprocess.run() 替代。",
                            "suggestion": "改用 subprocess.run(cmd_list, shell=False)。",
                        })

            # SSRF 检测: requests.get(url_param) 或 requests.post(url_param)
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if (isinstance(node.func.value, ast.Name)
                            and node.func.value.id == "requests"
                            and node.func.attr in ("get", "post", "put", "delete", "patch")):
                        for arg in node.args:
                            if isinstance(arg, ast.Name):  # 变量传入 URL
                                self.findings.append({
                                    "type": "ssrf_risk",
                                    "severity": "medium",
                                    "line": node.lineno,
                                    "message": f"SSRF 风险: requests.{node.func.attr}() 使用了变量 '{arg.id}' 作为 URL。",
                                    "suggestion": "对 URL 做白名单校验，禁止访问内网地址。",
                                })
                                break

    def _check_regex(self, code: str):
        """通过正则检测安全模式"""
        lines = code.split("\n")
        for line_no, line_text in enumerate(lines, 1):
            stripped = line_text.strip()

            # 跳过注释
            if stripped.startswith("#"):
                continue

            # 敏感信息硬编码
            for pattern, desc in self.SENSITIVE_PATTERNS:
                if pattern.search(stripped):
                    self.findings.append({
                        "type": "hardcoded_secret",
                        "severity": "high",
                        "line": line_no,
                        "message": f"检测到{desc}",
                        "suggestion": "使用环境变量或密钥管理服务存储敏感信息。",
                    })

            # SQL 拼接检测
            for sql_pat in self.SQL_PATTERNS:
                if sql_pat.search(stripped):
                    self.findings.append({
                        "type": "sql_injection",
                        "severity": "critical",
                        "line": line_no,
                        "message": "SQL 注入风险: 检测到 SQL 查询字符串拼接。",
                        "suggestion": "使用参数化查询 (prepared statements) 或 ORM。",
                    })
                    break


# 便捷函数
def check_security(code: str) -> List[Dict]:
    """快速安全检查"""
    return SecurityReviewer().review(code)
