import json
import os

class ConfigManager:
    """管理配置，支持保存到 config.json 文件"""
    def __init__(self):
        self.config_file = "../config.json"
        self.models_file = "../cfg/models.json"
        self.project_root = ""
        self.variable_excel_path = ""

        # 1. 对话/生成模型配置 (LLM)
        self.api_url = "http://192.104.51.3:28080/v1/chat/completions"
        self.api_key = ""
        self.model_name = "deepseek-v3.1"
        self.host = ""

        # 2. 向量/RAG模型配置 (Embedding)
        self.embed_api_url = "http://192.104.51.3:28080/embed"
        self.embed_api_key = ""
        self.embed_model_name = ""

        self.prompt_template = """# Role (角色设定)
你是一位精通C/C++航空领域的软件架构师和代码审计专家。

# Context (知识库参考)
系统已从内部知识库检索到以下相关背景信息，请在生成代码时优先参考：
\"\"\"
{context}
\"\"\"

# Rules (编码规范)
必须严格遵守以下项目级编码约束：
\"\"\"
{rules}
\"\"\"
(注：以上规则包含自动检索到的 **GJB 5369-2005** 相关条款。如果规则为空，请遵循该
标准的通用安全最佳实践)

# Task Assignment (结构化任务)
你当前需要实现以下具体需求：

1. **需求元数据**:
   - ID: {req_id}
   - 名称: {req_name}

2. **核心逻辑描述**:
   \"\"\"
   {req_content}
   \"\"\"

3. **变量定义 (输入/输出/状态)**:
   \"\"\"
   {req_vars}
   \"\"\"
   说明：如果此处为空或指示参考 Rules，则说明该需求完全依赖全局系统信号，请移步 
Rules 部分查看 Excel 匹配结果。

4. **参考实现 (遗留代码)**:
   \"\"\"
   {req_ref_code}
   \"\"\"

# Instructions (执行思维链)
请不要急于输出代码，而是按照以下步骤进行深度思考：
1. **需求解构**: 识别核心输入输出。
2. **规则匹配**: 仔细阅读 Rules 部分，指出当前代码可能违反的 GJB 规则。
3. **逻辑移植**: 参考 [参考实现] 的写法，但必须按照 [核心逻辑描述] 的要求重写业务逻辑，并根据 [变量定义] 生成对应的结构体。
4. **代码实现**: 编写符合 GJB 5369 标准的 C 代码。
5. **自我验证**: 检查是否满足所有强制类规则。
"""
        self.load_config()

    def save_config(self):
        data = {
            "api_url": self.api_url,
            "api_key": self.api_key,
            "model_name": self.model_name,
            "host": self.host,
            "embed_api_url": self.embed_api_url,
            "embed_api_key": self.embed_api_key,
            "embed_model_name": self.embed_model_name,
            "prompt_template": self.prompt_template,
            "project_root": self.project_root
        }
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            print("配置已保存到本地")
        except Exception as e:
            print(f"保存配置失败: {e}")

    def load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.api_url = data.get("api_url", self.api_url)
                    self.api_key = data.get("api_key", self.api_key)
                    self.model_name = data.get("model_name", self.model_name)
                    self.host = data.get("host", self.host)
                    self.embed_api_url = data.get("embed_api_url", self.embed_api_url)
                    self.embed_api_key = data.get("embed_api_key", self.embed_api_key)
                    self.embed_model_name = data.get("embed_model_name", self.embed_model_name)
                    self.prompt_template = data.get("prompt_template", self.prompt_template)
                    self.project_root = data.get("project_root", self.project_root)
            except Exception as e:
                print(f"加载配置失败: {e}")

    def load_model_profiles(self):
        if os.path.exists(self.models_file):
            try:
                with open(self.models_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"加载模型配置文件失败: {e}")
                return {}
        return {}

    def save_model_profile(self, name, profile_data):
        profiles = self.load_model_profiles()
        profiles[name] = profile_data
        
        # 确保目录存在
        os.makedirs(os.path.dirname(self.models_file), exist_ok=True)
        try:
            with open(self.models_file, 'w', encoding='utf-8') as f:
                json.dump(profiles, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"配置文件保存失败: {e}")
