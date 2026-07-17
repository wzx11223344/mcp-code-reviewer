"""
mcp-code-reviewer: MCP 代码审查服务器

基于 FastMCP 构建，提供以下审查能力:
- review_code: 全面代码审查 (安全+风格+复杂度+Bug)
- check_security: 安全审查
- analyze_complexity: 圈复杂度分析
- suggest_fixes: 自动修复建议
- review_diff: Git Diff 审查

使用方式:
    uv run python server.py
    或配置 MCP 客户端连接。
"""

import asyncio
import difflib
import re
from typing import Dict, List, Optional

from mcp.server.fastmcp import FastMCP

from reviewers.security import SecurityReviewer
from reviewers.style import StyleReviewer
from reviewers.complexity import ComplexityAnalyzer
from reviewers.bugfinder import BugFinder

# ============================================================
# MCP Server 初始化
# ============================================================
mcp = FastMCP(
    "code-reviewer",
    description="MCP 代码审查服务器 - 支持安全审查、风格检查、复杂度分析、Bug检测和Diff审查",
)

# ============================================================
# 审查器实例（全局复用）
# ============================================================
_security_reviewer = SecurityReviewer()
_style_reviewer = StyleReviewer()
_complexity_analyzer = ComplexityAnalyzer()
_bug_finder = BugFinder()


# ============================================================
# 辅助函数
# ============================================================

def _build_report(
    title: str,
    security_findings: List[Dict],
    style_findings: List[Dict],
    complexity_findings: List[Dict],
    bug_findings: List[Dict],
    extra_sections: Optional[Dict[str, str]] = None,
) -> str:
    """
    构建结构化 Markdown 审查报告。

    Args:
        title: 报告标题
        security_findings: 安全检查结果
        style_findings: 风格检查结果
        complexity_findings: 复杂度分析结果
        bug_findings: Bug 检测结果
        extra_sections: 额外章节 (section_name -> content)

    Returns:
        格式化的 Markdown 字符串
    """
    lines = [
        f"# {title}",
        "",
        f"**生成时间**: {_timestamp()}",
        "",
        "---",
        "",
    ]

    # ---------- 摘要 ----------
    total = (
        len(security_findings)
        + len(style_findings)
        + len(complexity_findings)
        + len(bug_findings)
    )
    critical = sum(
        1 for f in security_findings + style_findings + complexity_findings + bug_findings
        if f.get("severity") == "critical"
    )
    errors = sum(
        1 for f in security_findings + style_findings + complexity_findings + bug_findings
        if f.get("severity") == "error"
    )
    warnings = sum(
        1 for f in security_findings + style_findings + complexity_findings + bug_findings
        if f.get("severity") == "warning"
    )

    lines.append("## 审查摘要")
    lines.append("")
    lines.append(f"| 指标 | 数量 |")
    lines.append(f"|------|------|")
    lines.append(f"| 总问题 | {total} |")
    lines.append(f"| Critical (严重) | {critical} |")
    lines.append(f"| Error (错误) | {errors} |")
    lines.append(f"| Warning (警告) | {warnings} |")
    lines.append("")

    # ---------- 安全审查 ----------
    lines.append("## 安全审查")
    lines.append("")
    if not security_findings:
        lines.append("✅ 未发现安全问题。")
    else:
        for f in security_findings:
            lines.append(f"### [{f['severity'].upper()}] {f.get('message', '')}")
            lines.append("")
            lines.append(f"- **类型**: {f.get('type', 'unknown')}")
            lines.append(f"- **行号**: {f.get('line', 'N/A')}")
            lines.append(f"- **严重程度**: {f.get('severity', 'unknown')}")
            lines.append(f"- **建议**: {f.get('suggestion', '无')}")
            lines.append("")
    lines.append("---")
    lines.append("")

    # ---------- 风格检查 ----------
    lines.append("## 代码风格检查")
    lines.append("")
    if not style_findings:
        lines.append("✅ 代码风格良好。")
    else:
        for f in style_findings:
            lines.append(f"### [{f['severity'].upper()}] {f.get('message', '')}")
            lines.append("")
            lines.append(f"- **类型**: {f.get('type', 'unknown')}")
            lines.append(f"- **行号**: {f.get('line', 'N/A')}")
            lines.append(f"- **严重程度**: {f.get('severity', 'unknown')}")
            lines.append(f"- **建议**: {f.get('suggestion', '无')}")
            lines.append("")
    lines.append("---")
    lines.append("")

    # ---------- 复杂度分析 ----------
    lines.append("## 复杂度分析")
    lines.append("")
    if not complexity_findings:
        lines.append("✅ 代码复杂度在合理范围内。")
    else:
        for f in complexity_findings:
            metric_str = ""
            if "metric" in f:
                m = f["metric"]
                metric_str = f" (指标: {m.get('name', '?')} = {m.get('value', '?')})"
            lines.append(f"### [{f['severity'].upper()}] {f.get('message', '')}")
            lines.append("")
            lines.append(f"- **类型**: {f.get('type', 'unknown')}{metric_str}")
            lines.append(f"- **行号**: {f.get('line', 'N/A')}")
            lines.append(f"- **建议**: {f.get('suggestion', '无')}")
            lines.append("")
    lines.append("---")
    lines.append("")

    # ---------- Bug 检测 ----------
    lines.append("## Bug 模式检测")
    lines.append("")
    if not bug_findings:
        lines.append("✅ 未检测到常见 Bug 模式。")
    else:
        for f in bug_findings:
            lines.append(f"### [{f['severity'].upper()}] {f.get('message', '')}")
            lines.append("")
            lines.append(f"- **类型**: {f.get('type', 'unknown')}")
            lines.append(f"- **行号**: {f.get('line', 'N/A')}")
            lines.append(f"- **严重程度**: {f.get('severity', 'unknown')}")
            lines.append(f"- **建议**: {f.get('suggestion', '无')}")
            lines.append("")

    # ---------- 额外章节 ----------
    if extra_sections:
        lines.append("---")
        lines.append("")
        for section_name, content in extra_sections.items():
            lines.append(f"## {section_name}")
            lines.append("")
            lines.append(content)
            lines.append("")

    return "\n".join(lines)


