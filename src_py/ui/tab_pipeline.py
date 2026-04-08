"""
Tab: 流水线生成
"""

import os
import shutil
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTextEdit, QGroupBox, QCheckBox, QFormLayout, QListWidget, QListWidgetItem,
    QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar,
    QFileDialog, QMessageBox, QApplication,
)
from PyQt5.QtCore import Qt, QTimer, QSettings

from ui.widgets import FileDragTextEdit
from ui.workers import GenerationThread, RAGRecallThread
from backend.pipeline_engine import (
    BatchTask, VariableManager, RefCodeManager, StaticRuleManager, TaskParser,
    write_code_files, write_single_file,
)
from backend.code_parser import extract_code_blocks, extract_multi_files
from backend.prompt_builder import PromptBuilder


class PipelineTab(QWidget):
    """流水线处理 Tab"""

    def __init__(self, config, rag_manager, status_label):
        """
        参数:
            config: ConfigManager
            rag_manager: RAGManager
            status_label: QLabel (状态栏)
        """
        super().__init__()
        self.config = config
        self.rag_manager = rag_manager
        self.status_label = status_label
        self.tasks = []
        self.current_task_index = -1
        self.is_running = False
        self.var_manager = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 1. 批量导入
        input_group = QGroupBox("1. 批量需求导入")
        ig_layout = QVBoxLayout()
        hint = QLabel("💡 提示：支持拖入 .txt/.md (正则解析) 或 .xlsx (表头: 需求ID, 需求名称, 输出文件, 需求内容, 参考代码)。")
        hint.setStyleSheet("color: #666; font-size: 12px;")
        ig_layout.addWidget(hint)

        self.batch_input_edit = FileDragTextEdit()
        self.batch_input_edit.setPlaceholderText("在此粘贴文本，或直接拖入 .xlsx / .txt 文件...")
        ig_layout.addWidget(self.batch_input_edit)

        btn_layout = QHBoxLayout()
        parse_btn = QPushButton("🔍 智能解析")
        parse_btn.clicked.connect(self._parse_tasks)
        btn_layout.addWidget(parse_btn)
        clear_btn = QPushButton("清空列表")
        clear_btn.clicked.connect(self._clear_tasks)
        btn_layout.addWidget(clear_btn)
        ig_layout.addLayout(btn_layout)
        input_group.setLayout(ig_layout)
        layout.addWidget(input_group, 3)

        # 2. RAG 增强
        rag_group = QGroupBox("2. RAG 增强配置")
        rag_layout = QHBoxLayout()
        self.use_rag_cb = QCheckBox("启用流水线 RAG")
        self.use_rag_cb.setChecked(True)
        rag_layout.addWidget(self.use_rag_cb)
        self.kb_list = QListWidget()
        self.kb_list.setMaximumHeight(50)
        self.kb_list.setStyleSheet("border: 1px solid #ccc; border-radius: 4px;")
        rag_layout.addWidget(self.kb_list)
        rag_group.setLayout(rag_layout)
        layout.addWidget(rag_group, 1)

        # 3. 执行队列
        task_group = QGroupBox("3. 执行队列")
        tg_layout = QVBoxLayout()

        sel_layout = QHBoxLayout()
        sel_layout.addStretch()
        for label, mode in [("☑ 全选", "all"), ("🔄 反选", "invert"), ("☐ 全不选", "none")]:
            btn = QPushButton(label)
            btn.setFixedSize(60, 24)
            btn.setStyleSheet("font-size: 11px; padding: 2px;")
            btn.clicked.connect(lambda _, m=mode: self._batch_select(m))
            sel_layout.addWidget(btn)
        tg_layout.addLayout(sel_layout)

        self.task_table = QTableWidget()
        self.task_table.setColumnCount(5)
        self.task_table.setHorizontalHeaderLabels(["选择", "ID", "需求名称", "输出路径 (相对)", "状态"])
        self.task_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.task_table.setColumnWidth(0, 50)
        self.task_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.task_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.task_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.task_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        tg_layout.addWidget(self.task_table)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        tg_layout.addWidget(self.progress_bar)

        run_layout = QHBoxLayout()
        self.run_btn = QPushButton("▶ 开始流水线生成")
        self.run_btn.setStyleSheet("background-color: #07C160; color: white; font-weight: bold; padding: 10px;")
        self.run_btn.clicked.connect(self._start)
        self.stop_btn = QPushButton("⏹ 停止")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop)
        run_layout.addWidget(self.run_btn)
        run_layout.addWidget(self.stop_btn)
        tg_layout.addLayout(run_layout)

        task_group.setLayout(tg_layout)
        layout.addWidget(task_group, 2)

    # ------------------------------------------------------------------ #
    #  KB 刷新
    # ------------------------------------------------------------------ #
    def refresh_kb_list(self):
        self.kb_list.clear()
        for kb in self.rag_manager.knowledge_bases:
            item = QListWidgetItem(kb)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if "GJB" in kb else Qt.Unchecked)
            self.kb_list.addItem(item)

    # ------------------------------------------------------------------ #
    #  UI helpers
    # ------------------------------------------------------------------ #
    def _browse_file(self, line_edit, filters, setting_key="last_dir"):
        import os
        settings = QSettings("AICoder", "CADI")
        last_dir = settings.value(setting_key, "")
        if not last_dir and hasattr(self, 'config') and self.config.project_root:
            last_dir = self.config.project_root
            
        path, _ = QFileDialog.getOpenFileName(self, "选择文件", last_dir, filters)
        if path:
            settings.setValue(setting_key, os.path.dirname(path))
            line_edit.setText(path)

    def _batch_select(self, mode):
        for row in range(self.task_table.rowCount()):
            item = self.task_table.item(row, 0)
            if not item:
                continue
            if mode == "all":
                item.setCheckState(Qt.Checked)
            elif mode == "none":
                item.setCheckState(Qt.Unchecked)
            elif mode == "invert":
                item.setCheckState(Qt.Unchecked if item.checkState() == Qt.Checked else Qt.Checked)

    def _add_task_to_table(self, task):
        row = self.task_table.rowCount()
        self.task_table.insertRow(row)
        check = QTableWidgetItem()
        check.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
        check.setCheckState(Qt.Checked)
        check.setTextAlignment(Qt.AlignCenter)
        self.task_table.setItem(row, 0, check)
        self.task_table.setItem(row, 1, QTableWidgetItem(task.id))
        self.task_table.setItem(row, 2, QTableWidgetItem(task.name))
        self.task_table.setItem(row, 3, QTableWidgetItem("\n".join(task.target_files)))
        self.task_table.setItem(row, 4, QTableWidgetItem(task.status))
        self.task_table.resizeRowToContents(row)

    def _update_status(self, row, status):
        self.task_table.setItem(row, 4, QTableWidgetItem(status))
        self.task_table.scrollToItem(self.task_table.item(row, 0))

    # ------------------------------------------------------------------ #
    #  解析
    # ------------------------------------------------------------------ #
    def _parse_tasks(self):
        raw = self.batch_input_edit.toPlainText().strip()
        if not raw:
            return
        self.tasks = []
        self.task_table.setRowCount(0)

        tasks, excel_count, regex_count, errors = TaskParser.parse_input(raw)
        self.tasks = tasks
        for t in tasks:
            self._add_task_to_table(t)

        self.status_label.setText(f"解析结果: Excel任务 {excel_count} 个, 文本解析 {regex_count} 个")

        total = len(tasks)
        if total > 0:
            QMessageBox.information(self, "解析完成",
                f"共识别到 {total} 个任务。\n- Excel来源: {excel_count}\n- 文本解析: {regex_count}")
        else:
            msg = "未识别到有效任务。请检查文件格式或文本内容。"
            if errors:
                msg += "\n\n错误:\n" + "\n".join(errors)
            QMessageBox.warning(self, "解析失败", msg)

    def _clear_tasks(self):
        self.tasks = []
        self.task_table.setRowCount(0)
        self.progress_bar.setValue(0)

    # ------------------------------------------------------------------ #
    #  流水线执行
    # ------------------------------------------------------------------ #
    def _start(self):
        if not self.tasks:
            return
        if not self.config.project_root:
            QMessageBox.warning(self, "未配置根目录", "请先在【系统设置】中配置工程根目录！")
            return

        # 变量管理
        excel_path = self.config.variable_excel_path.strip()
        if excel_path and os.path.exists(excel_path):
            if not getattr(self, 'var_manager', None) or getattr(self, '_current_excel', '') != excel_path:
                self.var_manager = VariableManager(excel_path)
                self._current_excel = excel_path
        else:
            self.var_manager = None

        # 参考代码不再从界面配置，若后续需要可从配置中读取，此处设为 None
        self.ref_manager = None

        # 静态规则 Review
        static_excel = self.config.static_rule_path.strip()
        self.static_rule_manager = StaticRuleManager(static_excel) if static_excel and os.path.exists(static_excel) else None

        self.is_running = True
        self.run_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.current_task_index = -1
        
        # 确保重置状态
        for t in self.tasks:
            t.processing_stage = "GENERATE"
            
        self.progress_bar.setMaximum(len(self.tasks))
        self.progress_bar.setValue(0)
        self._run_next()

    def _stop(self):
        self.is_running = False
        
        if hasattr(self, 'rag_worker') and self.rag_worker.isRunning():
            try:
                self.rag_worker.finished_signal.disconnect()
                self.rag_worker.error_signal.disconnect()
            except Exception:
                pass
            self.rag_worker.terminate()
            self.rag_worker.wait(100)
            
        if hasattr(self, 'worker') and self.worker.isRunning():
            try:
                self.worker.finished_signal.disconnect()
                self.worker.error_signal.disconnect()
            except Exception:
                pass
            self.worker.terminate()
            self.worker.wait(100)

        if 0 <= self.current_task_index < len(self.tasks):
            self._update_status(self.current_task_index, "⚠️ 已停止 (用户终止)")
            item = self.task_table.item(self.current_task_index, 4)
            if item:
                item.setForeground(Qt.red)

        self.run_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_label.setText("流水线已手动停止")
        QMessageBox.information(self, "提示", "流水线已强制停止。")

    def _run_next(self):
        if not self.is_running:
            return
        self.current_task_index += 1
        if self.current_task_index >= len(self.tasks):
            self._finish()
            return

        task = self.tasks[self.current_task_index]

        # 跳过未勾选
        check_item = self.task_table.item(self.current_task_index, 0)
        if check_item and check_item.checkState() == Qt.Unchecked:
            self._update_status(self.current_task_index, "⏭️ 已跳过")
            QTimer.singleShot(10, self._run_next)
            return

        self._update_status(self.current_task_index, "🔍 检索上下文(RAG/Vars)...")
        self.task_table.scrollToItem(self.task_table.item(self.current_task_index, 0))
        QApplication.processEvents()

        # --- RAG ---
        if self.use_rag_cb.isChecked():
            selected_kbs = self._get_selected_kbs()
            if selected_kbs:
                self._update_status(self.current_task_index, "🔍 RAG检索中...")
                full_query = f"{task.id} {task.name}\n{task.content}"
                query_text = full_query[:800]
                self.rag_worker = RAGRecallThread(self.rag_manager, query_text, selected_kbs)
                self.rag_worker.finished_signal.connect(self._on_rag_finished)
                self.rag_worker.error_signal.connect(self._on_rag_error)
                self.rag_worker.start()
                return

        self._on_rag_finished("")

    def _on_rag_error(self, err_msg):
        if not self.is_running:
            return
        self._update_status(self.current_task_index, f"RAG异常: {err_msg}")
        self._on_rag_finished("")

    def _on_rag_finished(self, rag_context):
        if not self.is_running:
            return
        
        task = self.tasks[self.current_task_index]
        self._update_status(self.current_task_index, "🔍 准备变量与规则...")

        # --- 变量获取 ---
        matched_vars = "无 (未配置变量表或无匹配项)"
        if self.var_manager and self.var_manager.is_loaded:
            all_vars = self.var_manager.get_all_vars()
            if all_vars:
                matched_vars = "\n".join(all_vars)
                task.used_global_vars = matched_vars

        # --- 外部规则 ---
        external_rules = PromptBuilder.load_rules_file(self.config.rule_path.strip())
        if hasattr(self.config, 'special_variable_excel_path') and self.config.special_variable_excel_path:
            external_rules += PromptBuilder.load_special_variables_file(self.config.special_variable_excel_path)
            
        # 增加静态扫描提取的Excel内容到外部规则中
        if hasattr(self, 'static_rule_manager') and self.static_rule_manager and self.static_rule_manager.rules_text:
            external_rules += "\n\n【静态代码检查规则】(请在生成代码时必须严格遵守):\n" + self.static_rule_manager.rules_text + "\n"

        # --- 构建 prompt ---
        builder = PromptBuilder(self.config.prompt_template)
        prompt = builder.build_pipeline_prompt(
            task_id=task.id,
            task_name=task.name,
            task_content=task.content,
            rag_context=rag_context,
            matched_vars_text=matched_vars,
            external_rules=external_rules,
            target_files=task.target_files,
            ref_code=task.ref_code,
            local_vars=getattr(task, "vars", ""),
        )

        self._update_status(self.current_task_index, "生成中(AI思考)...")

        self.worker = GenerationThread(
            self.config.api_url, self.config.api_key, self.config.model_name, prompt, self.config.host
        )
        self.worker.finished_signal.connect(self._on_task_finished)
        self.worker.error_signal.connect(self._on_task_error)
        self.worker.start()

    def _on_task_finished(self, text):
        if not self.is_running:
            return
        task = self.tasks[self.current_task_index]
        
        if getattr(task, 'processing_stage', 'GENERATE') == 'GENERATE':
            self._handle_generation_finished(task, text)
        else:
            self._handle_review_finished(task, text)

    def _handle_generation_finished(self, task, text):
        root = self.config.project_root

        multi_files = extract_multi_files(text)
        status_msg = ""

        if multi_files:
            final_code = ""
            for fn, content in multi_files:
                if fn.lower().endswith(".c"):
                    final_code += f"{content}\n\n"
            task.generated_clean_code = final_code
            count = write_code_files(root, multi_files)
            status_msg = f"生成完成 ({count}个文件)"
        else:
            clean_code = extract_code_blocks(text)
            task.generated_clean_code = clean_code
            target = task.output_rel_path or (task.target_files[0] if task.target_files else "")
            if target and "未检测到" not in clean_code:
                if write_single_file(root, target, clean_code):
                    status_msg = "生成完成 (单文件)"
                else:
                    status_msg = "生成代码写入失败"
            else:
                status_msg = "生成完成 (格式不匹配)"

        # 流水线取消自动 Review，直接保存报告并进行下一个
        self._finalize_task(task, status_msg, "流水线未执行自动扫描")

    def _handle_review_finished(self, task, text):
        root = self.config.project_root
        status_msg = "Review 完成"

        # 尝试提取修正后的代码
        multi_files = extract_multi_files(text)
        if multi_files:
            final_code = ""
            for fn, content in multi_files:
                if fn.lower().endswith(".c"):
                    final_code += f"{content}\n\n"
            task.generated_clean_code = final_code
            write_code_files(root, multi_files)
            status_msg += " -> 代码已修正 (多文件)"
        else:
            clean_code = extract_code_blocks(text)
            if clean_code and "未检测到" not in clean_code:
                task.generated_clean_code = clean_code
                target = task.output_rel_path or (task.target_files[0] if task.target_files else "")
                if target:
                    if write_single_file(root, target, clean_code):
                        status_msg += " -> 代码已修正"
                    else:
                        status_msg += " -> 修正代码写入失败"
                else:
                    status_msg += " -> 格式不匹配"
            else:
                status_msg += " -> 格式不匹配"

        self._finalize_task(task, status_msg, text)

    def _finalize_task(self, task, status_msg, review_result_text):
        self._update_status(self.current_task_index, status_msg)
        self.progress_bar.setValue(self.current_task_index + 1)
        self._run_next()

    def _on_task_error(self, err_msg):
        if not self.is_running:
            return
        self._update_status(self.current_task_index, f"API错误: {err_msg}")
        self._run_next()

    def _finish(self):
        self.is_running = False
        self.run_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

        QMessageBox.information(self, "完成", "流水线队列处理完毕！")

    def _get_selected_kbs(self):
        selected = []
        for i in range(self.kb_list.count()):
            item = self.kb_list.item(i)
            if item.checkState() == Qt.Checked:
                selected.append(item.text())
        return selected
