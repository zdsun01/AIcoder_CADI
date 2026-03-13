"""
Tab: 代码生成
"""

import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTextEdit, QGroupBox, QCheckBox, QListWidget, QListWidgetItem, QSplitter,
    QApplication, QMessageBox,
)
from PyQt5.QtCore import Qt, QEvent

from ui.widgets import CCppHighlighter
from ui.workers import GenerationThread
from backend.code_parser import extract_code_blocks, parse_requirement_text
from backend.prompt_builder import PromptBuilder


class GenerationTab(QWidget):
    """代码生成 Tab"""

    def __init__(self, config, rag_manager, status_label, browse_file_fn):
        super().__init__()
        self.config = config
        self.rag_manager = rag_manager
        self.status_label = status_label
        self.browse_file_fn = browse_file_fn
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)

        # ---- 左侧：输入区 ----
        input_panel = QWidget()
        input_layout = QVBoxLayout(input_panel)

        # 1. 需求文件
        req_group = QGroupBox("1. 需求文件")
        req_layout = QVBoxLayout()
        self.req_path_edit = QLineEdit()
        self.req_path_edit.setPlaceholderText("选择需求文档 (.txt, .md)...")
        req_btn = QPushButton("📂 浏览...")
        req_btn.setCursor(Qt.PointingHandCursor)
        req_btn.clicked.connect(lambda: self.browse_file_fn(self.req_path_edit, "last_dir_req"))
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
        rule_btn.clicked.connect(lambda: self.browse_file_fn(self.rule_path_edit, "last_dir_rule"))
        rule_layout.addWidget(self.rule_path_edit)
        rule_layout.addWidget(rule_btn)
        rule_group.setLayout(rule_layout)
        input_layout.addWidget(rule_group)

        # 3. RAG 增强
        kb_group = QGroupBox("3. RAG 增强 (多选)")
        kb_layout = QVBoxLayout()
        self.use_rag_cb = QCheckBox("启用知识库增强")
        kb_layout.addWidget(self.use_rag_cb)
        self.kb_list_widget = QListWidget()
        self.kb_list_widget.setMaximumHeight(100)
        self.kb_list_widget.setStyleSheet("""
            QListWidget { border: 1px solid #ccc; border-radius: 4px; background: white; }
            QListWidget::item { padding: 4px; }
            QListWidget::item:hover { background: #f0f0f0; }
        """)
        kb_layout.addWidget(self.kb_list_widget)
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
                font-size: 16px; font-weight: bold; padding: 10px;
                background-color: #0078d7; color: white; border-radius: 5px; border: none;
            }
            QPushButton:hover { background-color: #0063b1; }
            QPushButton:pressed { background-color: #005a9e; }
            QPushButton:disabled { background-color: #ccc; }
        """)
        self.gen_btn.clicked.connect(self.start_generation)
        input_layout.addWidget(self.gen_btn)
        input_layout.addStretch()

        # ---- 右侧：输出区 ----
        output_splitter = QSplitter(Qt.Vertical)

        # 上：完整分析
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.addWidget(QLabel("<b>🧠 完整分析与推理 (Analysis):</b>"))
        self.result_area = QTextEdit()
        self.result_area.setReadOnly(True)
        self.result_area.setStyleSheet("font-family: Consolas; font-size: 13px; color: #555;")
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
        copy_btn.clicked.connect(self._copy_code)
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
        bottom_layout.addWidget(self.code_area)
        output_splitter.addWidget(bottom_widget)

        output_splitter.setStretchFactor(0, 4)
        output_splitter.setStretchFactor(1, 6)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(input_panel)
        splitter.addWidget(output_splitter)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter)

        # installEventFilter 必须在两个 area 都创建之后
        self.result_area.installEventFilter(self)
        self.code_area.installEventFilter(self)

    # ------------------------------------------------------------------ #
    #  核心逻辑
    # ------------------------------------------------------------------ #
    def refresh_kb_list(self):
        self.kb_list_widget.clear()
        for kb in self.rag_manager.knowledge_bases:
            item = QListWidgetItem(kb)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if kb == "GJB_5369_2005" else Qt.Unchecked)
            self.kb_list_widget.addItem(item)

    def start_generation(self):
        req_text = self.req_text_edit.toPlainText().strip()
        req_file = self.req_path_edit.text().strip()
        
        has_file = bool(req_file and os.path.exists(req_file))
        has_text = bool(req_text)
        
        if has_file and has_text:
            QMessageBox.warning(self, "提示", "需求文件和手动输入只能选择其一！")
            return

        req_content = ""
        if has_file:
            try:
                with open(req_file, "r", encoding="utf-8") as f:
                    req_content = f.read()
            except Exception as e:
                QMessageBox.warning(self, "错误", f"读取需求文件失败: {e}")
                return
        elif has_text:
            req_content = req_text

        if not req_content.strip():
            QMessageBox.warning(self, "提示", "请输入需求或上传需求文件")
            return

        # 收集规则
        rules_content = ""
        rule_file = self.rule_path_edit.text()
        rules_content += PromptBuilder.load_rules_file(rule_file)

        # RAG 检索
        rag_context = "无外部知识库上下文"
        if self.use_rag_cb.isChecked():
            selected_kbs = self._get_selected_kbs()
            if not selected_kbs:
                self.status_label.setText("提示：未选择任何知识库，将仅使用通用模型生成...")

            combined_context = []
            for kb_name in selected_kbs:
                self.status_label.setText(f"正在从知识库 [{kb_name}] 检索...")
                QApplication.processEvents()
                content = self.rag_manager.recall(req_content[:300], kb_name)
                if kb_name == "GJB_5369_2005":
                    if "未找到" not in content:
                        rules_content += f"\n【GJB 5369-2005 自动检索】:\n{content}\n"
                else:
                    if "未找到" not in content:
                        combined_context.append(f"--- 来源: {kb_name} ---\n{content}")

            if combined_context:
                rag_context = "\n\n".join(combined_context)

        # 构建 prompt
        parsed_req = parse_requirement_text(req_content)
        builder = PromptBuilder(self.config.prompt_template)
        final_prompt = builder.build_generation_prompt(parsed_req, rag_context, rules_content)

        # 异步调用
        self.gen_btn.setEnabled(False)
        self.result_area.setText("正在生成代码(已拆分需求结构)...\n")
        self.code_area.setText("/*等待生成新的代码...*/")
        self.status_label.setText(f"正在调用 {self.config.model_name} 生成代码(流式)...")

        self.thread = GenerationThread(
            self.config.api_url, self.config.api_key, self.config.model_name, final_prompt, self.config.host
        )
        self._current_full_text = ""
        self.thread.chunk_signal.connect(self._on_chunk)
        self.thread.finished_signal.connect(self._on_finished)
        self.thread.error_signal.connect(self._on_error)
        self.thread.start()

    def _on_chunk(self, text):
        from PyQt5.QtGui import QTextCursor
        self._current_full_text += text
        self.result_area.moveCursor(QTextCursor.End)
        self.result_area.insertPlainText(text)
        self.result_area.moveCursor(QTextCursor.End)

    def _on_finished(self, text):
        self._current_full_text = text
        self.result_area.setText(text)
        self.code_area.setText(extract_code_blocks(text))
        self.gen_btn.setEnabled(True)
        self.status_label.setText("生成完成")

    def _on_error(self, error_msg):
        self.result_area.setText(f"生成失败: {error_msg}\n\n请检查 '系统设置' 中的 API URL.")
        self.gen_btn.setEnabled(True)
        self.status_label.setText("出错")

    def _copy_code(self):
        code = self.code_area.toPlainText()
        if code:
            QApplication.clipboard().setText(code)
            self.status_label.setText("代码已复制到剪贴板！")
        else:
            QMessageBox.warning(self, "提示", "没有代码可复制")

    def _get_selected_kbs(self):
        selected = []
        for i in range(self.kb_list_widget.count()):
            item = self.kb_list_widget.item(i)
            if item.checkState() == Qt.Checked:
                selected.append(item.text())
        return selected

    def eventFilter(self, source, event):
        if source in (self.result_area, self.code_area) and event.type() == QEvent.Wheel:
            if event.modifiers() & Qt.ControlModifier:
                if event.angleDelta().y() > 0:
                    source.zoomIn(1)
                else:
                    source.zoomOut(1)
                return True
        return super().eventFilter(source, event)
