"""
主窗口 —— 仅负责组装各 Tab，不包含业务逻辑。
"""

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QLabel, QTabWidget, QFileDialog,
)

from backend.config import ConfigManager
from backend.rag_core import RAGManager

from ui.tab_generation import GenerationTab
from ui.tab_kb import KBManageTab
from ui.tab_settings import SettingsTab
from ui.tab_qa import QATab
from ui.tab_pipeline import PipelineTab
from ui.tab_var_test import VariableTestTab


class AICoderApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = ConfigManager()
        self.rag_manager = RAGManager(
            self.config.embed_api_url,
            embed_api_key=self.config.embed_api_key,
            embed_model_name=self.config.embed_model_name,
        )

        self.setWindowTitle("AI Coding Assistant (Win7 Compatible - Modular)")
        self.resize(1000, 700)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self.status_label = QLabel("就绪")
        self.statusBar().addWidget(self.status_label)

        self._init_tabs()

    def _init_tabs(self):
        # Tab1: 代码生成
        self.gen_tab = GenerationTab(
            self.config, self.rag_manager, self.status_label, self._browse_file
        )
        self.tabs.addTab(self.gen_tab, "代码生成")

        # Tab2: 流水线生成
        self.pipeline_tab = PipelineTab(
            self.config, self.rag_manager, self.status_label,
            rule_path_fn=lambda: self.gen_tab.rule_path_edit.text().strip(),
        )
        self.tabs.addTab(self.pipeline_tab, "流水线生成")

        # Tab3: 知识库管理
        self.kb_tab = KBManageTab(
            self.config, self.rag_manager, self.status_label,
            self._browse_file, self._refresh_all_kbs,
        )
        self.tabs.addTab(self.kb_tab, "知识库管理")

        # Tab4: 系统设置
        self.settings_tab = SettingsTab(
            self.config, self.status_label, self._on_settings_saved,
        )
        self.tabs.addTab(self.settings_tab, "系统设置")

        # Tab5: 智能问答
        self.qa_tab = QATab(self.config, self.rag_manager, self.status_label)
        self.tabs.addTab(self.qa_tab, "智能问答")

        # Tab6: 变量表测试
        self.var_test_tab = VariableTestTab(self.config, self.rag_manager, self.status_label)
        self.tabs.addTab(self.var_test_tab, "变量表测试")

        # 初始化知识库列表
        self._refresh_all_kbs()

    # ------------------------------------------------------------------ #
    #  全局辅助
    # ------------------------------------------------------------------ #
    def _browse_file(self, line_edit):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择文件")
        if file_path:
            line_edit.setText(file_path)

    def _refresh_all_kbs(self):
        """刷新所有 Tab 中的知识库列表"""
        self.gen_tab.refresh_kb_list()
        self.kb_tab.refresh()
        self.qa_tab.refresh_kb_list()
        self.pipeline_tab.refresh_kb_list()
        self.var_test_tab.refresh_kbs()

    def _on_settings_saved(self):
        """设置保存后同步 UI"""
        self.gen_tab.model_label_display.setText(f"当前: {self.config.model_name}")
