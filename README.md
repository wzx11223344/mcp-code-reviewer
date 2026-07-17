# mcp-code-reviewer

[![CI](https://github.com/your-username/mcp-code-reviewer/actions/workflows/ci.yml/badge.svg)](https://github.com/your-username/mcp-code-reviewer/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-Server-purple)](https://github.com/modelcontextprotocol/python-sdk)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

基于 [FastMCP](https://github.com/modelcontextprotocol/python-sdk) 构建的代码审查 MCP Server，支持对 Python 代码进行安全审查、风格检查、复杂度分析和 Bug 模式检测。

## 功能特性

| 工具 | 说明 | 输入 | 输出 |
|------|------|------|------|
| `review_code` | 全面代码审查 | code + language | Markdown 报告 (安全+风格+复杂度+Bug) |
| `check_security` | 安全漏洞检测 | code + language | Markdown 安全报告 |
| `analyze_complexity` | 圈复杂度分析 | code + language | Markdown 复杂度报告 |
| `suggest_fixes` | 自动修复建议 | code + issue_type | Markdown 修复方案 |
| `review_diff` | Git Diff 增量审查 | diff + language | Markdown Diff 报告 |

### 检测能力

- **安全审查**: SQL注入、命令注入、`exec`/`eval`、`pickle.loads`、硬编码密钥、SSRF、不安全的 `yaml.load`
- **风格检查**: 行过长 (>120字符)、缺失 docstring、命名规范、魔法数字、未使用 import、尾随空格
- **复杂度分析**: 圈复杂度 (McCabe)、函数长度、嵌套深度、参数数量、返回语句数量
- **Bug 检测**: 可变默认参数、除零风险、类型不匹配 (str+int)、循环中修改列表、裸露 except

## 快速开始

### 前置要求

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (推荐) 或 pip

### 安装

```bash
# 克隆仓库
git clone https://github.com/your-username/mcp-code-reviewer.git
cd mcp-code-reviewer

# 使用 pip 安装依赖
pip install -r requirements.txt

# 或使用 uv
uv sync
```

### 运行

```bash
# 直接运行
python server.py

# 使用 uv
uv run python server.py
```

## MCP 客户端配置

将以下配置添加到你的 MCP 客户端配置文件中:

### Cursor
```json
{
  "mcpServers": {
    "code-reviewer": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/mcp-code-reviewer", "server.py"]
    }
  }
}
```

### Claude Desktop
```json
{
  "mcpServers": {
    "code-reviewer": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/mcp-code-reviewer", "server.py"]
    }
  }
}
```

### VS Code (vscode-mcp)
```json
{
  "servers": {
    "code-reviewer": {
      "type": "command",
      "command": "uv",
      "args": ["run", "--directory", "/path/to/mcp-code-reviewer", "server.py"]
    }
  }
}
```

> 注意: 将 `/path/to/mcp-code-reviewer` 替换为实际的项目路径。

## 使用示例

### 全面代码审查

```python
# 完整的 MCP 工具调用
review_result = await mcp.call_tool("review_code", {
    "code": '''
def process(data):
    import subprocess
    subprocess.run("rm -rf " + data, shell=True)
    return data
''',
    "language": "python"
})
```

### 安全审查

```python
result = await mcp.call_tool("check_security", {
    "code": 'eval(user_input)',
    "language": "python"
})
```

### Git Diff 审查

```python
result = await mcp.call_tool("review_diff", {
    "diff": """
diff --git a/app.py b/app.py
+import os
+os.system("rm -rf /tmp")
""",
    "language": "python"
})
```

## 项目结构

```
mcp-code-reviewer/
├── server.py              # MCP Server 主程序
├── reviewers/
│   ├── __init__.py
│   ├── security.py        # 安全检查器
│   ├── style.py           # 代码风格检查
│   ├── complexity.py      # 复杂度分析
│   └── bugfinder.py       # Bug 模式检测
├── tests/
│   ├── __init__.py
│   ├── test_security.py
│   ├── test_style.py
│   ├── test_complexity.py
│   └── test_bugfinder.py
├── requirements.txt
├── pyproject.toml
├── .gitignore
└── README.md
```

## 运行测试

```bash
# 运行所有测试
pytest

# 运行特定测试文件
pytest tests/test_security.py -v

# 生成覆盖率报告
pytest --cov=reviewers --cov-report=term-missing
```

## 支持的资源

MCP Server 提供了以下只读资源:

- `reviewer://languages` - 支持的语言列表
- `reviewer://metrics` - 审查指标说明
- `reviewer://about` - 关于信息

## 许可证

[MIT](LICENSE)