def _timestamp() -> str:
    """获取当前时间戳字符串"""
    import datetime
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _detect_language(code: str) -> str:
    """
    通过代码内容启发式检测语言。目前主要支持 Python。
    可扩展支持更多语言。
    """
    # Python 特征
    if re.search(r'^\s*(import |from |def |class |print\(|if __name__)', code, re.MULTILINE):
        return "python"
    # JavaScript/TypeScript
    if re.search(r'^\s*(import |export |const |let |var |function |async |await )', code, re.MULTILINE):
        return "javascript"
    # Java
    if re.search(r'^\s*(public |private |protected |class |import java\.)', code, re.MULTILINE):
        return "java"
    # Go
    if re.search(r'^\s*(package |import |func |type struct)', code, re.MULTILINE):
        return "go"
    # Rust
    if re.search(r'^\s*(fn |let mut |use |impl |pub )', code, re.MULTILINE):
        return "rust"

    return "unknown"


# ============================================================
# MCP Tools
# ============================================================

@mcp.tool()
async def review_code(code: str, language: str = "python") -> str:
    """执行全面代码审查: 安全+风格+复杂度+Bug检测

    Args:
        code: 待审查的源代码
        language: 编程语言 (默认 python)

    Returns:
        结构化 Markdown 审查报告
    """
    if not code.strip():
        return "❌ 错误: 未提供待审查的代码。"

    detected_lang = _detect_language(code)
    if language == "auto":
        language = detected_lang
        if language == "unknown":
            language = "python"

    security_findings = _security_reviewer.review(code)
    style_findings = _style_reviewer.review(code, language)
    complexity_findings = _complexity_analyzer.review(code)
    bug_findings = _bug_finder.review(code)

    report = _build_report(
        title=f"全面代码审查报告 ({language})",
        security_findings=security_findings,
        style_findings=style_findings,
        complexity_findings=complexity_findings,
        bug_findings=bug_findings,
    )
    return report


