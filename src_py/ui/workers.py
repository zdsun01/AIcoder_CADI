"""
QThread 工作线程 —— 薄封装，仅负责在后台调用 backend API 并发射信号。
"""

import re
import requests
from PyQt5.QtCore import QThread, pyqtSignal

from backend.api_client import LLMClient


class ConnectionTestThread(QThread):
    """异步测试 LLM 连接"""
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, api_url, api_key, model, host=""):
        super().__init__()
        self.client = LLMClient(api_url, api_key, model, host)

    def run(self):
        success, msg = self.client.test_connection()
        self.finished_signal.emit(success, msg)


class GenerationThread(QThread):
    """异步调用 LLM 生成"""
    finished_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)

    def __init__(self, api_url, api_key, model, prompt, host=""):
        super().__init__()
        self.client = LLMClient(api_url, api_key, model, host)
        self.prompt = prompt

    def run(self):
        success, result = self.client.generate(self.prompt)
        if success:
            self.finished_signal.emit(result)
        else:
            self.error_signal.emit(result)


class BatchTestThread(QThread):
    """变量表自动化测试线程"""
    progress_signal = pyqtSignal(int, int, str)
    finished_signal = pyqtSignal(bool, str)
    log_signal = pyqtSignal(str)

    def __init__(self, config, rag_manager, test_data, template_path, output_dir, kb_name):
        super().__init__()
        self.config = config
        self.rag_manager = rag_manager
        self.test_data = test_data
        self.template_path = template_path
        self.output_dir = output_dir
        self.kb_name = kb_name
        self.is_running = True

    def run(self):
        import os
        from backend.prompt_builder import PromptBuilder
        from backend.report_generator import WordReportGenerator

        generated_files = []
        total = len(self.test_data)
        self.log_signal.emit(f"🚀 开始批量测试，共 {total} 个变量...")

        for idx, row in enumerate(self.test_data):
            if not self.is_running:
                break

            num_id = idx + 1
            signal_name = str(row.get("信号名称", "Unknown"))
            headers = [k for k in row.keys() if k and not str(k).startswith("Unnamed")]
            row_content_str = "\n".join([f"{k}: {v}" for k, v in row.items()])

            self.progress_signal.emit(idx, total, f"正在测试 [{num_id}/{total}]: {signal_name}")

            # RAG 检索
            question_for_llm = f'变量"{signal_name}"的定义是什么？'
            rag_context = ""
            try:
                rag_context = self.rag_manager.recall(question_for_llm, self.kb_name)
            except Exception as e:
                rag_context = f"检索失败: {e}"

            # 构建 prompt
            prompt, _ = PromptBuilder.build_variable_test_prompt(signal_name, rag_context, headers)

            # LLM 调用
            llm_response = ""
            try:
                payload = {
                    "model": self.config.model_name,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                }
                headers_http = {
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Content-Type": "application/json",
                }
                if self.config.host:
                    headers_http["Host"] = self.config.host
                resp = requests.post(self.config.api_url, json=payload, headers=headers_http, timeout=60)
                if resp.status_code == 200:
                    result = resp.json()
                    if "choices" in result:
                        llm_response = result["choices"][0]["message"]["content"]
                    else:
                        llm_response = str(result)
                else:
                    llm_response = f"API Error: {resp.status_code} - {resp.text}"
            except Exception as e:
                llm_response = f"请求异常: {str(e)}"

            # 生成 Word
            word_data = {
                "{num_id}": str(num_id),
                "{信号名称}": signal_name,
                "{变量表该行的所有内容}": row_content_str,
                "{LLM回答}": llm_response,
            }

            temp_filename = f"test_res_{num_id:03d}_{signal_name}.docx"
            temp_filename = re.sub(r'[\\/*?:"<>|]', "_", temp_filename)
            temp_file_path = os.path.join(self.output_dir, temp_filename)

            success, msg = WordReportGenerator.generate_report(self.template_path, temp_file_path, word_data)
            if success:
                generated_files.append(temp_file_path)
            else:
                self.log_signal.emit(f"❌ Word 生成失败 ({signal_name}): {msg}")

        # 合并报告
        if generated_files and self.is_running:
            self.progress_signal.emit(total, total, "正在合并测试报告...")
            final_report_path = os.path.join(self.output_dir, "Final_Variable_Test_Report.docx")
            success, msg = WordReportGenerator.merge_reports(generated_files, final_report_path)

            if success:
                self.finished_signal.emit(True, f"测试完成！报告已生成: {final_report_path}")
            else:
                self.finished_signal.emit(False, f"合并失败: {msg}")

            for f in generated_files:
                try:
                    os.remove(f)
                except Exception:
                    pass
        else:
            self.finished_signal.emit(False, "未生成任何有效文件或任务被停止")

    def stop(self):
        self.is_running = False
