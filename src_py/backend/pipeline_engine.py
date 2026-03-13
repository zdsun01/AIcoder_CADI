"""
流水线引擎 —— 批量任务解析、变量管理、参考代码管理等纯业务逻辑。
"""

import os
import re
import pandas as pd
from urllib.parse import unquote

from backend.code_parser import parse_requirement_text


# ====================================================================== #
#  数据类
# ====================================================================== #

class BatchTask:
    """单个流水线任务"""

    def __init__(self, raw_text, parsed_data):
        self.raw_text = raw_text
        self.id = parsed_data.get("req_id", "Unknown")
        self.name = parsed_data.get("req_name", "Unknown")
        self.output_rel_path = parsed_data.get("output_file", "").strip()
        self.content = parsed_data.get("req_content", "")
        self.vars = parsed_data.get("req_vars", "")
        self.ref_code = parsed_data.get("req_ref_code", "")
        self.target_files = parsed_data.get("target_files", [])
        self.status = "等待中"
        self.result_code = ""
        self.error_msg = ""
        self.generated_clean_code = ""
        self.used_global_vars = ""


# ====================================================================== #
#  变量管理
# ====================================================================== #

class VariableManager:
    """管理变量 Excel 表，提供关键词检索功能"""

    def __init__(self, excel_path):
        self.df = pd.DataFrame()
        self.is_loaded = False
        self.load_excel(excel_path)

    def load_excel(self, excel_path):
        if not excel_path or not os.path.exists(excel_path):
            return
        try:
            self.df = pd.read_excel(excel_path, engine="openpyxl")
            self.df.fillna("", inplace=True)
            self.df["search_index"] = self.df.apply(
                lambda x: f"{x.get('信号名称', '')} {x.get('信号ID（变量名）', '')} {x.get('值定义', '')}",
                axis=1,
            )
            self.is_loaded = True
            print(f"变量表加载成功，共 {len(self.df)} 条数据")
        except Exception as e:
            print(f"变量表加载失败: {e}")

    def search_relevant_vars(self, requirement_text, top_k=10):
        if not self.is_loaded or self.df.empty:
            return []

        req_keywords = set(re.split(r"[^\w]+", requirement_text))
        req_keywords = {k for k in req_keywords if len(k) > 1}

        results = []
        for _, row in self.df.iterrows():
            score = 0
            search_content = str(row["search_index"])
            for kw in req_keywords:
                if kw in search_content:
                    score += 1
            if score > 0:
                var_info = (
                    f"- 名称: {row.get('信号名称', '')}, "
                    f"ID: {row.get('信号ID（变量名）', '')}, "
                    f"类型: {row.get('数据类型', '')}, "
                    f"定义: {row.get('值定义', '')}"
                )
                results.append((score, var_info))

        results.sort(key=lambda x: x[0], reverse=True)
        return [r[1] for r in results[:top_k]]


# ====================================================================== #
#  参考代码管理
# ====================================================================== #

class RefCodeManager:
    """管理参考代码 Excel"""

    def __init__(self, excel_path):
        self.ref_data = {}
        if excel_path and os.path.exists(excel_path):
            self.load_excel(excel_path)

    def load_excel(self, path):
        try:
            df = pd.read_excel(path, engine="openpyxl")
            df.columns = [str(col).strip() for col in df.columns]
            id_col = next((c for c in df.columns if "ID" in c or "id" in c), None)
            code_col = next((c for c in df.columns if "代码" in c or "Code" in c), None)
            if id_col and code_col:
                for _, row in df.iterrows():
                    req_id = str(row[id_col]).strip()
                    code = str(row[code_col])
                    if code.lower() == "nan":
                        code = "无参考代码"
                    self.ref_data[req_id] = code
                print(f"参考代码库加载成功: {len(self.ref_data)} 条")
        except Exception as e:
            print(f"参考代码加载失败: {e}")

    def get_code(self, req_id):
        return self.ref_data.get(req_id, "无 (未在参考库中找到对应ID)")


# ====================================================================== #
#  批量任务解析
# ====================================================================== #

