"""
Tab: 系统设置
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTextEdit, QGroupBox, QFormLayout, QFileDialog, QMessageBox, QComboBox
)
from ui.workers import ConnectionTestThread


class SettingsTab(QWidget):
    """系统设置 Tab"""

    def __init__(self, config, status_label, on_settings_saved_fn):
        super().__init__()
        self.config = config
        self.status_label = status_label
        self.on_settings_saved_fn = on_settings_saved_fn
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 0. 工程环境
        env_group = QGroupBox("0. 工程环境配置")
        env_layout = QHBoxLayout()
        self.proj_root_input = QLineEdit(self.config.project_root)
        self.proj_root_input.setPlaceholderText("生成的代码将写入此目录 (例如 D:/MyProject)")
        browse_root_btn = QPushButton("📂 选择根目录")
        browse_root_btn.clicked.connect(self._browse_project_root)
        env_layout.addWidget(QLabel("工程根目录:"))
        env_layout.addWidget(self.proj_root_input)
        env_layout.addWidget(browse_root_btn)
        env_group.setLayout(env_layout)
        layout.addWidget(env_group)

        # 1. LLM 配置
        llm_group = QGroupBox("1. 对话与代码生成模型 (Chat/Generation)")
        llm_layout = QFormLayout()
        
        # 加载配置
        self.model_profiles = self.config.load_model_profiles()

        self.model_name_input = QComboBox()
        self.model_name_input.setEditable(True)
        # 添加已保存的配置文件名称
        self.model_name_input.addItems(list(self.model_profiles.keys()))
        self.model_name_input.setCurrentText(self.config.model_name)
        self.model_name_input.currentTextChanged.connect(self._on_model_name_changed)

        self.host_input = QLineEdit(self.config.host)
        self.host_input.setPlaceholderText("例如: api.example.com (用于 Host HTTP Header，可为空)")
        
        self.api_url_input = QLineEdit(self.config.api_url)
        self.api_url_input.setPlaceholderText("例如: http://192.168.51.3:28080/v1/chat/completions")
        
        self.api_key_input = QLineEdit(self.config.api_key)
        self.api_key_input.setEchoMode(QLineEdit.Password)
        
        llm_layout.addRow("模型名称:", self.model_name_input)
        llm_layout.addRow("Host:", self.host_input)
        llm_layout.addRow("Base URL:", self.api_url_input)
        llm_layout.addRow("API Key:", self.api_key_input)

        self.test_api_btn = QPushButton("🔌 测试 LLM 连接")
        self.test_api_btn.clicked.connect(self._test_connection)
        llm_layout.addRow("", self.test_api_btn)
        llm_group.setLayout(llm_layout)
        layout.addWidget(llm_group)

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
        layout.addWidget(embed_group)

        # 保存按钮
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("💾 保存所有配置")
        save_btn.setStyleSheet("font-weight: bold; color: white; background-color: #0078d7; padding: 8px;")
        save_btn.clicked.connect(self._save_settings)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

        # 提示词模板
        layout.addWidget(QLabel("<hr>"))
        layout.addWidget(QLabel("<b>提示词模板 (Prompt)</b>"))
        self.prompt_template_edit = QTextEdit()
        self.prompt_template_edit.setPlainText(self.config.prompt_template)
        self.prompt_template_edit.setMinimumHeight(150)
        layout.addWidget(self.prompt_template_edit, 1)

        save_prompt_btn = QPushButton("保存提示词模板")
        save_prompt_btn.clicked.connect(self._save_prompt)
        layout.addWidget(save_prompt_btn)
        layout.addStretch()

    # ------------------------------------------------------------------ #
    #  连接测试
    # ------------------------------------------------------------------ #
    def _on_model_name_changed(self, text):
        if text in self.model_profiles:
            profile = self.model_profiles[text]
            self.host_input.setText(profile.get("host", ""))
            self.api_url_input.setText(profile.get("api_url", ""))
            self.api_key_input.setText(profile.get("api_key", ""))

    def _test_connection(self):
        url = self.api_url_input.text().strip()
        key = self.api_key_input.text().strip()
        model = self.model_name_input.currentText().strip()
        host = self.host_input.text().strip()
        if not url or not model:
            QMessageBox.warning(self, "提示", "请先填写 Base URL 和 模型名称")
            return

        self.test_api_btn.setEnabled(False)
        self.test_api_btn.setText("正在连接...")
        self.status_label.setText("正在测试 API 连接...")

        self.test_thread = ConnectionTestThread(url, key, model, host)
        self.test_thread.finished_signal.connect(self._on_test_finished)
        self.test_thread.start()

    def _on_test_finished(self, success, message):
        self.test_api_btn.setEnabled(True)
        self.test_api_btn.setText("🔌 测试 LLM 连接")
        if success:
            self.status_label.setText("API 连接测试通过")
            QMessageBox.information(self, "成功", message)
        else:
            self.status_label.setText("API 连接测试失败")
            QMessageBox.critical(self, "连接错误", message)

    # ------------------------------------------------------------------ #
    #  保存
    # ------------------------------------------------------------------ #
    def _save_settings(self):
        # 保存到 config.json
        self.config.api_url = self.api_url_input.text().strip()
        self.config.api_key = self.api_key_input.text().strip()
        self.config.model_name = self.model_name_input.currentText().strip()
        self.config.host = self.host_input.text().strip()
        self.config.embed_api_url = self.embed_url_input.text().strip()
        self.config.embed_api_key = self.embed_key_input.text().strip()
        self.config.embed_model_name = self.embed_model_input.text().strip()
        self.config.project_root = self.proj_root_input.text().strip()
        self.config.save_config()

        # 保存到 cfg/models.json
        if self.config.model_name:
            profile_data = {
                "host": self.config.host,
                "api_url": self.config.api_url,
                "api_key": self.config.api_key
            }
            self.config.save_model_profile(self.config.model_name, profile_data)
            # 更新当前内存中的 profile
            self.model_profiles[self.config.model_name] = profile_data
            if self.model_name_input.findText(self.config.model_name) == -1:
                self.model_name_input.addItem(self.config.model_name)

        self.on_settings_saved_fn()
        QMessageBox.information(self, "保存成功", "配置已保存！\n注意：如果修改了 Embedding 配置，请重启软件以生效。")

    def _save_prompt(self):
        self.config.prompt_template = self.prompt_template_edit.toPlainText()
        self.config.save_config()
        QMessageBox.information(self, "保存", "提示词模板已更新并保存到本地")

    def _browse_project_root(self):
        directory = QFileDialog.getExistingDirectory(self, "选择工程根目录")
        if directory:
            self.proj_root_input.setText(directory)
