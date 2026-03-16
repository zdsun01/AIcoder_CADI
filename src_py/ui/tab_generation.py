"""
Tab: 代码生成
"""

import os
import difflib
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTextEdit, QGroupBox, QCheckBox, QListWidget, QListWidgetItem, QSplitter,
    QApplication, QMessageBox, QDialog, QTextBrowser,
    QScrollArea, QFrame
)
from PyQt5.QtCore import Qt, QEvent
from PyQt5.QtGui import QFont, QFontMetrics

from ui.widgets import CCppHighlighter
from ui.workers import GenerationThread
from backend.code_parser import extract_code_blocks, parse_requirement_text
from backend.prompt_builder import PromptBuilder


from backend.pipeline_engine import StaticRuleManager, VariableManager

class DiffDialog(QDialog):
    """代码比对确认弹窗（支持左右对照与分块选择）"""
    def __init__(self, old_code, new_code, parent=None):
        super().__init__(parent)
        self.setWindowTitle("代码修正比对 (Interactive Side-by-Side Diff)")
        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint | Qt.WindowMinimizeButtonHint)
        self.resize(1200, 800)
        
        self.old_code = old_code
        self.new_code = new_code
        self.final_code = ""
        self.accepted = False
        
        main_layout = QVBoxLayout(self)
        
        # --- 顶部控制栏 ---
        ctrl_layout = QHBoxLayout()
        self.toggle_fs_btn = QPushButton("🔲 全屏/还原")
        self.toggle_fs_btn.clicked.connect(self.toggle_fullscreen)
        self.toggle_fs_btn.setMinimumHeight(30)
        
        lbl = QLabel("💡 左侧为原始代码，右侧为修正代码。背景色：<font color='red'>红色(删除)</font>、<font color='green'>绿色(新增)</font>、<font color='#b8860b'>黄色(修改)</font>。<br>勾选中间的 <b>[✅ 采用]</b> 即可应用该处修改。")
        lbl.setStyleSheet("color: #555; font-size: 13px;")
        
        ctrl_layout.addWidget(lbl)
        ctrl_layout.addStretch()
        ctrl_layout.addWidget(self.toggle_fs_btn)
        main_layout.addLayout(ctrl_layout)
        
        # --- 表头 ---
        header_layout = QHBoxLayout()
        h_left = QLabel("修改前 (Original)")
        h_left.setStyleSheet("font-weight: bold; font-size: 14px; background: #e0e0e0; padding: 5px;")
        h_left.setAlignment(Qt.AlignCenter)
        
        h_mid = QLabel("操作")
        h_mid.setFixedWidth(60)
        h_mid.setStyleSheet("font-weight: bold; font-size: 12px;")
        h_mid.setAlignment(Qt.AlignCenter)
        
        h_right = QLabel("修改后 (Fixed)")
        h_right.setStyleSheet("font-weight: bold; font-size: 14px; background: #e0e0e0; padding: 5px;")
        h_right.setAlignment(Qt.AlignCenter)
        
        header_layout.addWidget(h_left)
        header_layout.addWidget(h_mid)
        header_layout.addWidget(h_right)
        main_layout.addLayout(header_layout)
        
        # --- 分块展示区域 ---
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll_widget = QWidget()
        self.scroll_widget.setStyleSheet("background-color: #ffffff;")
        self.scroll_layout = QVBoxLayout(self.scroll_widget)
        self.scroll_layout.setSpacing(0)
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        
        self.diff_blocks = []
        self._build_diff_ui()
        
        self.scroll_layout.addStretch()
        self.scroll.setWidget(self.scroll_widget)
        main_layout.addWidget(self.scroll)
        
        # --- 底部按钮 ---
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        reject_all_btn = QPushButton("❌ 放弃所有并返回")
        reject_all_btn.setMinimumHeight(35)
        reject_all_btn.clicked.connect(self.reject)
        
        accept_btn = QPushButton("✅ 完成比对，应用已选块代码")
        accept_btn.setMinimumHeight(35)
        accept_btn.setStyleSheet("background-color: #07C160; color: white; font-weight: bold; padding: 0 20px;")
        accept_btn.clicked.connect(self.accept_changes)
        
        btn_layout.addWidget(reject_all_btn)
        btn_layout.addWidget(accept_btn)
        main_layout.addLayout(btn_layout)

    def toggle_fullscreen(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def _build_diff_ui(self):
        old_lines = self.old_code.splitlines()
        new_lines = self.new_code.splitlines()
        
        font = QFont("Consolas", 11)
        fm = QFontMetrics(font)
        line_h = fm.lineSpacing()
        
        sm = difflib.SequenceMatcher(None, old_lines, new_lines)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            row_widget = QFrame()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 2, 0, 2)
            row_layout.setSpacing(5)
            
            old_text = "\n".join(old_lines[i1:i2])
            new_text = "\n".join(new_lines[j1:j2])
            
            lc_old = max(1, i2 - i1)
            lc_new = max(1, j2 - j1)
            
            if tag == 'equal':
                if i2 - i1 == 0: continue
                te_height = max(30, (i2 - i1) * line_h + 10)
                
                left_te = QTextEdit(old_text)
                right_te = QTextEdit(new_text)
                
                for te in (left_te, right_te):
                    te.setFont(font)
                    te.setReadOnly(True)
                    te.setLineWrapMode(QTextEdit.NoWrap)
                    te.setFixedHeight(te_height)
                    te.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
                    te.setStyleSheet("background-color: #f7f7f7; color: #777; border: none;")
                
                mid_widget = QLabel()
                mid_widget.setFixedWidth(60)
                
                row_layout.addWidget(left_te)
                row_layout.addWidget(mid_widget)
                row_layout.addWidget(right_te)
                
                self.diff_blocks.append({
                    'type': 'equal',
                    'lines': old_lines[i1:i2]
                })
                row_widget.setStyleSheet("border-bottom: 1px solid #eee;")
            else:
                max_lines = max(lc_old, lc_new)
                te_height = max(35, max_lines * line_h + 10)
                
                left_te = QTextEdit(old_text if tag in ('replace', 'delete') else "")
                right_te = QTextEdit(new_text if tag in ('replace', 'insert') else "")
                
                for te in (left_te, right_te):
                    te.setFont(font)
                    te.setReadOnly(True)
                    te.setLineWrapMode(QTextEdit.NoWrap)
                    te.setFixedHeight(te_height)
                    te.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
                
                if tag == 'replace':
                    left_te.setStyleSheet("background-color: #fffaea; color: #8c7300; border: 1px solid #ffd54f;")
                    right_te.setStyleSheet("background-color: #fffaea; color: #8c7300; border: 1px solid #ffd54f;")
                elif tag == 'delete':
                    left_te.setStyleSheet("background-color: #ffeaea; color: #aa0000; border: 1px solid #ffcccc;")
                    right_te.setStyleSheet("background-color: #f7f7f7; border: none;")
                elif tag == 'insert':
                    left_te.setStyleSheet("background-color: #f7f7f7; border: none;")
                    right_te.setStyleSheet("background-color: #eaffea; color: #006600; border: 1px solid #ccffcc;")
                
                mid_widget = QWidget()
                mid_widget.setFixedWidth(60)
                mid_layout = QVBoxLayout(mid_widget)
                mid_layout.setContentsMargins(0,0,0,0)
                
                chk = QCheckBox("采用")
                chk.setChecked(True)
                chk.setStyleSheet("font-weight: bold; color: #007700; font-size: 12px;")
                mid_layout.addWidget(chk, alignment=Qt.AlignCenter)
                
                row_layout.addWidget(left_te)
                row_layout.addWidget(mid_widget)
                row_layout.addWidget(right_te)
                
                self.diff_blocks.append({
                    'type': 'diff',
                    'old_lines': old_lines[i1:i2],
                    'new_lines': new_lines[j1:j2],
                    'checkbox': chk
                })
                row_widget.setStyleSheet("border-top: 1px dashed #ccc; border-bottom: 1px dashed #ccc; background-color: #fefefe;")
                
            self.scroll_layout.addWidget(row_widget)

    def accept_changes(self):
        final_code_lines = []
        for blk in self.diff_blocks:
            if blk['type'] == 'equal':
                final_code_lines.extend(blk['lines'])
            else:
                if blk['checkbox'].isChecked():
                    final_code_lines.extend(blk['new_lines'])
                else:
                    final_code_lines.extend(blk['old_lines'])
                    
        self.final_code = "\n".join(final_code_lines)
        self.accepted = True
        self.accept()

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

        # 4. RAG 增强
        kb_group = QGroupBox("2. RAG 增强 (多选)")
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

        # 5. 模型显示
        model_group = QGroupBox("5. 模型选择")
        model_layout = QHBoxLayout()
        self.model_label_display = QLabel(f"当前: {self.config.model_name}")
        model_layout.addWidget(self.model_label_display)
        model_group.setLayout(model_layout)
        input_layout.addWidget(model_group)

        # 生成与扫描按钮
        btn_layout = QHBoxLayout()
        
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
        btn_layout.addWidget(self.gen_btn)

        self.scan_btn = QPushButton("🔍 静态扫描")
        self.scan_btn.setCursor(Qt.PointingHandCursor)
        self.scan_btn.setStyleSheet("""
            QPushButton {
                font-size: 16px; font-weight: bold; padding: 10px;
                background-color: #07C160; color: white; border-radius: 5px; border: none;
            }
            QPushButton:hover { background-color: #06ad56; }
            QPushButton:pressed { background-color: #05994c; }
            QPushButton:disabled { background-color: #ccc; }
        """)
        self.scan_btn.setEnabled(False)  # 只有生成代码后才可用
        self.scan_btn.clicked.connect(self.start_static_scan)
        btn_layout.addWidget(self.scan_btn)

        input_layout.addLayout(btn_layout)
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
        rule_file = self.config.rule_path
        rules_content += PromptBuilder.load_rules_file(rule_file)

        if hasattr(self.config, 'special_variable_excel_path') and self.config.special_variable_excel_path:
            rules_content += PromptBuilder.load_special_variables_file(self.config.special_variable_excel_path)

        # 增加静态扫描提取的Excel内容到规则中
        if hasattr(self.config, 'static_rule_path') and self.config.static_rule_path:
            manager = StaticRuleManager(self.config.static_rule_path)
            if manager.rules_text:
                rules_content += "\n\n【静态代码检查规则】(请在生成代码时必须严格遵守):\n" + manager.rules_text + "\n"

        # 增加全局变量表匹配的内容
        if hasattr(self.config, 'variable_excel_path') and self.config.variable_excel_path:
            var_manager = VariableManager(self.config.variable_excel_path)
            if var_manager.is_loaded:
                all_vars = var_manager.get_all_vars()
                if all_vars:
                    rules_content += "\n\n【全局变量参考】(完整全局变量表，供随时调用):\n" + "\n".join(all_vars) + "\n"


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
        self.scan_btn.setEnabled(True)
        self.status_label.setText("生成完成")

    def _on_error(self, error_msg):
        self.result_area.setText(f"生成失败: {error_msg}\n\n请检查 '系统设置' 中的 API URL.")
        self.gen_btn.setEnabled(True)
        self.status_label.setText("出错")

    # ------------------------------------------------------------------ #
    #  静态代码扫描
    # ------------------------------------------------------------------ #
    def start_static_scan(self):
        static_excel = self.config.static_rule_path.strip() if self.config.static_rule_path else ""
        if not static_excel or not os.path.exists(static_excel):
            QMessageBox.warning(self, "提示", "请先在【系统设置】中配置有效的静态扫描规则 Excel 文件！")
            return
            
        generated_code = self.code_area.toPlainText().strip()
        if not generated_code or "等待生成新的代码" in generated_code:
            QMessageBox.warning(self, "提示", "请先生成或输入待扫描的代码！")
            return
            
        manager = StaticRuleManager(static_excel)
        if not manager.rules_text:
            QMessageBox.warning(self, "提示", "无法从 Excel 中提取规则，请检查格式(需包含“标号”和“准则描述”列)！")
            return
            
        prompt = PromptBuilder.build_review_prompt(manager.rules_text, generated_code)
        
        self.gen_btn.setEnabled(False)
        self.scan_btn.setEnabled(False)
        
        self.result_area.append("\n\n" + "="*50 + "\n🚀 [开始静态代码扫描 (Review)]\n")
        self.status_label.setText(f"正在调用 {self.config.model_name} 进行静态扫描(流式)...")
        
        self.scan_thread = GenerationThread(
            self.config.api_url, self.config.api_key, self.config.model_name, prompt, self.config.host
        )
        self.scan_thread.chunk_signal.connect(self._on_scan_chunk)
        self.scan_thread.finished_signal.connect(self._on_scan_finished)
        self.scan_thread.error_signal.connect(self._on_scan_error)
        self.scan_thread.start()
        
    def _on_scan_chunk(self, text):
        from PyQt5.QtGui import QTextCursor
        self.result_area.moveCursor(QTextCursor.End)
        self.result_area.insertPlainText(text)
        self.result_area.moveCursor(QTextCursor.End)
        
    def _on_scan_finished(self, text):
        clean_code = extract_code_blocks(text)
        if clean_code and "未检测到" not in clean_code:
            original_code = self.code_area.toPlainText()
            diff_dialog = DiffDialog(original_code, clean_code, self)
            
            if diff_dialog.exec_() and diff_dialog.accepted:
                self.code_area.setText(diff_dialog.final_code)
                self.status_label.setText("静态代码扫描完成，已应用代码修正！")
            else:
                self.status_label.setText("静态代码扫描完成，已放弃修改。")
        else:
            self.status_label.setText("静态动态扫描完成，未检测到需修正代码")
            
        self.gen_btn.setEnabled(True)
        self.scan_btn.setEnabled(True)
        
    def _on_scan_error(self, error_msg):
        self.result_area.append(f"\n扫描失败: {error_msg}")
        self.gen_btn.setEnabled(True)
        self.scan_btn.setEnabled(True)
        self.status_label.setText("扫描出错")

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
