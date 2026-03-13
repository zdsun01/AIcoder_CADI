"""
代码解析器 —— 从 LLM 响应中提取代码。
"""

import re


def extract_code_blocks(text):
    """从 Markdown 格式的 LLM 响应中提取代码块"""
    pattern = r"```(?:\w+)?\s*(.*?)```"
    matches = re.findall(pattern, text, re.DOTALL)
    if matches:
        return "\n\n".join(matches)
    return "// 未检测到标准 Markdown 代码块，请查看上方完整回复。"


def extract_multi_files(text):
    """
    从 LLM 响应中提取多文件格式的代码。

    返回: list of (filename, content) 或 空列表（说明未匹配到多文件格式）
    """
    pattern = r"/\* === FILE_START: (.*?) === \*/(.*?)/\* === FILE_END === \*/"
    matches = re.findall(pattern, text, re.DOTALL)
    result = []
    for filename, content in matches:
        result.append((filename.strip(), content.strip()))
    return result


def parse_requirement_text(full_text):
    """解析需求文本，提取结构化字段"""
    data = {
        "req_id": "N/A",
        "req_name": "General Task",
        "req_content": full_text,
        "req_vars": "None",
        "req_ref_code": "None",
    }
    match_id = re.search(r"需求id[：:]\s*(.*?)\n", full_text, re.IGNORECASE)
    if match_id:
        data["req_id"] = match_id.group(1).strip()

    match_name = re.search(r"需求名称[：:]\s*(.*?)\n", full_text, re.IGNORECASE)
    if match_name:
        data["req_name"] = match_name.group(1).strip()

    match_content = re.search(
        r"需求内容[：:]\s*(.*?)\n\s*变量[：:]", full_text, re.IGNORECASE | re.DOTALL
    )
    if match_content:
        data["req_content"] = match_content.group(1).strip()

    match_vars = re.search(
        r"变量[：:]\s*(.*?)\n\s*参考代码[：:]", full_text, re.IGNORECASE | re.DOTALL
    )
    if match_vars:
        data["req_vars"] = match_vars.group(1).strip()

    match_ref = re.search(r"参考代码[：:]\s*(.*)", full_text, re.IGNORECASE | re.DOTALL)
    if match_ref:
        data["req_ref_code"] = match_ref.group(1).strip()

    return data