@mcp.tool()
async def check_security(code: str, language: str = "python") -> str:
    """安全审查: 检测SQL注入/命令注入/路径遍历/敏感信息泄露等模式

    Args:
        code: 待审查的源代码
        language: 编程语言 (默认 python)

    Returns:
        结构化 Markdown 安全审查报告
    """
    if not code.strip():
        return "❌ 错误: 未提供待审查的代码。"

    findings = _security_reviewer.review(code)

    lines = [
        "# 安全审查报告",
        "",
        f"**生成时间**: {_timestamp()}",
        f"**语言**: {language}",
        "",
        "---",
        "",
    ]

    if not findings:
        lines.append("## ✅ 未发现安全问题")
        lines.append("")
        lines.append("代码看起来安全。")
    else:
        total = len(findings)
        critical = sum(1 for f in findings if f.get("severity") == "critical")
        high = sum(1 for f in findings if f.get("severity") == "high")
        medium = sum(1 for f in findings if f.get("severity") == "medium")

        lines.append("## 安全审查摘要")
        lines.append("")
        lines.append(f"| 严重程度 | 数量 |")
        lines.append(f"|----------|------|")
        lines.append(f"| Critical | {critical} |")
        lines.append(f"| High     | {high} |")
        lines.append(f"| Medium   | {medium} |")
        lines.append(f"| **总计** | **{total}** |")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## 发现的问题")
        lines.append("")

        for i, f in enumerate(findings, 1):
            lines.append(f"### {i}. [{f['severity'].upper()}] {f.get('message', '')}")
            lines.append("")
            lines.append(f"- **类型**: {f.get('type', 'unknown')}")
            lines.append(f"- **行号**: {f.get('line', 'N/A')}")
            lines.append(f"- **严重程度**: {f.get('severity', 'unknown')}")
            lines.append(f"- **建议**: {f.get('suggestion', '无')}")
            lines.append("")

    return "\n".join(lines)


@mcp.tool()
async def analyze_complexity(code: str, language: str = "python") -> str:
    """圈复杂度分析: 函数复杂度评分 + 过长函数检测 + 嵌套深度检测

    Args:
        code: 待分析的源代码
        language: 编程语言 (默认 python)

    Returns:
        结构化 Markdown 复杂度分析报告
    """
    if not code.strip():
        return "❌ 错误: 未提供待分析的代码。"

    findings = _complexity_analyzer.review(code)

    lines = [
        "# 代码复杂度分析报告",
        "",
        f"**生成时间**: {_timestamp()}",
        f"**语言**: {language}",
        "",
        "### 圈复杂度参考标准",
        "",
        "| 评分 | 风险等级 | 说明 |",
        "|------|----------|------|",
        "| 1-10 | 低 | 代码结构良好 |",
        "| 11-20 | 中 | 建议考虑重构 |",
        "| 21-50 | 高 | 强烈建议重构 |",
        "| >50 | 极高 | 必须重构 |",
        "",
        "---",
        "",
    ]

    if not findings:
        lines.append("## ✅ 复杂度在合理范围内")
        lines.append("")
        lines.append("未检测到复杂度问题。")
    else:
        for f in findings:
            metric_str = ""
            if "metric" in f:
                m = f["metric"]
                metric_str = f" (指标: {m.get('name', '?')} = {m.get('value', '?')})"
            lines.append(f"### [{f['severity'].upper()}] {f.get('message', '')}")
            lines.append("")
            lines.append(f"- **类型**: {f.get('type', 'unknown')}{metric_str}")
            lines.append(f"- **行号**: {f.get('line', 'N/A')}")
            lines.append(f"- **建议**: {f.get('suggestion', '无')}")
            lines.append("")

    return "\n".join(lines)


