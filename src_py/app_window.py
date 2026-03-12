import sys
import os
import re
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTextEdit, QFileDialog, QTabWidget, QCheckBox,
    QComboBox, QMessageBox, QGroupBox, QFormLayout,
    QListWidget, QListWidgetItem, QAbstractItemView,
    QSplitter
)
from PyQt5.QtCore import Qt, QEvent

# === 导入拆分后的模块 ===
from config import ConfigManager
from rag_core import RAGManager
from net_workers import ConnectionTestThread, GenerationThread
from pipeline import PipelineTab
from ui_widgets import ChatBubble, AutoExpandTextEdit, CCppHighlighter
from test_rag import VariableTestTab

class AICoderApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = ConfigManager()
        self.rag_manager = RAGManager(
            self.config.embed_api_url,
            embed_api_key=self.config.embed_api_key,
            embed_model_name=self.config.embed_model_name
        )

        self.setWindowTitle("AI Coding Assistant (Win7 Compatible - Modular)")
        self.resize(1000, 700)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self.init_generation_tab()
        self.init_pipeline_tab()
        self.init_rag_tab()
        self.init_settings_tab()
        self.init_qa_tab()
        self.init_variable_test_tab() 
        self.status_label = QLabel("就绪")
        self.statusBar().addWidget(self.status_label)

    # ----------------- 需求解析 ----------------- #
    def parse_requirement_text(self, full_text):
        data = {
            "req_id": "N/A",
            "req_name": "General Task",
            "req_content": full_text,
            "req_vars": "None",
            "req_ref_code": "None"
        }
        match_id = re.search(r"需求id[：:]\s*(.*?)\n", full_text, re.IGNORECASE)
        if match_id:
            data["req_id"] = match_id.group(1).strip()

        match_name = re.search(r"需求名称[：:]\s*(.*?)\n", full_text, re.IGNORECASE)
        if match_name:
            data["req_name"] = match_name.group(1).strip()

        match_content = re.search(r"需求内容[：:]\s*(.*?)\n\s*变量[：:]", full_text, re.IGNORECASE | re.DOTALL)
        if match_content:
            data["req_content"] = match_content.group(1).strip()

        match_vars = re.search(r"变量[：:]\s*(.*?)\n\s*参考代码[：:]", full_text, re.IGNORECASE | re.DOTALL)
        if match_vars:
            data["req_vars"] = match_vars.group(1).strip()

        match_ref = re.search(r"参考代码[：:]\s*(.*)", full_text, re.IGNORECASE | re.DOTALL)
        if match_ref:
            data["req_ref_code"] = match_ref.group(1).strip()

        return data

    # ----------------- Tab1: 代码生成 ----------------- #
    def init_generation_tab(self):
        tab = QWidget()
        layout = QHBoxLayout(tab)

        # 左侧：输入区
        input_panel = QWidget()
        input_layout = QVBoxLayout(input_panel)

        # 1. 需求文件
        req_group = QGroupBox("1. 需求文件")
        req_layout = QVBoxLayout()
        self.req_path_edit = QLineEdit()
        self.req_path_edit.setPlaceholderText("选择需求文档 (.txt, .md)...")

        req_btn = QPushButton("📂 浏览...")
        req_btn.setCursor(Qt.PointingHandCursor)
        req_btn.clicked.connect(lambda: self.browse_file(self.req_path_edit))

        req_layout.addWidget(self.req_path_edit)
        req_layout.addWidget(req_btn)

        self.req_text_edit = QTextEdit()
        self.req_text_edit.setPlaceholderText("或者直接在此处输入详细需求...")
        req_layout.addWidget(self.req_text_edit)
        req_group.setLayout(req_layout)
        input_layout.addWidget(req_group)

        # 2. 规则文件
        rule_group = QGroupBox("2. 特定编码规则 (可选)")
        rule_layout = QHBoxLayout()
        self.rule_path_edit = QLineEdit()
        rule_btn = QPushButton("📂 浏览...")
        rule_btn.setCursor(Qt.PointingHandCursor)
        rule_btn.clicked.connect(lambda: self.browse_file(self.rule_path_edit))
        rule_layout.addWidget(self.rule_path_edit)
        rule_layout.addWidget(rule_btn)
        rule_group.setLayout(rule_layout)
        input_layout.addWidget(rule_group)

        # 3. RAG 增强
        kb_group = QGroupBox("3. RAG 增强 (多选)")
        kb_layout = QVBoxLayout()
        self.use_rag_cb = QCheckBox("启用知识库增强")
        kb_layout.addWidget(self.use_rag_cb)
        self.kb_list_widget_gen = QListWidget()
        self.kb_list_widget_gen.setMaximumHeight(100)
        self.kb_list_widget_gen.setStyleSheet("""
            QListWidget { border: 1px solid #ccc; border-radius: 4px; background: white; }
            QListWidget::item { padding: 4px; }
            QListWidget::item:hover { background: #f0f0f0; }
        """)
        self.refresh_kb_selector_items()
        kb_layout.addWidget(self.kb_list_widget_gen)
        kb_group.setLayout(kb_layout)
        input_layout.addWidget(kb_group)

        # 4. 模型显示
        model_group = QGroupBox("4. 模型选择")
        model_layout = QHBoxLayout()
        self.model_label_display = QLabel(f"当前: {self.config.model_name}")
        model_layout.addWidget(self.model_label_display)
        model_group.setLayout(model_layout)
        input_layout.addWidget(model_group)

        # 生成按钮
        self.gen_btn = QPushButton("🚀 生成代码")
        self.gen_btn.setCursor(Qt.PointingHandCursor)
        self.gen_btn.setStyleSheet("""
            QPushButton {
                font-size: 16px;
                font-weight: bold;
                padding: 10px;
                background-color: #0078d7;
                color: white;
                border-radius: 5px;
                border: none;
            }
            QPushButton:hover { background-color: #0063b1; }
            QPushButton:pressed { background-color: #005a9e; }
            QPushButton:disabled { background-color: #ccc; }
        """)
        self.gen_btn.clicked.connect(self.start_generation)
        input_layout.addWidget(self.gen_btn)
        input_layout.addStretch()

        # 右侧：输出区
        output_splitter = QSplitter(Qt.Vertical)

        # 上：完整分析
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.addWidget(QLabel("<b>🧠 完整分析与推理 (Analysis):</b>"))
        self.result_area = QTextEdit()
        self.result_area.setReadOnly(True)
        self.result_area.setStyleSheet("font-family: Consolas; font-size: 13px; color: #555;")
        self.result_area.installEventFilter(self)
        top_layout.addWidget(self.result_area)
        output_splitter.addWidget(top_widget)

        # 下：纯代码
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        code_header = QHBoxLayout()
        code_header.addWidget(QLabel("<b>💻 纯代码 (Clean Code):</b> "))
        code_header.addStretch()
        copy_btn = QPushButton("📋 一键复制")
        copy_btn.setFixedWidth(110)
        copy_btn.setCursor(Qt.PointingHandCursor)
        copy_btn.clicked.connect(self.copy_code_to_clipboard)
        code_header.addWidget(copy_btn)
        bottom_layout.addLayout(code_header)

        self.code_area = QTextEdit()
        self.code_area.setReadOnly(True)
        self.code_area.setStyleSheet("""
            QTextEdit {
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 14px;
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #333;
                padding: 5px;
            }
        """)
        self.highlighter = CCppHighlighter(self.code_area.document())
        self.code_area.installEventFilter(self)
        bottom_layout.addWidget(self.code_area)
        output_splitter.addWidget(bottom_widget)

        output_splitter.setStretchFactor(0, 4)
        output_splitter.setStretchFactor(1, 6)

        # 左右 splitter
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(input_panel)
        splitter.addWidget(output_splitter)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter)

        self.tabs.addTab(tab, "代码生成")

    # ----------------- Tab2: 知识库管理 ----------------- #
    def init_rag_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # 1. 当前知识库列表
        layout.addWidget(QLabel("<b>当前已索引的知识库:</b>"))
        self.kb_list_widget = QTextEdit()
        self.kb_list_widget.setReadOnly(True)
        self.kb_list_widget.setMaximumHeight(140)
        self.refresh_kb_list()
        layout.addWidget(self.kb_list_widget)

        layout.addSpacing(30)

        # 2. 维护区
        maintenance_group = QGroupBox("⚠️ 数据库维护与初始化 (更换模型后必读)")
        maintenance_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #FF9800;
                border-radius: 6px;
                margin-top: 20px;
                font-size: 16px;
                background-color: #FFFBF5;
            }
            QGroupBox::title {
                color: #E65100;
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 10px;
                padding: 0 5px;
                background-color: transparent;
                font-weight: bold;
            }
        """)
        m_layout = QVBoxLayout()
        m_layout.setContentsMargins(20, 20, 20, 20)
        m_layout.setSpacing(15)

        hint_label = QLabel(
            "<span style='color:#555;'>提示：若更换了 Embedding 模型，会导致<b>“维度不匹配”</b>错误。</span><br>"
            "<span style='color:#E65100;'>操作顺序：先点击 [清空所有数据] -> 再点击 [一键导入]</span>"
        )
        hint_label.setWordWrap(True)
        hint_label.setStyleSheet("font-size: 14px; line-height: 1.5;")
        m_layout.addWidget(hint_label)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(20)

        self.reset_db_btn = QPushButton("🗑️ 清空所有数据")
        self.reset_db_btn.setMinimumHeight(38)
        self.reset_db_btn.setCursor(Qt.PointingHandCursor)
        self.reset_db_btn.setStyleSheet("""
            QPushButton {
                background-color: #FFF0F0;
                color: #D9534F;
                border: 1px solid #D9534F;
                border-radius: 5px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #FFDddD; }
        """)
        self.reset_db_btn.clicked.connect(self.reset_all_database)

        self.import_gjb_btn = QPushButton("📚 一键导入 GJB 5369 默认库")
        self.import_gjb_btn.setMinimumHeight(38)
        self.import_gjb_btn.setCursor(Qt.PointingHandCursor)
        self.import_gjb_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d7;
                color: white;
                border: none;
                border-radius: 5px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #0063b1; }
        """)
        self.import_gjb_btn.clicked.connect(self.load_default_gjb_kb)

        btn_layout.addWidget(self.reset_db_btn)
        btn_layout.addWidget(self.import_gjb_btn)
        m_layout.addLayout(btn_layout)

        maintenance_group.setLayout(m_layout)
        layout.addWidget(maintenance_group)

        # 3. 上传新文档
        upload_group = QGroupBox("上传新文档")
        upload_group.setStyleSheet("QGroupBox { margin-top: 20px; font-weight: bold; }")
        form_layout = QFormLayout()
        form_layout.setContentsMargins(10, 25, 10, 10)
        form_layout.setVerticalSpacing(12)

        self.new_kb_file = QLineEdit()
        self.new_kb_file.setMinimumHeight(30)
        self.new_kb_file.setPlaceholderText("支持 .txt, .md, .json 等")

        browse_kb = QPushButton("📂 浏览...")
        browse_kb.setFixedSize(80, 30)
        browse_kb.clicked.connect(lambda: self.browse_file(self.new_kb_file))

        file_layout = QHBoxLayout()
        file_layout.addWidget(self.new_kb_file)
        file_layout.addWidget(browse_kb)

        self.new_kb_name = QLineEdit()
        self.new_kb_name.setMinimumHeight(30)
        self.new_kb_name.setPlaceholderText("例如: 项目需求文档_V1.0")

        upload_btn = QPushButton("⬆️ 上传并建立索引")
        upload_btn.setMinimumHeight(35)
        upload_btn.setStyleSheet("font-weight: bold;")
        upload_btn.clicked.connect(self.upload_knowledge_base)

        form_layout.addRow("文件路径:", file_layout)
        form_layout.addRow("知识库名:", self.new_kb_name)
        form_layout.addRow("", upload_btn)

        upload_group.setLayout(form_layout)
        layout.addWidget(upload_group)

        # 4. 删除单个知识库
        delete_layout = QHBoxLayout()
        delete_layout.setContentsMargins(0, 15, 0, 0)

        self.del_kb_combo = QComboBox()
        self.del_kb_combo.setMinimumHeight(30)
        self.del_kb_combo.addItems(self.rag_manager.knowledge_bases)

        del_single_btn = QPushButton("删除选中的知识库")
        del_single_btn.setMinimumHeight(30)
        del_single_btn.setStyleSheet("color: #d9534f;")
        del_single_btn.clicked.connect(self.delete_knowledge_base)

        delete_layout.addWidget(QLabel("单独删除:"))
        delete_layout.addWidget(self.del_kb_combo, 1)
        delete_layout.addWidget(del_single_btn)

        layout.addLayout(delete_layout)
        layout.addStretch()

        self.tabs.addTab(tab, "知识库管理")

    # 清空数据库
    def reset_all_database(self):
        reply = QMessageBox.question(
            self, '高风险操作',
            "⚠️ 确定要清空所有知识库吗？\n\n执行此操作将删除本地 chroma_db 文件夹下的所有索引数据。\n如果您刚更换了 Embedding 模型，必须执行此操作。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            success, msg = self.rag_manager.reset_database()
            if success:
                self.refresh_kb_list()
                QMessageBox.information(self, "成功", "数据库已清空，现在可以重新导入数据了~")
            else:
                QMessageBox.critical(self, "失败", f"操作失败: {msg}")

    # 导入默认 GJB
    def load_default_gjb_kb(self):
        if not self.rag_manager.embedding_fn:
            QMessageBox.warning(self, "错误", "Embedding 服务未初始化，请检查系统设置。")
            return

        self.status_label.setText("正在后台处理 GJB 5369 规则库...")
        QApplication.processEvents()

        try:
            self.rag_manager.init_default_kb()
            self.refresh_kb_list()
            self.status_label.setText("导入完成")
            QMessageBox.information(self, "成功", "GJB 5369-2005 默认库导入成功！")
        except Exception as e:
            self.status_label.setText("导入失败")
            QMessageBox.critical(self, "维度错误", f"导入失败: {str(e)}\n\n请先点击【清空所有数据】按钮再试。")

    # ----------------- Tab3: 系统设置 ----------------- #
    def start_test_connection(self):
        url = self.api_url_input.text().strip()
        key = self.api_key_input.text().strip()
        model = self.model_name_input.text().strip()

        if not url or not model:
            QMessageBox.warning(self, "提示", "请先填写 Base URL 和 模型名称")
            return

        self.test_api_btn.setEnabled(False)
        self.test_api_btn.setText("正在连接...")
        self.status_label.setText("正在测试 API 连接...")

        self.test_thread = ConnectionTestThread(url, key, model)
        self.test_thread.finished_signal.connect(self.on_test_finished)
        self.test_thread.start()

    def on_test_finished(self, success, message):
        self.test_api_btn.setEnabled(True)
        self.test_api_btn.setText("🔌 测试 LLM 连接")

        if success:
            self.status_label.setText("API 连接测试通过")
            QMessageBox.information(self, "成功", message)
        else:
            self.status_label.setText("API 连接测试失败")
            QMessageBox.critical(self, "连接错误", message)

    def init_settings_tab(self):
        tab = QWidget()
        main_layout = QVBoxLayout(tab)

        #v2 updates
        env_group = QGroupBox("0. 工程环境配置")
        env_layout = QHBoxLayout()
        self.proj_root_input = QLineEdit(self.config.project_root)
        self.proj_root_input.setPlaceholderText("生成的代码将写入此目录 (例如 D:/MyProject)")
        
        browse_root_btn = QPushButton("📂 选择根目录")
        browse_root_btn.clicked.connect(self.browse_project_root)
        
        env_layout.addWidget(QLabel("工程根目录:"))
        env_layout.addWidget(self.proj_root_input)
        env_layout.addWidget(browse_root_btn)
        env_group.setLayout(env_layout)
        main_layout.addWidget(env_group)

        # 1. LLM 配置
        llm_group = QGroupBox("1. 对话与代码生成模型 (Chat/Generation)")
        llm_layout = QFormLayout()

        self.api_url_input = QLineEdit(self.config.api_url)
        self.api_url_input.setPlaceholderText("例如: http://192.168.51.3:28080/v1/chat/completions")

        self.api_key_input = QLineEdit(self.config.api_key)
        self.api_key_input.setEchoMode(QLineEdit.Password)

        self.model_name_input = QLineEdit(self.config.model_name)

        llm_layout.addRow("Base URL:", self.api_url_input)
        llm_layout.addRow("API Key:", self.api_key_input)
        llm_layout.addRow("模型名称:", self.model_name_input)

        self.test_api_btn = QPushButton("🔌 测试 LLM 连接")
        self.test_api_btn.clicked.connect(self.start_test_connection)
        llm_layout.addRow("", self.test_api_btn)

        llm_group.setLayout(llm_layout)
        main_layout.addWidget(llm_group)

        # 2. Embedding 配置
        embed_group = QGroupBox("2. 知识库嵌入模型 (Embedding)")
        embed_layout = QFormLayout()

        self.embed_url_input = QLineEdit(self.config.embed_api_url)
        self.embed_url_input.setPlaceholderText("例如: http://192.168.51.3:28080/embed")

        self.embed_key_input = QLineEdit(self.config.embed_api_key)
        self.embed_key_input.setEchoMode(QLineEdit.Password)

        self.embed_model_input = QLineEdit(self.config.embed_model_name)
        self.embed_model_input.setPlaceholderText("例如: qwen3-embedding:latest")

        embed_layout.addRow("Embed URL:", self.embed_url_input)
        embed_layout.addRow("Embed Key:", self.embed_key_input)
        embed_layout.addRow("Embed Model:", self.embed_model_input)

        embed_group.setLayout(embed_layout)
        main_layout.addWidget(embed_group)

        # 底部保存按钮
        btn_layout = QHBoxLayout()
        save_api_btn = QPushButton("💾 保存所有配置")
        save_api_btn.setStyleSheet("font-weight: bold; color: white; background-color: #0078d7; padding: 8px;")
        save_api_btn.clicked.connect(self.save_api_settings)
        btn_layout.addWidget(save_api_btn)
        main_layout.addLayout(btn_layout)

        # 提示词模板
        main_layout.addWidget(QLabel("<hr>"))
        main_layout.addWidget(QLabel("<b>提示词模板 (Prompt)</b>"))

        self.prompt_template_edit = QTextEdit()
        self.prompt_template_edit.setPlainText(self.config.prompt_template)
        self.prompt_template_edit.setMinimumHeight(150)
        main_layout.addWidget(self.prompt_template_edit, 1)

        save_prompt_btn = QPushButton("保存提示词模板")
        save_prompt_btn.clicked.connect(self.save_prompt_settings)
        main_layout.addWidget(save_prompt_btn)

        main_layout.addStretch()
        self.tabs.addTab(tab, "系统设置")

    def browse_project_root(self):
        directory = QFileDialog.getExistingDirectory(self, "选择工程根目录")
        if directory:
            self.proj_root_input.setText(directory)

    # ----------------- Tab4: 智能问答 ----------------- #
    def refresh_qa_kb_items(self):
        if not hasattr(self, 'qa_kb_list_widget'):
            return

        self.qa_kb_list_widget.clear()
        kbs = self.rag_manager.knowledge_bases
        for kb in kbs:
            item = QListWidgetItem(kb)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            if kb == "GJB_5369_2005":
                item.setCheckState(Qt.Checked)
            else:
                item.setCheckState(Qt.Unchecked)
            self.qa_kb_list_widget.addItem(item)

    def init_qa_tab(self):
        """初始化智能问答 Tab (聊天流模式)"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 1. 聊天记录显示区
        self.chat_history_list = QListWidget()
        self.chat_history_list.setStyleSheet("""
            QListWidget {
                background-color: #F5F5F5;
                border: none;
                outline: none;
            }
            QListWidget::item {
                background-color: transparent;
            }
            QListWidget::item:hover {
                background-color: transparent;
            }
            QListWidget::item:selected {
                background-color: transparent;
            }
        """)
        self.chat_history_list.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        layout.addWidget(self.chat_history_list)

        # 2. 知识库设置区
        controls_group = QGroupBox("知识库设置 (多选)")
        controls_group.setMaximumHeight(100)
        controls_layout = QHBoxLayout()

        self.qa_use_rag_cb = QCheckBox("启用知识库参考")
        controls_layout.addWidget(self.qa_use_rag_cb)

        self.qa_kb_list_widget = QListWidget()
        self.qa_kb_list_widget.setStyleSheet("""
            QListWidget { border: 1px solid #ccc; border-radius: 4px; background: white; }
            QListWidget::item { padding: 2px; }
            QListWidget::item:hover { background: #f0f0f0; }
        """)
        self.refresh_qa_kb_items()
        controls_layout.addWidget(self.qa_kb_list_widget)

        controls_group.setLayout(controls_layout)
        layout.addWidget(controls_group)

        # 3. 底部输入区
        input_container = QWidget()
        input_container.setStyleSheet("background-color: #FFFFFF; border-top: 1px solid #E0E0E0;")
        input_layout = QHBoxLayout(input_container)
        input_layout.setContentsMargins(10, 10, 10, 10)

        self.qa_input_area = AutoExpandTextEdit()
        self.qa_input_area.setPlaceholderText("💡在此输入你的问题 (Ctrl+Enter 发送)...")
        self.qa_input_area.submit_signal.connect(self.start_qa_generation)

        self.qa_send_btn = QPushButton("发送")
        self.qa_send_btn.setFixedSize(80, 36)
        self.qa_send_btn.setStyleSheet("""
            QPushButton {
                background-color: #07C160;
                color: white;
                font-weight: bold;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #06AD56; }
            QPushButton:pressed { background-color: #059B4C; }
            QPushButton:disabled { background-color: #A0E0B0; }
        """)
        self.qa_send_btn.clicked.connect(self.start_qa_generation)

        input_layout.addWidget(self.qa_input_area)
        input_layout.addWidget(self.qa_send_btn, 0, Qt.AlignBottom)
        layout.addWidget(input_container)

        self.tabs.addTab(tab, "智能问答")

    def add_chat_message(self, text, is_user):
        bubble = ChatBubble(text, is_user)
        item = QListWidgetItem()
        item.setSizeHint(bubble.sizeHint())
        self.chat_history_list.addItem(item)
        self.chat_history_list.setItemWidget(item, bubble)
        self.chat_history_list.scrollToBottom()

    def start_qa_generation(self):
        question = self.qa_input_area.toPlainText().strip()
        if not question:
            return

        self.add_chat_message(question, is_user=True)
        self.qa_input_area.clear()

        selected_kbs = []
        if self.qa_use_rag_cb.isChecked():
            count = self.qa_kb_list_widget.count()
            for i in range(count):
                item = self.qa_kb_list_widget.item(i)
                if item.checkState() == Qt.Checked:
                    selected_kbs.append(item.text())

        context = ""
        kb_names_str = ",".join(selected_kbs) if selected_kbs else "无"

        if selected_kbs:
            self.status_label.setText(f"正在检索 {len(selected_kbs)} 个知识库...")
            QApplication.processEvents()

            combined_results = []
            for kb_name in selected_kbs:
                res = self.rag_manager.recall(question, kb_name)
                if res and "未找到" not in res:
                    combined_results.append(f"【来源: 知识库 {kb_name}】\n{res}")

            if combined_results:
                context = "\n\n".join(combined_results)
            else:
                context = "（检索了所选知识库，但未发现高度相关的内容）"

        if context and "未发现高度相关" not in context:
            prompt = (
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
            prompt = (
                f"你是一个专业的助手。\n"
                f"【用户问题】: {question}\n\n"
                f"请直接回答问题，条理清晰。"
            )

        self.qa_send_btn.setEnabled(False)
        self.qa_send_btn.setText("思考中...")
        current_model = self.config.model_name
        self.status_label.setText(f"[{current_model}] 正在思考...")

        self.qa_thread = GenerationThread(
            self.config.api_url,
            self.config.api_key,
            self.config.model_name,
            prompt
        )
        self.qa_thread.finished_signal.connect(self.on_qa_finished)
        self.qa_thread.error_signal.connect(self.on_qa_error)
        self.qa_thread.start()

    def on_qa_finished(self, text):
        self.add_chat_message(text, is_user=False)
        self.qa_send_btn.setEnabled(True)
        self.qa_send_btn.setText("发送")
        self.status_label.setText("回答完成")
        self.qa_input_area.setFocus()

    def on_qa_error(self, error_msg):
        self.add_chat_message(f"❌ 请求出错: {error_msg}", is_user=False)
        self.qa_send_btn.setEnabled(True)
        self.qa_send_btn.setText("发送")
        self.status_label.setText("出错")

    # ----------------- Tab5: 流水线生成 ----------------- #
    def init_pipeline_tab(self):
        self.pipeline_tab = PipelineTab(self) # 传入 self 作为 parent app
        self.tabs.addTab(self.pipeline_tab, "流水线生成")

    def init_variable_test_tab(self):
        self.var_test_tab = VariableTestTab(self)
        self.tabs.addTab(self.var_test_tab, "变量表测试")

    # ----------------- 通用辅助函数 ----------------- #
    def browse_file(self, line_edit):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择文件")
        if file_path:
            line_edit.setText(file_path)

    def refresh_kb_selector_items(self):
        if not hasattr(self, 'kb_list_widget_gen'):
            return

        self.kb_list_widget_gen.clear()
        kbs = self.rag_manager.knowledge_bases
        for kb in kbs:
            item = QListWidgetItem(kb)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            if kb == "GJB_5369_2005":
                item.setCheckState(Qt.Checked)
            self.kb_list_widget_gen.addItem(item)

    def refresh_kb_list(self):
        kbs = self.rag_manager.knowledge_bases
        content = "\n".join([f"- {kb}" for kb in kbs])
        self.kb_list_widget.setText(content)
        if hasattr(self, 'del_kb_combo'):
            self.del_kb_combo.clear()
            self.del_kb_combo.addItems(kbs)
        self.refresh_kb_selector_items()
        self.refresh_qa_kb_items()

    def upload_knowledge_base(self):
        path = self.new_kb_file.text()
        name = self.new_kb_name.text()
        if not path or not name:
            QMessageBox.warning(self, "错误", "请填写文件路径和知识库名称")
            return

        self.status_label.setText("正在向量化处理(Embedding)...")
        QApplication.processEvents()

        success, msg = self.rag_manager.add_to_kb(path, name)

        if success:
            self.refresh_kb_list()
            QMessageBox.information(self, "成功", msg)
            self.status_label.setText("知识库就绪")
        else:
            QMessageBox.critical(self, "失败", f"处理出错: {msg}")
            self.status_label.setText("处理失败")

    def delete_knowledge_base(self):
        name = self.del_kb_combo.currentText()
        if self.rag_manager.delete_kb(name):
            self.refresh_kb_list()
            QMessageBox.information(self, "成功", f"已删除知识库: {name}")

    def save_api_settings(self):
        self.config.api_url = self.api_url_input.text().strip()
        self.config.api_key = self.api_key_input.text().strip()
        self.config.model_name = self.model_name_input.text().strip()
        self.config.embed_api_url = self.embed_url_input.text().strip()
        self.config.embed_api_key = self.embed_key_input.text().strip()
        self.config.embed_model_name = self.embed_model_input.text().strip()
        self.config.project_root = self.proj_root_input.text().strip()

        self.model_label_display.setText(f"当前: {self.config.model_name}")
        self.config.save_config()
        QMessageBox.information(self, "保存成功", "配置已保存！\n注意：如果修改了 Embedding 配置，请重启软件以生效。")

    def save_prompt_settings(self):
        self.config.prompt_template = self.prompt_template_edit.toPlainText()
        self.config.save_config()
        QMessageBox.information(self, "保存", "提示词模板已更新并保存到本地")

    def start_generation(self):
        req_content = self.req_text_edit.toPlainText()
        req_file = self.req_path_edit.text()
        if req_file and os.path.exists(req_file):
            try:
                with open(req_file, 'r', encoding='utf-8') as f:
                    req_content += "\n" + f.read()
            except Exception as e:
                QMessageBox.warning(self, "错误", f"读取需求文件失败: {e}")
                return

        if not req_content.strip():
            QMessageBox.warning(self, "提示", "请输入需求或上传需求文件")
            return

        rules_content = ""
        rule_file = self.rule_path_edit.text()
        if rule_file and os.path.exists(rule_file):
            try:
                with open(rule_file, 'r', encoding='utf-8') as f:
                    rules_content += f"【用户上传规则】:\n{f.read()}\n\n"
            except Exception:
                pass

        gjb_kb_name = "GJB_5369_2005"
        rag_context = "无外部知识库上下文"

        if self.use_rag_cb.isChecked():
            selected_kbs = []
            count = self.kb_list_widget_gen.count()
            for i in range(count):
                item = self.kb_list_widget_gen.item(i)
                if item.checkState() == Qt.Checked:
                    selected_kbs.append(item.text())

            if not selected_kbs:
                self.status_label.setText("提示：未选择任何知识库，将仅使用通用模型生成...")
            combined_context = []
            for kb_name in selected_kbs:
                self.status_label.setText(f"正在从知识库 [{kb_name}] 检索...")
                QApplication.processEvents()
                content = self.rag_manager.recall(req_content[:300], kb_name)

                if kb_name == gjb_kb_name:
                    if "未找到" not in content:
                        rules_content += f"\n【GJB 5369-2005 自动检索】:\n{content}\n"
                else:
                    if "未找到" not in content:
                        combined_context.append(f"--- 来源: {kb_name} ---\n{content}")

            if combined_context:
                rag_context = "\n\n".join(combined_context)

        if not rules_content:
            rules_content = "无特定规则，请遵循 GJB 5369-2005 通用标准。"

        parsed_req = self.parse_requirement_text(req_content)
        try:
            final_prompt = self.config.prompt_template.format(
                rules=rules_content,
                context=rag_context,
                **parsed_req,
                requirements=req_content
            )
        except KeyError:
            final_prompt = self.config.prompt_template.format(
                rules=rules_content,
                context=rag_context,
                **parsed_req,
                requirements=req_content
            )

        self.gen_btn.setEnabled(False)
        self.result_area.setText("正在生成代码(已拆分需求结构)...")
        self.code_area.setText("/*等待生成新的代码...*/")
        current_model = self.config.model_name
        self.status_label.setText(f"正在调用 {current_model} 生成代码...")

        self.thread = GenerationThread(
            self.config.api_url,
            self.config.api_key,
            self.config.model_name,
            final_prompt
        )
        self.thread.finished_signal.connect(self.on_generation_finished)
        self.thread.error_signal.connect(self.on_generation_error)
        self.thread.start()

    def extract_code_blocks(self, text):
        pattern = r"```(?:\w+)?\s*(.*?)```"
        matches = re.findall(pattern, text, re.DOTALL)
        if matches:
            return "\n\n".join(matches)
        else:
            return "// 未检测到标准 Markdown 代码块，请查看上方完整回复。"

    def copy_code_to_clipboard(self):
        code = self.code_area.toPlainText()
        if code:
            clipboard = QApplication.clipboard()
            clipboard.setText(code)
            self.status_label.setText("代码已复制到剪贴板！")
        else:
            QMessageBox.warning(self, "提示", "没有代码可复制")

    def on_generation_finished(self, text):
        self.result_area.setText(text)
        clean_code = self.extract_code_blocks(text)
        self.code_area.setText(clean_code)
        self.gen_btn.setEnabled(True)
        self.status_label.setText("生成完成")

    def on_generation_error(self, error_msg):
        self.result_area.setText(f"生成失败: {error_msg}\n\n请检查 '系统设置' 中的 API URL.")
        self.gen_btn.setEnabled(True)
        self.status_label.setText("出错")

    def eventFilter(self, source, event):
        targets = [self.result_area]
        if hasattr(self, 'code_area'):
            targets.append(self.code_area)

        if source in targets and event.type() == QEvent.Wheel:
            if event.modifiers() & Qt.ControlModifier:
                if event.angleDelta().y() > 0:
                    source.zoomIn(1)
                else:
                    source.zoomOut(1)
                return True
        return super().eventFilter(source, event)