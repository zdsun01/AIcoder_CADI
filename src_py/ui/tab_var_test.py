"""
Tab: 变量表测试
"""

import os
import pandas as pd
from datetime import datetime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTextEdit, QGroupBox, QFormLayout, QComboBox, QSpinBox, QProgressBar,
    QFileDialog, QMessageBox,
)
from PyQt5.QtCore import QSettings
from ui.workers import BatchTestThread


class VariableTestTab(QWidget):
    """变量表智能测试 Tab"""

    def __init__(self, config, rag_manager, status_label):
        super().__init__()
        self.config = config
        self.rag_manager = rag_manager
        self.status_label = status_label
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 1. 配置
        config_group = QGroupBox("1. 测试配置")
        form = QFormLayout()

        file_layout = QHBoxLayout()
        self.excel_path_edit = QLineEdit()
        self.excel_path_edit.setPlaceholderText("选择包含 '信号名称' 的 Excel 变量表...")
        btn_excel = QPushButton("📂")
        btn_excel.clicked.connect(lambda: self._browse(self.excel_path_edit, "Excel (*.xlsx)"))
        file_layout.addWidget(self.excel_path_edit)
        file_layout.addWidget(btn_excel)

        tpl_layout = QHBoxLayout()
        self.word_tpl_edit = QLineEdit()
        self.word_tpl_edit.setPlaceholderText("选择包含 {num_id}, {信号名称} 等占位符的 Word 模板...")
        btn_tpl = QPushButton("📂")
        btn_tpl.clicked.connect(lambda: self._browse(self.word_tpl_edit, "Word (*.docx)"))
        tpl_layout.addWidget(self.word_tpl_edit)
        tpl_layout.addWidget(btn_tpl)

        self.top_n_spin = QSpinBox()
        self.top_n_spin.setRange(1, 1000)
        self.top_n_spin.setValue(5)
        self.top_n_spin.setSuffix(" 个变量")

        self.kb_combo = QComboBox()
        refresh_btn = QPushButton("🔄")
        refresh_btn.setFixedSize(30, 20)
        refresh_btn.clicked.connect(self.refresh_kbs)
        kb_layout = QHBoxLayout()
        kb_layout.addWidget(self.kb_combo)
        kb_layout.addWidget(refresh_btn)

        form.addRow("变量表 (Excel):", file_layout)
        form.addRow("测试模板 (Word):", tpl_layout)
        form.addRow("测试数量 (Top N):", self.top_n_spin)
        form.addRow("测试目标知识库:", kb_layout)
        config_group.setLayout(form)
        layout.addWidget(config_group)

        # 2. 控制
        ctrl = QHBoxLayout()
        self.start_btn = QPushButton("▶ 开始自动化测试")
        self.start_btn.setStyleSheet("background-color: #07C160; color: white; font-weight: bold; padding: 10px;")
        self.start_btn.clicked.connect(self._start)
        self.stop_btn = QPushButton("⏹ 停止")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop)
        ctrl.addWidget(self.start_btn)
        ctrl.addWidget(self.stop_btn)
        layout.addLayout(ctrl)

        # 3. 进度与日志
        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setStyleSheet("font-size: 12px; color: #333; background: #f9f9f9;")
        layout.addWidget(self.log_area)

    def _browse(self, line_edit, filters):
        settings = QSettings("AICoder", "CADI")
        last_dir = settings.value("last_dir", "")
        path, _ = QFileDialog.getOpenFileName(self, "选择文件", last_dir, filters)
        if path:
            settings.setValue("last_dir", os.path.dirname(path))
            line_edit.setText(path)

    def refresh_kbs(self):
        self.kb_combo.clear()
        self.kb_combo.addItems(self.rag_manager.knowledge_bases)

    def _log(self, msg):
        time_str = datetime.now().strftime("%H:%M:%S")
        self.log_area.append(f"[{time_str}] {msg}")

    def _start(self):
        excel_path = self.excel_path_edit.text().strip()
        tpl_path = self.word_tpl_edit.text().strip()
        kb_name = self.kb_combo.currentText()
        top_n = self.top_n_spin.value()

        if not os.path.exists(excel_path) or not os.path.exists(tpl_path):
            QMessageBox.warning(self, "错误", "请检查 Excel 或 Word 模板路径是否正确！")
            return

        try:
            df = pd.read_excel(excel_path, engine="openpyxl")
            df.columns = [str(col).strip() for col in df.columns]
            if "信号名称" not in df.columns:
                QMessageBox.warning(self, "格式错误", "Excel 中必须包含列名 '信号名称'！")
                return
            test_data = df.head(top_n).to_dict("records")
            if not test_data:
                QMessageBox.warning(self, "数据为空", "未读取到有效数据。")
                return
        except Exception as e:
            self._log(f"启动失败: {e}")
            QMessageBox.critical(self, "错误", str(e))
            return

        self._log(f"已加载 {len(test_data)} 条测试数据，准备连接知识库 [{kb_name}]...")
        output_dir = os.path.join(self.config.project_root, "test_reports")
        os.makedirs(output_dir, exist_ok=True)

        self.thread = BatchTestThread(
            self.config, self.rag_manager, test_data, tpl_path, output_dir, kb_name
        )
        self.thread.progress_signal.connect(self._on_progress)
        self.thread.log_signal.connect(self._log)
        self.thread.finished_signal.connect(self._on_finished)

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress_bar.setValue(0)
        self.thread.start()

    def _on_progress(self, current, total, msg):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.status_label.setText(msg)
        self._log(msg)

    def _on_finished(self, success, msg):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_bar.setValue(self.progress_bar.maximum())
        if success:
            QMessageBox.information(self, "成功", msg)
            self._log("✅ 测试全部完成")
        else:
            QMessageBox.warning(self, "完成", msg)
            self._log("⚠️ 测试结束 (有错误或中断)")

    def _stop(self):
        if hasattr(self, "thread"):
            self.thread.stop()
            self._log("正在停止...")
            self.stop_btn.setEnabled(False)