@mcp.tool()
async def suggest_fixes(code: str, issue_type: str = "all") -> str:
    """自动修复建议: 针对检测到的问题生成修复代码

    Args:
        code: 待修复的源代码
        issue_type: 问题类型 (all|security|style|complexity|bugs)

    Returns:
        包含修复建议的结构化 Markdown 报告
    """
    if not code.strip():
        return "❌ 错误: 未提供代码。"

    security_findings = _security_reviewer.review(code) if issue_type in ("all", "security") else []
    style_findings = _style_reviewer.review(code) if issue_type in ("all", "style") else []
    complexity_findings = _complexity_analyzer.review(code) if issue_type in ("all", "complexity") else []
    bug_findings = _bug_finder.review(code) if issue_type in ("all", "bugs") else []

    all_findings = security_findings + style_findings + complexity_findings + bug_findings

    lines = [
        "# 代码修复建议",
        "",
        f"**生成时间**: {_timestamp()}",
        f"**问题类型过滤**: {issue_type}",
        f"**检测到的问题数**: {len(all_findings)}",
        "",
        "---",
        "",
    ]

    if not all_findings:
        lines.append("## ✅ 未检测到需要修复的问题")
        lines.append("")
        return "\n".join(lines)

    for i, f in enumerate(all_findings, 1):
        lines.append(f"## {i}. {f.get('message', '未知问题')}")
        lines.append("")
        lines.append(f"- **类型**: {f.get('type', 'unknown')}")
        lines.append(f"- **行号**: {f.get('line', 'N/A')}")
        lines.append(f"- **严重程度**: {f.get('severity', 'unknown')}")
        lines.append("")
        lines.append("### 修复建议")
        lines.append("")
        lines.append(f"{f.get('suggestion', '无自动修复建议。')}")
        lines.append("")

        # 生成修复代码示例（针对常见问题）
        fix_code = _generate_fix_example(f, code)
        if fix_code:
            lines.append("### 修复代码示例")
            lines.append("")
            lines.append("```python")
            lines.append(fix_code)
            lines.append("```")
            lines.append("")

    return "\n".join(lines)


def _generate_fix_example(finding: Dict, original_code: str) -> Optional[str]:
    """根据发现生成修复代码示例"""
    issue_type = finding.get("type", "")

    if issue_type == "sql_injection":
        return (
            "# 原代码 (SQL 拼接，存在注入风险)\n"
            "cursor.execute(\"SELECT * FROM users WHERE id = \" + user_id)\n\n"
            "# 修复: 使用参数化查询\n"
            "cursor.execute(\"SELECT * FROM users WHERE id = ?\", (user_id,))"
        )

    if issue_type == "command_injection":
        return (
            "# 原代码 (shell=True，存在注入风险)\n"
            "subprocess.run(f\"ls {path}\", shell=True)\n\n"
            "# 修复: 使用参数列表\n"
            "subprocess.run([\"ls\", path], shell=False)"
        )

    if issue_type == "dangerous_function":
        func_name = finding.get("message", "").split(":")[0] if ":" in finding.get("message", "") else "eval"
        return (
            f"# 原代码 (危险函数调用 {func_name})\n"
            f"result = {func_name}(user_input)\n\n"
            f"# 修复: 避免使用 {func_name}()\n"
            f"# 如果必须使用，确保输入经过严格的校验\n"
            f"import ast\n"
            f"tree = ast.parse(user_input)  # 仅解析语法树，不执行"
        )

    if issue_type == "mutable_default_arg":
        return (
            "# 原代码 (可变默认参数)\n"
            "def process(items=[]):\n"
            "    items.append('new')\n"
            "    return items\n\n"
            "# 修复: 使用 None 作为默认值\n"
            "def process(items=None):\n"
            "    if items is None:\n"
            "        items = []\n"
            "    items.append('new')\n"
            "    return items"
        )

    if issue_type == "modify_while_iterating":
        return (
            "# 原代码 (循环中修改列表)\n"
            "for item in my_list:\n"
            "    if condition(item):\n"
            "        my_list.remove(item)\n\n"
            "# 修复: 遍历列表的副本\n"
            "for item in my_list[:]:\n"
            "    if condition(item):\n"
            "        my_list.remove(item)"
        )

    if issue_type == "bare_except":
        return (
            "# 原代码 (裸 except)\n"
            "try:\n"
            "    result = do_something()\n"
            "except:\n"
            "    pass\n\n"
            "# 修复: 指定具体异常类型\n"
            "try:\n"
            "    result = do_something()\n"
            "except ValueError as e:\n"
            "    print(f'处理值错误: {e}')\n"
            "except Exception as e:\n"
            "    print(f'处理其他异常: {e}')"
        )

    if issue_type == "division_by_zero":
        return (
            "# 原代码 (除零风险)\n"
            "result = a / 0\n\n"
            "# 修复: 除法前检查除数\n"
            "if divisor != 0:\n"
            "    result = a / divisor\n"
            "else:\n"
            "    result = float('inf')  # 或抛出有意义的异常"
        )

    if issue_type == "type_mismatch":
        return (
            "# 原代码 (类型不匹配)\n"
            "result = 'Count: ' + 42\n\n"
            "# 修复: 使用 f-string 或 str() 转换\n"
            "result = f'Count: {42}'\n"
            "# 或\n"
            "result = 'Count: ' + str(42)"
        )

    return None


