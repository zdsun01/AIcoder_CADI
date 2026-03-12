import requests
from PyQt5.QtCore import QThread, pyqtSignal

class ConnectionTestThread(QThread):
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, api_url, api_key, model):
        super().__init__()
        self.api_url = api_url
        self.api_key = api_key
        self.model = model

    def run(self):
        try:
            headers = {
                "Content-Type": "application/json",
                #"Host": "scaihpc-embed.cadi.net"
            }
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            data = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "你是谁？"},
                ],
                "max_tokens": 1
            }
            resp = requests.post(self.api_url, headers=headers, json=data, timeout=999)
            resp.raise_for_status()
            _ = resp.json()["choices"][0]["message"]["content"]
            self.finished_signal.emit(True, "连接成功！API 配置有效。")
        except Exception as e:
            self.finished_signal.emit(False, f"连接失败: {e}")


class GenerationThread(QThread):
    finished_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)

    def __init__(self, api_url, api_key, model, prompt):
        super().__init__()
        self.api_url = api_url
        self.api_key = api_key
        self.model = model
        self.prompt = prompt

    def run(self):
        try:
            headers = {
                "Content-Type": "application/json",
                #"Host": "scaihpc-deepseek.cadi.net",
                "Authorization": f"Bearer {self.api_key}",
            }
            data = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "You are a helpful AI assistant."},
                    {"role": "user", "content": self.prompt}
                ]
            }
            resp = requests.post(self.api_url, headers=headers, json=data, timeout=999)
            resp.raise_for_status()
            j = resp.json()
            generated_text = j["choices"][0]["message"]["content"]

            if generated_text:
                self.finished_signal.emit(generated_text)
            else:
                self.error_signal.emit("API 返回内容为空")

        except Exception as e:
            self.error_signal.emit(f"请求失败: {e}")