import json
import os

class ConfigManager:
    """管理配置，提示词保存到 cfg/prompt_template.json 文件"""
    def __init__(self):
        # 使用相对于当前文件或工程根目录的确定路径
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.models_file = os.path.join(base_dir, "cfg", "models.json")
        self.embed_models_file = os.path.join(base_dir, "cfg", "embedding.json")
        self.prompt_template_file = os.path.join(base_dir, "cfg", "prompt_template.json")
        self.active_config_file = os.path.join(base_dir, "cfg", "last_model_config.json")
        self.project_root = ""
        self.variable_excel_path = ""

        # 1. 对话/生成模型配置 (LLM)
        self.api_url = ""
        self.api_key = ""
        self.model_name = ""
        self.host = ""

        # 2. 向量/RAG模型配置 (Embedding)
        self.embed_api_url = ""
        self.embed_api_key = ""
        self.embed_model_name = ""
        self.embed_host = ""

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
        # 保存 prompt_template 相关的部分
        try:
            os.makedirs(os.path.dirname(self.prompt_template_file), exist_ok=True)
            with open(self.prompt_template_file, 'w', encoding='utf-8') as f:
                json.dump({"prompt_template": self.prompt_template}, f, indent=4, ensure_ascii=False)
            print("提示词模板已保存到 cfg/prompt_template.json")
        except Exception as e:
            print(f"保存提示词模板失败: {e}")
        
        # 保存活跃配置
        try:
            active_data = {
                "project_root": self.project_root,
                "model_name": self.model_name,
                "embed_model_name": self.embed_model_name
            }
            with open(self.active_config_file, 'w', encoding='utf-8') as f:
                json.dump(active_data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"保存活跃配置失败: {e}")

    def load_config(self):
        # 1. 加载提示词模板
        if os.path.exists(self.prompt_template_file):
            try:
                with open(self.prompt_template_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.prompt_template = data.get("prompt_template", self.prompt_template)
            except Exception as e:
                print(f"加载提示词模板失败: {e}")
                
        # 加载活跃配置
        if os.path.exists(self.active_config_file):
            try:
                with open(self.active_config_file, 'r', encoding='utf-8') as f:
                    active_data = json.load(f)
                    self.project_root = active_data.get("project_root", self.project_root)
                    self.model_name = active_data.get("model_name", self.model_name)
                    self.embed_model_name = active_data.get("embed_model_name", self.embed_model_name)
            except Exception as e:
                print(f"加载活跃配置失败: {e}")

        # 2. 如果存在模型配置，自动加载第一个或者默认的 LLM 模型作为初始化
        try:
            model_profiles = self.load_model_profiles()
            if model_profiles:
                if not self.model_name or self.model_name not in model_profiles:
                    self.model_name = list(model_profiles.keys())[0]
                
                profile = model_profiles.get(self.model_name, {})
                self.api_url = profile.get("api_url", self.api_url)
                self.api_key = profile.get("api_key", self.api_key)
                self.host = profile.get("host", self.host)
        except Exception as e:
            print(f"动态加载 LLM 配置失败: {e}")

        # 3. 如果存在 Embedding 配置，自动加载第一个或者默认的 Embedding 模型作为初始化
        try:
            embed_profiles = self.load_embed_profiles()
            if embed_profiles:
                if not self.embed_model_name or self.embed_model_name not in embed_profiles:
                    self.embed_model_name = list(embed_profiles.keys())[0]
                
                profile = embed_profiles.get(self.embed_model_name, {})
                self.embed_api_url = profile.get("embed_api_url", profile.get("api_url", self.embed_api_url))
                self.embed_api_key = profile.get("embed_api_key", profile.get("api_key", self.embed_api_key))
                self.embed_host = profile.get("embed_host", profile.get("host", self.embed_host))
        except Exception as e:
            print(f"动态加载 Embedding 配置失败: {e}")

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

    def load_embed_profiles(self):
        if os.path.exists(self.embed_models_file):
            try:
                with open(self.embed_models_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"加载 Embedding 模型配置文件失败: {e}")
                return {}
        return {}

    def save_embed_profile(self, name, profile_data):
        profiles = self.load_embed_profiles()
        profiles[name] = profile_data
        
        os.makedirs(os.path.dirname(self.embed_models_file), exist_ok=True)
        try:
            with open(self.embed_models_file, 'w', encoding='utf-8') as f:
                json.dump(profiles, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Embedding 配置文件保存失败: {e}")