@mcp.tool()
async def review_diff(diff: str, language: str = "python") -> str:
    """审查 Git diff: 只审查变更行

    解析 unified diff 格式，提取新增/修改的行，仅对这些行进行审查。

    Args:
        diff: Git diff 输出内容 (unified diff 格式)
        language: 编程语言 (默认 python)

    Returns:
        结构化 Markdown diff 审查报告
    """
    if not diff.strip():
        return "❌ 错误: 未提供 diff 内容。"

    # 解析 diff，提取变更行
    changed_lines = []
    current_file = "unknown"
    added_chunks = []

    for line in diff.split("\n"):
        if line.startswith("+++ ") or line.startswith("--- "):
            continue
        if line.startswith("diff --git"):
            # 提取文件名
            parts = line.split()
            if len(parts) >= 4:
                current_file = parts[2].replace("a/", "", 1)
            continue
        if line.startswith("@@ "):
            # 提取行号信息
            match = re.search(r'\+(\d+)(?:,(\d+))?', line)
            if match:
                start_line = int(match.group(1))
                added_chunks.append({"file": current_file, "start": start_line, "lines": []})
            continue

        if added_chunks and (line.startswith("+") and not line.startswith("+++")):
            # 新增行
            content = line[1:]  # 去掉 '+'
            added_chunks[-1]["lines"].append(content)
            changed_lines.append({"file": current_file, "line": added_chunks[-1]["start"] + len(added_chunks[-1]["lines"]) - 1, "content": content})

        elif added_chunks and line.startswith(" "):
            # 上下文行，不做检查
            pass

        elif added_chunks and line.startswith("-"):
            pass

    if not changed_lines:
        return "## Diff 审查报告\n\n未检测到需要审查的变更行（可能是纯删除或空 diff）。"

    # 对变更行进行审查
    security_findings = _security_reviewer.review("\n".join(l["content"] for l in changed_lines))
    style_findings = _style_reviewer.review("\n".join(l["content"] for l in changed_lines), language)
    bug_findings = _bug_finder.review("\n".join(l["content"] for l in changed_lines))

    # 构建 diff 统计
    changed_files = set(l["file"] for l in changed_lines)
    added_count = len(changed_lines)
    total_findings = len(security_findings) + len(style_findings) + len(bug_findings)

    lines = [
        "# Git Diff 代码审查报告",
        "",
        f"**生成时间**: {_timestamp()}",
        f"**语言**: {language}",
        "",
        "---",
        "",
        "## Diff 统计",
        "",
        f"| 指标 | 数值 |",
        f"|------|------|",
        f"| 变更文件数 | {len(changed_files)} |",
        f"| 新增/修改行数 | {added_count} |",
        f"| 发现问题数 | {total_findings} |",
        "",
        "### 变更文件",
        "",
    ]

    for cf in sorted(changed_files):
        lines.append(f"- `{cf}`")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 受限的安全审查（只针对新增行中发现的严重问题）
    if security_findings:
        lines.append("## 安全风险")
        lines.append("")
        lines.append("⚠️ 在新增代码中发现以下安全风险:")
        lines.append("")
        for f in security_findings:
            if f.get("severity") in ("critical", "high"):
                lines.append(f"- **Line {f.get('line', '?')}**: [{f['severity'].upper()}] {f.get('message', '')}")
                lines.append(f"  - 建议: {f.get('suggestion', '无')}")
                lines.append("")
        lines.append("---")
        lines.append("")

    # 风格/质量
    if style_findings:
        lines.append("## 代码风格问题")
        lines.append("")
        for f in style_findings:
            lines.append(f"- **Line {f.get('line', '?')}**: [{f['severity'].upper()}] {f.get('message', '')}")
        lines.append("")
        lines.append("---")
        lines.append("")

    if bug_findings:
        lines.append("## Bug 风险")
        lines.append("")
        for f in bug_findings:
            lines.append(f"- **Line {f.get('line', '?')}**: [{f['severity'].upper()}] {f.get('message', '')}")
            lines.append(f"  - 建议: {f.get('suggestion', '无')}")
            lines.append("")
        lines.append("---")
        lines.append("")

    if total_findings == 0:
        lines.append("## ✅ 变更代码质量良好")
        lines.append("")
        lines.append("未在变更行中发现安全、风格或 Bug 问题。")
        lines.append("")

    return "\n".join(lines)


