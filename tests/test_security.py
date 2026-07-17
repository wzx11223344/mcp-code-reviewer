"""security.py 单元测试"""

import pytest
from reviewers.security import SecurityReviewer


@pytest.fixture
def reviewer():
    return SecurityReviewer()


class TestSecurityReviewer:
    """SecurityReviewer 测试集"""

    def test_detect_eval(self, reviewer):
        """检测 eval 调用"""
        code = 'result = eval(user_input)'
        findings = reviewer.review(code)
        assert any(f["type"] == "dangerous_function" for f in findings)

    def test_detect_exec(self, reviewer):
        """检测 exec 调用"""
        code = 'exec("print(1)")'
        findings = reviewer.review(code)
        assert any(f["type"] == "dangerous_function" for f in findings)

    def test_detect_sql_injection(self, reviewer):
        """检测 SQL 注入"""
        code = 'cursor.execute("SELECT * FROM users WHERE id = " + user_id)'
        findings = reviewer.review(code)
        assert any(f["type"] == "sql_injection" for f in findings)

    def test_detect_shell_true(self, reviewer):
        """检测 subprocess shell=True"""
        code = 'subprocess.run("ls", shell=True)'
        findings = reviewer.review(code)
        assert any(f["type"] == "command_injection" for f in findings)

    def test_detect_os_system(self, reviewer):
        """检测 os.system"""
        code = 'os.system("rm -rf /")'
        findings = reviewer.review(code)
        assert any(f["type"] == "command_injection" for f in findings)

    def test_detect_pickle_loads(self, reviewer):
        """检测 pickle.loads"""
        code = 'data = pickle.loads(received_data)'
        findings = reviewer.review(code)
        assert any(f["type"] == "unsafe_deserialization" for f in findings)

    def test_detect_hardcoded_password(self, reviewer):
        """检测硬编码密码"""
        code = 'password = "my_secret_pwd_123"'
        findings = reviewer.review(code)
        assert any(f["type"] == "hardcoded_secret" for f in findings)

    def test_detect_ssrf_risk(self, reviewer):
        """检测 SSRF 风险"""
        code = 'response = requests.get(url_param)'
        findings = reviewer.review(code)
        assert any(f["type"] == "ssrf_risk" for f in findings)

    def test_detect_yaml_load_no_loader(self, reviewer):
        """检测 yaml.load 未指定 Loader"""
        code = 'data = yaml.load(content)'
        findings = reviewer.review(code)
        assert any(f["type"] == "unsafe_yaml_load" for f in findings)

    def test_no_false_positive_safe_code(self, reviewer):
        """安全代码不应产生误报"""
        code = '''
import json

def safe_function(data):
    """安全的函数"""
    result = json.loads(data)
    return {"status": "ok", "data": result}
'''
        findings = reviewer.review(code)
        # 可能有一些对常量/字符串的误报，检查没有关键问题
        critical = [f for f in findings if f["severity"] in ("critical", "high")]
        assert len(critical) == 0
