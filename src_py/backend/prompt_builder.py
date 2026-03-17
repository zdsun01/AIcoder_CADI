"""
提示词构建器 —— 所有 Prompt 拼接逻辑集中于此。

每个场景对应一个方法，返回最终要发送给 LLM 的完整 prompt 字符串。
"""

import os


class PromptBuilder:
    """集中管理所有 Prompt 构建逻辑"""

    def __init__(self, template: str):
        self.template = template

    # ------------------------------------------------------------------ #
    #  场景 1：单次代码生成（Tab1）
    # ------------------------------------------------------------------ #
    def build_generation_prompt(
        self, parsed_req, rag_context, rules_content
    ):
        """
        构建单次代码生成的 prompt。

        参数:
            parsed_req: dict，含 req_id, req_name, req_content, req_vars, req_ref_code
            rag_context: str，RAG 检索到的上下文
            rules_content: str，编码规则文本
        """
        if not rules_content:
            rules_content = "无特定规则，请遵循 GJB 5369-2005 通用标准。"

        try:
            return self.template.format(
                rules=rules_content,
                context=rag_context,
                **parsed_req,
            )
        except KeyError:
            # 万一模板含多余占位符，用 safe fallback
            return self.template.format(
                rules=rules_content,
                context=rag_context,
                req_id=parsed_req.get("req_id", "N/A"),
                req_name=parsed_req.get("req_name", ""),
                req_content=parsed_req.get("req_content", ""),
                req_vars=parsed_req.get("req_vars", "None"),
                req_ref_code=parsed_req.get("req_ref_code", "None"),
            )

    # ------------------------------------------------------------------ #
    #  场景 2：流水线批量生成（Tab5）
    # ------------------------------------------------------------------ #
    def build_pipeline_prompt(
        self,
        task_id,
        task_name,
        task_content,
        rag_context,
        matched_vars_text,
        external_rules,
        target_files,
        ref_code,
        local_vars,
    ):
        """
        构建流水线模式的 prompt。集成变量指南、多文件格式约束，取消七步SOP，使用类似单次生成的提示词。
        """
        # --- 变量展示 (看齐单次生成，仅作全集展示和基础提醒) ---
        variable_instruction = f"\n【全局变量参考】(完整全局变量表，供随时调用):\n{matched_vars_text}\n"

        # --- 目标文件列表 ---
        files_instruction = self._build_files_instruction(target_files)

        # --- 流水线格式约束 ---
        pipeline_constraint = (
            "\n【流水线模式-强制格式约束】:\n"
            "1. 请直接输出函数实现代码，严禁包含 main() 函数。\n"
            "2. 代码必须是完整的、可编译的 C 函数。\n"
            "3. 保持单次生成的简洁性，直接实现需求即可。\n"
        )

        # --- 参考代码 ---
        if ref_code and ref_code not in ("无", "None", ""):
            ref_code_section = f"\n【参考代码/遗留代码】:\n{ref_code}\n"
        else:
            ref_code_section = "无 (新开发需求)"

        # --- 合并 rules ---
        base_rule = (
            "遵循 GJB 5369-2005 通用安全标准。\n"
            if not external_rules
            else external_rules
        )
        final_rules = (
            f"{base_rule}\n{variable_instruction}\n"
            f"{files_instruction}\n{pipeline_constraint}"
        )

        # --- req_vars ---
        final_req_vars = self._resolve_req_vars(local_vars, matched_vars_text)

        # --- 填充模板 (直接复用 self.template 类似单次生成) ---
        try:
            return self.template.format(
                req_id=task_id,
                req_name=task_name,
                req_content=task_content,
                req_vars=final_req_vars,
                req_ref_code=ref_code_section,
                context=rag_context,
                rules=final_rules,
            )
        except KeyError:
            # 万一模板含多余占位符，用 safe fallback
            return self.template.format(
                rules=final_rules,
                context=rag_context,
                req_id=task_id,
                req_name=task_name,
                req_content=task_content,
                req_vars=final_req_vars,
                req_ref_code=ref_code_section,
            )

    # ------------------------------------------------------------------ #
    #  场景 3：智能问答（Tab4）
    # ------------------------------------------------------------------ #
    @staticmethod
    def build_qa_prompt(question, context, kb_names_str):
        """构建问答场景的 prompt"""
        if context and "未发现高度相关" not in context:
            return (
                f"你是一个专业的助手。用户提出了一个问题，系统已从以下知识库 [{kb_names_str}] 中检索到了参考片段。\n"
                f"请结合参考资料回答问题。\n\n"
                f"【用户问题】: {question}\n\n"
                f"【检索到的多源参考资料】:\n{context}\n\n"
                f"【回答策略】(请严格遵守):\n"
                f"1. **相关性判断**: 首先仔细阅读所有参考资料，判断它们是否包含了问题的答案。\n"
                f"2. **情况 A (资料相关)**: 如果参考资料有用，请进行综合回答，并指出来源。\n"
                f"3. **情况 B (资料不相关)**: 若参考资料与问题相似度很低，请说明这一点，然后基于通用知识回答。\n"
            )
        else:
            return (
                f"你是一个专业的助手。\n"
                f"【用户问题】: {question}\n\n"
                f"请直接回答问题，条理清晰。"
            )

    # ------------------------------------------------------------------ #
    #  场景 4：变量表测试（Tab6）
    # ------------------------------------------------------------------ #
    @staticmethod
    def build_variable_test_prompt(signal_name, rag_context, header_names):
        """构建变量测试 prompt"""
        question = f'变量"{signal_name}"的定义是什么？'
        headers_str = "、".join(header_names)
        prompt = (
            f"你是一个严谨的测试工程师。请根据参考资料回答问题。\n\n"
            f"【参考资料】:\n{rag_context}\n\n"
            f"【问题】: {question}\n\n"
            f"【要求】:\n"
            f"1. 请直接回答问题，列出该变量的详细属性（如 {headers_str}）。\n"
            f"2. 这是一个自动化测试报告的'实际输出'部分，请保持回答条理清晰，可以使用列表格式。\n"
            f'3. 如果参考资料中未找到相关定义，请直接回答"未找到该变量定义"。'
        )
        return prompt, question

    # ------------------------------------------------------------------ #
    #  场景 5：静态代码检查 (Review)
    # ------------------------------------------------------------------ #
    @staticmethod
    def build_review_prompt(rules_text, generated_code):
        """构建静态检查 Review 节点的 prompt"""
        return (
            "你是一个严格的嵌入式C语言静态代码审计专家。请根据以下静态检查规则对提供的代码进行审查。\n\n"
            "【静态检查规则】:\n"
            f"{rules_text}\n\n"
            "【待检查的代码】:\n"
            f"{generated_code}\n\n"
            "【任务要求】:\n"
            "1. 仔细比对代码和每一条规则。\n"
            "2. 如果发现违反规则的地方，请明确指出违反了哪条规则（带上标号），并给出修改建议。\n"
            "3. 即使没有发现问题，也请给出简短的肯定回复（如：代码符合规则，未发现明显的违规）。\n"
            "4. 你的输出内容将作为代码的审查报告，请保持专业、客观、条理清晰。\n"
            "5. 在输出审查报告后，**必须**提供一份修复所有检查问题的完整代码，并使用 ```c 代码内容 ``` 的格式包裹。"
        )

    # ------------------------------------------------------------------ #
    #  辅助：读取专用规则
    # ------------------------------------------------------------------ #
    @staticmethod
    def load_rules_file(rule_path):
        """读取用户指定的规则文件，支持 txt, md, xlsx, xls 返回文本"""
        if not rule_path or not os.path.exists(rule_path):
            return ""
            
        if rule_path.lower().endswith(('.xlsx', '.xls')):
            try:
                import pandas as pd
                df = pd.read_excel(rule_path, engine="openpyxl" if rule_path.endswith(".xlsx") else None)
                df.dropna(how="all", inplace=True)
                
                # 尝试寻找常用表头（如规则、描述、ID等）
                id_col = next((c for c in df.columns if "标号" in str(c) or "规则类型" in str(c).upper()), None)
                desc_col = next((c for c in df.columns if "描述" in str(c) or "规则内容" in str(c) or "规则" in str(c) or "Rule" in str(c)), None)
                
                rules_text = ""
                if id_col and desc_col:
                    rules = []
                    for _, row in df.iterrows():
                        rule_id = str(row[id_col]).strip()
                        rule_desc = str(row[desc_col]).strip()
                        if rule_id and rule_id.lower() != "nan" and rule_desc and rule_desc.lower() != "nan":
                            rules.append(f"- [{rule_id}] {rule_desc}")
                    rules_text = "\n".join(rules)
                else:
                    # 如果没有特定表头，泛型拼接所有非空列
                    rules = []
                    for _, row in df.iterrows():
                        row_items = []
                        for col in df.columns:
                            if "Unnamed" not in str(col):
                                val = str(row[col]).strip()
                                if val and val.lower() != "nan":
                                    row_items.append(f"{col}: {val}")
                        if row_items:
                            rules.append(" | ".join(row_items))
                    rules_text = "\n".join(rules)
                    
                return f"【用户指定专用规则】:\n{rules_text}\n"
            except Exception as e:
                return f"【读取专用规则 Excel 失败】: {e}\n"
        else:
            try:
                with open(rule_path, "r", encoding="utf-8") as f:
                    return f"【用户指定专用规则】:\n{f.read()}\n"
            except Exception:
                return ""

    @staticmethod
    def load_special_variables_file(file_path):
        """读取专用变量的Excel，表头包含 结构体名称 和 结构体内容"""
        if not file_path or not os.path.exists(file_path):
            return ""

        if file_path.lower().endswith(('.xlsx', '.xls')):
            try:
                import pandas as pd
                sheets_dict = pd.read_excel(file_path, sheet_name=None, engine="openpyxl" if file_path.endswith(".xlsx") else None)
                structs = []
                
                for sheet_name, df in sheets_dict.items():
                    df.dropna(how="all", inplace=True)
                    # 寻找我们需要的表头
                    name_col = next((c for c in df.columns if "结构体名称" in str(c)), None)
                    content_col = next((c for c in df.columns if "结构体内容" in str(c)), None)
                    
                    if name_col and content_col:
                        for _, row in df.iterrows():
                            s_name = str(row[name_col]).strip()
                            s_content = str(row[content_col]).strip()
                            if s_name and s_name.lower() != "nan" and s_content and s_content.lower() != "nan":
                                structs.append(f"【结构体】{s_name}\n内容:\n{s_content}\n")
                                
                if structs:
                    structs_text = "\n".join(structs)
                    return f"\n【专用结构体定义(需求可用)】\n{structs_text}\n"
                else:
                    return ""
            except Exception as e:
                return f"\n【读取专用结构体 Excel 失败】: {e}\n"
        return ""

    # ================================================================== #
    #  Private helpers
    # ================================================================== #

    @staticmethod
    def _build_files_instruction(target_files):
        if not target_files:
            return ""
        instruction = "\n【目标文件列表】(请依次生成):\n"
        for f in target_files:
            instruction += f"- {f}\n"
        instruction += (
            "\n【重要：多文件分割格式】\n"
            "请严格按照以下格式输出每个文件的代码，不要合并：\n"
            "/* === FILE_START: src/xxx/filename.c === */\n"
            "...(代码内容)...\n"
            "/* === FILE_END === */\n\n"
        )
        return instruction

    @staticmethod
    def _resolve_req_vars(local_vars, matched_vars_text):
        parsed = (local_vars or "").strip()
        if parsed and parsed not in ("None", "无"):
            return f"{parsed}\n(注：请同时结合 Rules 中检索到的系统级别【全局变量】进行开发)"
        if matched_vars_text and "未配置变量表" not in matched_vars_text:
            return "本需求未定义局部变量，**请严格使用 [Rules] - [全局变量使用指南] 章节中列出的系统变量**。"
        return "无明确变量定义，请根据逻辑自行推断（需符合命名规范）。"