# ============================================================
# 资源 (Resources)
# ============================================================

@mcp.resource("reviewer://languages")
def get_supported_languages() -> str:
    """返回支持的语言列表"""
    return """## 支持的语言

mcp-code-reviewer 当前主要支持 **Python**，其他语言有限支持。

| 语言 | 安全审查 | 风格检查 | 复杂度分析 | Bug检测 |
|------|----------|----------|------------|--------|
| Python | ✅ 完整 | ✅ 完整 | ✅ 完整 | ✅ 完整 |
| JavaScript | ⚠️ 基础 | ⚠️ 基础 | ⚠️ 基础 | ⚠️ 基础 |
| TypeScript | ⚠️ 基础 | ⚠️ 基础 | ⚠️ 基础 | ⚠️ 基础 |
| Java | ⚠️ 基础 | ⚠️ 基础 | ⚠️ 基础 | ⚠️ 基础 |
| Go | ⚠️ 基础 | ⚠️ 基础 | ⚠️ 基础 | ⚠️ 基础 |
| Rust | ⚠️ 基础 | ⚠️ 基础 | ⚠️ 基础 | ⚠️ 基础 |

> ⚠️ 基础 = 正则匹配为主；✅ 完整 = AST 深度分析
"""


@mcp.resource("reviewer://metrics")
def get_metrics_explanation() -> str:
    """返回指标说明"""
    return """## 审查指标说明

### 1. 圈复杂度 (Cyclomatic Complexity)
- **定义**: 代码中独立线性路径的数量
- **计算**: 基准=1，每个 if/for/while/and/or/case/except 加1
- **参考**: 1-10 低, 11-20 中, 21-50 高, >50 极高

### 2. 嵌套深度 (Nesting Depth)
- **定义**: 条件/循环语句的最大嵌套层数
- **参考**: <=3 良好, 4-5 中等, >5 过深

### 3. 函数长度 (Function Length)
- **定义**: 函数的行数
- **参考**: <=30 良好, 31-60 中等, >60 过长

### 4. 参数数量 (Parameter Count)
- **定义**: 函数参数个数
- **参考**: <=5 良好, 6-7 中等, >=8 过多
"""


@mcp.resource("reviewer://about")
def get_about() -> str:
    """返回关于信息"""
    return """# mcp-code-reviewer

一个基于 FastMCP 的代码审查 MCP Server，提供全面的代码审查能力。

## 功能

- **review_code**: 全面审查 (安全+风格+复杂度+Bug)
- **check_security**: 安全漏洞检测
- **analyze_complexity**: 复杂度分析
- **suggest_fixes**: 修复建议生成
- **review_diff**: Git Diff 增量审查

## 使用方法

### 方式1: 直接运行
```bash
uv run python server.py
```

### 方式2: MCP 客户端配置
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
"""


# ============================================================
# 入口
# ============================================================

def main():
    """启动 MCP Server"""
    mcp.run()


if __name__ == "__main__":
    main()
