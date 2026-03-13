"""
Tab: 智能问答
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QCheckBox, QListWidget, QListWidgetItem,
    QAbstractItemView, QApplication,
)
from PyQt5.QtCore import Qt

from ui.widgets import ChatBubble, AutoExpandTextEdit
from ui.workers import GenerationThread
from backend.prompt_builder import PromptBuilder


class QATab(QWidget):
    """智能问答 Tab"""

    def __init__(self, config, rag_manager, status_label):
        super().__init__()
        self.config = config
        self.rag_manager = rag_manager
        self.status_label = status_label
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 1. 聊天记录
        self.chat_list = QListWidget()
        self.chat_list.setStyleSheet("""
            QListWidget {
                background-color: #F5F5F5; border: none; outline: none;
            }
            QListWidget::item { background-color: transparent; }
            QListWidget::item:hover { background-color: transparent; }
            QListWidget::item:selected { background-color: transparent; }
        """)
        self.chat_list.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        layout.addWidget(self.chat_list)

        # 2. 知识库设置
        controls_group = QGroupBox("知识库设置 (多选)")
        controls_group.setMaximumHeight(100)
        controls_layout = QHBoxLayout()

        self.use_rag_cb = QCheckBox("启用知识库参考")
        controls_layout.addWidget(self.use_rag_cb)

        self.kb_list_widget = QListWidget()
        self.kb_list_widget.setStyleSheet("""
            QListWidget { border: 1px solid #ccc; border-radius: 4px; background: white; }
            QListWidget::item { padding: 2px; }
            QListWidget::item:hover { background: #f0f0f0; }
        """)
        controls_layout.addWidget(self.kb_list_widget)
        controls_group.setLayout(controls_layout)
        layout.addWidget(controls_group)

        # 3. 底部输入
        input_container = QWidget()
        input_container.setStyleSheet("background-color: #FFFFFF; border-top: 1px solid #E0E0E0;")
        input_layout = QHBoxLayout(input_container)
        input_layout.setContentsMargins(10, 10, 10, 10)

        self.input_area = AutoExpandTextEdit()
        self.input_area.setPlaceholderText("💡在此输入你的问题 (Ctrl+Enter 发送)...")
        self.input_area.submit_signal.connect(self._send)

        self.send_btn = QPushButton("发送")
        self.send_btn.setFixedSize(80, 36)
        self.send_btn.setStyleSheet("""
            QPushButton {
                background-color: #07C160; color: white; font-weight: bold;
                border-radius: 4px; font-size: 14px;
            }
            QPushButton:hover { background-color: #06AD56; }
            QPushButton:pressed { background-color: #059B4C; }
            QPushButton:disabled { background-color: #A0E0B0; }
        """)
        self.send_btn.clicked.connect(self._send)

        input_layout.addWidget(self.input_area)
        input_layout.addWidget(self.send_btn, 0, Qt.AlignBottom)
        layout.addWidget(input_container)

    # ------------------------------------------------------------------ #
    #  刷新
    # ------------------------------------------------------------------ #
    def refresh_kb_list(self):
        self.kb_list_widget.clear()
        for kb in self.rag_manager.knowledge_bases:
            item = QListWidgetItem(kb)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if kb == "GJB_5369_2005" else Qt.Unchecked)
            self.kb_list_widget.addItem(item)

    # ------------------------------------------------------------------ #
    #  核心逻辑
    # ------------------------------------------------------------------ #
    def _add_message(self, text, is_user):
        bubble = ChatBubble(text, is_user)
        from PyQt5.QtWidgets import QListWidgetItem as LWI
        item = LWI()
        item.setSizeHint(bubble.sizeHint())
        self.chat_list.addItem(item)
        self.chat_list.setItemWidget(item, bubble)
        self.chat_list.scrollToBottom()

    def _send(self):
        question = self.input_area.toPlainText().strip()
        if not question:
            return

        self._add_message(question, is_user=True)
        self.input_area.clear()

        # RAG 检索
        selected_kbs = []
        if self.use_rag_cb.isChecked():
            for i in range(self.kb_list_widget.count()):
                item = self.kb_list_widget.item(i)
                if item.checkState() == Qt.Checked:
                    selected_kbs.append(item.text())

        context = ""
        kb_names_str = ",".join(selected_kbs) if selected_kbs else "无"

        if selected_kbs:
            self.status_label.setText(f"正在检索 {len(selected_kbs)} 个知识库...")
            QApplication.processEvents()
            context = self.rag_manager.recall_multi(question, selected_kbs)

        # 构建 prompt
        prompt = PromptBuilder.build_qa_prompt(question, context, kb_names_str)

        self.send_btn.setEnabled(False)
        self.send_btn.setText("思考中...")
        self.status_label.setText(f"[{self.config.model_name}] 正在思考...")

        self.thread = GenerationThread(
            self.config.api_url, self.config.api_key, self.config.model_name, prompt, self.config.host
        )
        self.thread.finished_signal.connect(self._on_finished)
        self.thread.error_signal.connect(self._on_error)
        self.thread.start()

    def _on_finished(self, text):
        self._add_message(text, is_user=False)
        self.send_btn.setEnabled(True)
        self.send_btn.setText("发送")
        self.status_label.setText("回答完成")
        self.input_area.setFocus()

    def _on_error(self, error_msg):
        self._add_message(f"❌ 请求出错: {error_msg}", is_user=False)
        self.send_btn.setEnabled(True)
        self.send_btn.setText("发送")
        self.status_label.setText("出错")