class TaskParser:
    """解析输入文本/文件为 BatchTask 列表"""

    @staticmethod
    def parse_excel_file(path):
        """解析 Excel 需求文件，返回 (tasks: list[BatchTask], error: str|None)"""
        tasks = []
        try:
            df = pd.read_excel(path, engine="openpyxl" if path.endswith(".xlsx") else None)
            df.dropna(how="all", inplace=True)
            df.columns = [str(col).strip() for col in df.columns]

            required_cols = ["需求ID", "需求名称"]
            for col in required_cols:
                if col not in df.columns:
                    matched = False
                    for existing_col in df.columns:
                        if col.lower() == existing_col.lower():
                            df.rename(columns={existing_col: col}, inplace=True)
                            matched = True
                            break
                    if not matched:
                        return [], f"Excel {path} 缺少列: {col}"

            for index, row in df.iterrows():
                req_id = str(row.get("需求ID", "")).strip()
                if not req_id or req_id.lower() == "nan":
                    continue

                req_name = str(row.get("需求名称", "")).strip()
                output_files_raw = str(row.get("输出文件", "")).strip()
                req_content = str(row.get("需求内容", "")).strip()
                ref_code = str(row.get("参考代码", "")).strip()
                if ref_code.lower() == "nan":
                    ref_code = "无"

                target_files = TaskParser._parse_file_list(output_files_raw)
                if not target_files:
                    safe_name = req_id.replace(".", "_").replace(":", "_").strip()
                    target_files = [f"src/auto_generated/{safe_name}.c"]

                parsed_data = {
                    "req_id": req_id,
                    "req_name": req_name,
                    "req_content": req_content,
                    "req_vars": "None",
                    "req_ref_code": ref_code,
                    "output_file": target_files[0],
                    "target_files": target_files,
                }
                tasks.append(BatchTask(f"[Excel Source] {path} Row {index}", parsed_data))

        except Exception as e:
            return [], str(e)

        return tasks, None

    @staticmethod
    def parse_text_blocks(full_text):
        """从合并后的文本中用正则解析任务，返回 list[BatchTask]"""
        tasks = []
        pattern = r"(需求id[：:].*?)(?=\n\s*需求id[：:]|\Z)"
        matches = re.finditer(pattern, full_text, re.IGNORECASE | re.DOTALL)

        for match in matches:
            block = match.group(1).strip()
            if not block:
                continue

            data = parse_requirement_text(block)

            file_pattern = r"输出文件[：:]\s*(.*?)(?=\n\s*(?:需求内容|变量|参考代码|阶段|类型|需求id)|$)"
            match_out = re.search(file_pattern, block, re.IGNORECASE | re.DOTALL)

            target_files = []
            if match_out:
                target_files = TaskParser._parse_file_list(match_out.group(1).strip())
            if not target_files:
                safe_name = data["req_id"].replace(".", "_").replace(":", "_").strip()
                target_files = [f"src/auto_generated/{safe_name}.c"]

            data["target_files"] = target_files
            data["output_file"] = target_files[0] if target_files else ""

            if data.get("req_id", "N/A") != "N/A":
                tasks.append(BatchTask(block, data))

        return tasks

    @staticmethod
    def parse_input(raw_input):
        """
        解析混合输入（文件路径 + 纯文本），返回:
            (tasks: list[BatchTask],
             excel_count: int,
             text_count: int,
             errors: list[str])
        """
        tasks = []
        errors = []
        full_text = ""
        excel_count = 0
        text_file_count = 0

        lines = raw_input.split("\n")
        for line in lines:
            line = line.strip()
            if not line:
                continue

            if line.startswith("file:///"):
                line = unquote(line[8:])

            path = line.strip('"').strip("'")
            if re.match(r"^/[a-zA-Z]:", path):
                path = path[1:]

            if os.path.isfile(path):
                if path.lower().endswith((".xlsx", ".xls")):
                    parsed, err = TaskParser.parse_excel_file(path)
                    if err:
                        errors.append(err)
                    else:
                        tasks.extend(parsed)
                        excel_count += len(parsed)
                else:
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            full_text += f.read() + "\n\n"
                            text_file_count += 1
                    except Exception as e:
                        errors.append(f"读取失败: {path} ({e})")
            else:
                full_text += line + "\n"

        if full_text.strip():
            regex_tasks = TaskParser.parse_text_blocks(full_text)
            tasks.extend(regex_tasks)

        return tasks, excel_count, len(tasks) - excel_count, errors

    @staticmethod
    def _parse_file_list(raw):
        if not raw or raw.lower() == "nan":
            return []
        potential_files = re.split(r"[,\s\n]+", raw)
        result = []
        for f in potential_files:
            f = f.strip()
            if f:
                if f.startswith("/") or f.startswith("\\"):
                    f = f[1:]
                result.append(f)
        return result


# ====================================================================== #
#  文件写入
# ====================================================================== #

def write_code_files(root_dir, multi_files):
    """
    将多文件代码写入磁盘。

    参数:
        root_dir: 工程根目录
        multi_files: list of (filename, content)
    返回:
        success_count: int
    """
    count = 0
    for filename, content in multi_files:
        try:
            full_path = os.path.join(root_dir, filename)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            count += 1
        except Exception as e:
            print(f"写入 {filename} 失败: {e}")
    return count


def write_single_file(root_dir, rel_path, content):
    """写入单个代码文件"""
    try:
        full_path = os.path.join(root_dir, rel_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        return True
    except Exception as e:
        print(f"写入失败: {e}")
        return False
