import requests


class LLMClient:
    """LLM API 调用客户端（纯 HTTP，无 UI 依赖）"""

    def __init__(self, api_url, api_key="", model_name="", host=""):
        self.api_url = api_url
        self.api_key = api_key
        self.model_name = model_name
        self.host = host

    def _build_headers(self):
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if self.host:
            headers["Host"] = self.host
        return headers

    def test_connection(self):
        """测试 LLM 连接，返回 (success: bool, message: str)"""
        try:
            data = {
                "model": self.model_name,
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "你是谁？"},
                ],
                "max_tokens": 1,
            }
            resp = requests.post(
                self.api_url,
                headers=self._build_headers(),
                json=data,
                timeout=30,
            )
            resp.raise_for_status()
            _ = resp.json()["choices"][0]["message"]["content"]
            return True, "连接成功！API 配置有效。"
        except Exception as e:
            return False, f"连接失败: {e}"

    def generate(self, prompt, system_message="You are a helpful AI assistant."):
        """调用 LLM 生成，返回 (success: bool, content_or_error: str)"""
        try:
            data = {
                "model": self.model_name,
                "messages": [
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt},
                ],
            }
            resp = requests.post(
                self.api_url,
                headers=self._build_headers(),
                json=data,
                timeout=999,
            )
            resp.raise_for_status()
            result = resp.json()
            text = result["choices"][0]["message"]["content"]
            if text:
                return True, text
            return False, "API 返回内容为空"
        except Exception as e:
            return False, f"请求失败: {e}"
