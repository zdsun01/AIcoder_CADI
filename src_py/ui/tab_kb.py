"""
Tab: 知识库管理
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTextEdit, QGroupBox, QFormLayout, QComboBox, QMessageBox, QApplication,
)
from PyQt5.QtCore import Qt


class KBManageTab(QWidget):
    """知识库管理 Tab"""

    def __init__(self, config, rag_manager, status_label, browse_file_fn, refresh_all_kb_fn):
        super().__init__()
        self.config = config
        self.rag_manager = rag_manager
        self.status_label = status_label
        self.browse_file_fn = browse_file_fn
        self.refresh_all_kb_fn = refresh_all_kb_fn
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # 1. 当前知识库列表
        layout.addWidget(QLabel("<b>当前已索引的知识库:</b>"))
        self.kb_display = QTextEdit()
        self.kb_display.setReadOnly(True)
        self.kb_display.setMaximumHeight(140)
        layout.addWidget(self.kb_display)

        layout.addSpacing(30)

        # 2. 维护区
        maintenance_group = QGroupBox("⚠️ 数据库维护与初始化 (更换模型后必读)")
        maintenance_group.setStyleSheet("""
            QGroupBox {
                border: 1px solid #FF9800; border-radius: 6px; margin-top: 20px;
                font-size: 16px; background-color: #FFFBF5;
            }
            QGroupBox::title {
                color: #E65100; subcontrol-origin: margin; subcontrol-position: top left;
                left: 10px; padding: 0 5px; background-color: transparent; font-weight: bold;
            }
        """)
        m_layout = QVBoxLayout()
        m_layout.setContentsMargins(20, 20, 20, 20)
        m_layout.setSpacing(15)

        hint = QLabel(
            '<span style="color:#555;">提示：若更换了 Embedding 模型，会导致<b>\u201c维度不匹配\u201d</b>错误。</span><br>'
            '<span style="color:#E65100;">操作顺序：先点击 [清空所有数据] -> 再点击 [一键导入]</span>'
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("font-size: 14px; line-height: 1.5;")
        m_layout.addWidget(hint)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(20)

        reset_btn = QPushButton("🗑️ 清空所有数据")
        reset_btn.setMinimumHeight(38)
        reset_btn.setCursor(Qt.PointingHandCursor)
        reset_btn.setStyleSheet("""
            QPushButton { background-color: #FFF0F0; color: #D9534F; border: 1px solid #D9534F;
                          border-radius: 5px; font-weight: bold; font-size: 13px; }
            QPushButton:hover { background-color: #FFDddD; }
        """)
        reset_btn.clicked.connect(self._reset_database)

        import_btn = QPushButton("📚 一键导入 GJB 5369 默认库")
        import_btn.setMinimumHeight(38)
        import_btn.setCursor(Qt.PointingHandCursor)
        import_btn.setStyleSheet("""
            QPushButton { background-color: #0078d7; color: white; border: none;
                          border-radius: 5px; font-weight: bold; font-size: 13px; }
            QPushButton:hover { background-color: #0063b1; }
        """)
        import_btn.clicked.connect(self._load_default_gjb)

        btn_layout.addWidget(reset_btn)
        btn_layout.addWidget(import_btn)
        m_layout.addLayout(btn_layout)
        maintenance_group.setLayout(m_layout)
        layout.addWidget(maintenance_group)

        # 3. 上传新文档
        upload_group = QGroupBox("上传新文档")
        upload_group.setStyleSheet("QGroupBox { margin-top: 20px; font-weight: bold; }")
        form = QFormLayout()
        form.setContentsMargins(10, 25, 10, 10)
        form.setVerticalSpacing(12)

        self.new_kb_file = QLineEdit()
        self.new_kb_file.setMinimumHeight(30)
        self.new_kb_file.setPlaceholderText("支持 .txt, .md, .json 等")
        browse_kb = QPushButton("📂 浏览...")
        browse_kb.setFixedSize(80, 30)
        browse_kb.clicked.connect(lambda: self.browse_file_fn(self.new_kb_file))
        file_layout = QHBoxLayout()
        file_layout.addWidget(self.new_kb_file)
        file_layout.addWidget(browse_kb)

        self.new_kb_name = QLineEdit()
        self.new_kb_name.setMinimumHeight(30)
        self.new_kb_name.setPlaceholderText("例如: 项目需求文档_V1.0")

        upload_btn = QPushButton("⬆️ 上传并建立索引")
        upload_btn.setMinimumHeight(35)
        upload_btn.setStyleSheet("font-weight: bold;")
        upload_btn.clicked.connect(self._upload_kb)

        form.addRow("文件路径:", file_layout)
        form.addRow("知识库名:", self.new_kb_name)
        form.addRow("", upload_btn)
        upload_group.setLayout(form)
        layout.addWidget(upload_group)

        # 4. 删除单个知识库
        del_layout = QHBoxLayout()
        del_layout.setContentsMargins(0, 15, 0, 0)
        self.del_kb_combo = QComboBox()
        self.del_kb_combo.setMinimumHeight(30)

        del_btn = QPushButton("删除选中的知识库")
        del_btn.setMinimumHeight(30)
        del_btn.setStyleSheet("color: #d9534f;")
        del_btn.clicked.connect(self._delete_kb)

        del_layout.addWidget(QLabel("单独删除:"))
        del_layout.addWidget(self.del_kb_combo, 1)
        del_layout.addWidget(del_btn)
        layout.addLayout(del_layout)
        layout.addStretch()

    # ------------------------------------------------------------------ #
    #  刷新
    # ------------------------------------------------------------------ #
    def refresh(self):
        kbs = self.rag_manager.knowledge_bases
        self.kb_display.setText("\n".join([f"- {kb}" for kb in kbs]))
        self.del_kb_combo.clear()
        self.del_kb_combo.addItems(kbs)

    # ------------------------------------------------------------------ #
    #  操作
    # ------------------------------------------------------------------ #
    def _reset_database(self):
        reply = QMessageBox.question(
            self, "高风险操作",
            "⚠️ 确定要清空所有知识库吗？\n\n执行此操作将删除本地 chroma_db 文件夹下的所有索引数据。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            success, msg = self.rag_manager.reset_database()
            if success:
                self.refresh_all_kb_fn()
                QMessageBox.information(self, "成功", "数据库已清空，现在可以重新导入数据了~")
            else:
                QMessageBox.critical(self, "失败", f"操作失败: {msg}")

    def _load_default_gjb(self):
        if not self.rag_manager.embedding_fn:
            QMessageBox.warning(self, "错误", "Embedding 服务未初始化，请检查系统设置。")
            return
        self.status_label.setText("正在后台处理 GJB 5369 规则库...")
        QApplication.processEvents()
        try:
            self.rag_manager.init_default_kb()
            self.refresh_all_kb_fn()
            self.status_label.setText("导入完成")
            QMessageBox.information(self, "成功", "GJB 5369-2005 默认库导入成功！")
        except Exception as e:
            self.status_label.setText("导入失败")
            QMessageBox.critical(self, "维度错误", f"导入失败: {str(e)}\n\n请先点击【清空所有数据】按钮再试。")

    def _upload_kb(self):
        path = self.new_kb_file.text()
        name = self.new_kb_name.text()
        if not path or not name:
            QMessageBox.warning(self, "错误", "请填写文件路径和知识库名称")
            return
        self.status_label.setText("正在向量化处理(Embedding)...")
        QApplication.processEvents()
        success, msg = self.rag_manager.add_to_kb(path, name)
        if success:
            self.refresh_all_kb_fn()
            QMessageBox.information(self, "成功", msg)
            self.status_label.setText("知识库就绪")
        else:
            QMessageBox.critical(self, "失败", f"处理出错: {msg}")
            self.status_label.setText("处理失败")

    def _delete_kb(self):
        name = self.del_kb_combo.currentText()
        if not name:
            return
        if self.rag_manager.delete_kb(name):
            self.refresh_all_kb_fn()
            QMessageBox.information(self, "成功", f"已删除知识库: {name}")
