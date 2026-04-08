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


class RAGRecallThread(QThread):
    """异步执行 RAG 检索"""
    finished_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)

    def __init__(self, rag_manager, query_text, selected_kbs):
        super().__init__()
        self.rag_manager = rag_manager
        self.query_text = query_text
        self.selected_kbs = selected_kbs
        
    def run(self):
        try:
            rag_context = self.rag_manager.recall_multi(self.query_text, self.selected_kbs)
            self.finished_signal.emit(rag_context)
        except Exception as e:
            self.error_signal.emit(f"RAG检索异常: {str(e)}")


class GenerationThread(QThread):
    """异步调用 LLM 生成"""
    chunk_signal = pyqtSignal(str)   # 用于流式更新
    finished_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)

    def __init__(self, api_url, api_key, model, prompt, host=""):
        super().__init__()
        self.client = LLMClient(api_url, api_key, model, host)
        self.prompt = prompt

    def run(self):
        full_text = ""
        has_error = False
        error_msg = ""
        
        for success, content in self.client.generate_stream(self.prompt):
            if success:
                full_text += content
                self.chunk_signal.emit(content)
            else:
                has_error = True
                error_msg = content
                break
                
        if has_error:
            self.error_signal.emit(error_msg)
        else:
            self.finished_signal.emit(full_text)

