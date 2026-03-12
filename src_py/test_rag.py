from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTextEdit, QFileDialog, QTabWidget, QCheckBox,
    QComboBox, QMessageBox, QGroupBox, QFormLayout,
    QListWidget, QListWidgetItem, QAbstractItemView,
    QSplitter
)
from PyQt5.QtWidgets import QProgressBar, QSpinBox
import os
import re
import pandas as pd
from rag_core import RAGManager
from pipeline import WordReportGenerator

from PyQt5.QtCore import QThread, pyqtSignal

class BatchTestThread(QThread):
    """后台批量测试线程，负责循环调用 LLM 并生成 Word"""
    progress_signal = pyqtSignal(int, int, str) # current, total, status_msg
    finished_signal = pyqtSignal(bool, str)     # success, msg
    log_signal = pyqtSignal(str)                # 用于输出日志到 UI

    def __init__(self, config, rag_manager, test_data, template_path, output_dir, kb_name):
        super().__init__()
        self.config = config
        self.rag_manager = rag_manager
        self.test_data = test_data  # List of dicts from Excel
        self.template_path = template_path
        self.output_dir = output_dir
        self.kb_name = kb_name
        self.is_running = True

    def run(self):
        import requests
        import json
        import shutil
        import re
        
        generated_files = []
        total = len(self.test_data)
        
        self.log_signal.emit(f"🚀 开始批量测试，共 {total} 个变量...")

        for idx, row in enumerate(self.test_data):
            if not self.is_running: break
            
            # 1. 准备基础数据
            num_id = idx + 1
            signal_name = str(row.get('信号名称', 'Unknown'))
            
            # 获取表头用于辅助 Prompt (预期输出列也需要用到)
            headers = [k for k in row.keys() if k and not str(k).startswith("Unnamed")]
            headers_str = "、".join(headers)
            
            # -------------------------------------------------------
            # [关键修改 1]：构造符合模板语境的问题
            # 模板里的问题是：“{信号名称}的定义是什么？”
            # 我们在 Prompt 里也尽量贴合这个语境
            # -------------------------------------------------------
            question_for_llm = f"变量“{signal_name}”的定义是什么？"
            
            # -------------------------------------------------------
            # [关键修改 2]：预期输出 (Excel 内容)
            # 使用 \n 换行，确保在 Word 单元格里每一项占一行，清晰易读
            # -------------------------------------------------------
            row_content_str = "\n".join([f"{k}: {v}" for k, v in row.items()])
            
            self.progress_signal.emit(idx, total, f"正在测试 [{num_id}/{total}]: {signal_name}")
            
            # 2. RAG 检索
            rag_context = ""
            try:
                rag_context = self.rag_manager.recall(question_for_llm, self.kb_name)
            except Exception as e:
                rag_context = f"检索失败: {e}"

            # 3. LLM 生成
            prompt = (
                f"你是一个严谨的测试工程师。请根据参考资料回答问题。\n\n"
                f"【参考资料】:\n{rag_context}\n\n"
                f"【问题】: {question_for_llm}\n\n"
                f"【要求】:\n"
                f"1. 请直接回答问题，列出该变量的详细属性（如 {headers_str}）。\n"
                f"2. 这是一个自动化测试报告的‘实际输出’部分，请保持回答条理清晰，可以使用列表格式。\n"
                f"3. 如果参考资料中未找到相关定义，请直接回答“未找到该变量定义”。"
            )

            llm_response = ""
            try:
                payload = {
                    "model": self.config.model_name,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False
                }
                headers_http = {"Authorization": f"Bearer {self.config.api_key}", "Content-Type": "application/json"}
                
                resp = requests.post(self.config.api_url, json=payload, headers=headers_http, timeout=60)
                if resp.status_code == 200:
                    result = resp.json()
                    if "choices" in result:
                        llm_response = result["choices"][0]["message"]["content"]
                    else:
                        llm_response = str(result)
                else:
                    llm_response = f"API Error: {resp.status_code} - {resp.text}"
            except Exception as e:
                llm_response = f"请求异常: {str(e)}"

            word_data = {
                "{num_id}": str(num_id),                # 对应模板：Var_..._00{num_id}
                "{信号名称}": signal_name,              # 对应模板：{信号名称}的定义是什么？
                "{变量表该行的所有内容}": row_content_str, # 对应模板：预期输出列
                "{LLM回答}": llm_response              # 对应模板：实际输出列
            }

            temp_filename = f"test_res_{num_id:03d}_{signal_name}.docx"
            temp_filename = re.sub(r'[\\/*?:"<>|]', "_", temp_filename)
            temp_file_path = os.path.join(self.output_dir, temp_filename)

            success, msg = WordReportGenerator.generate_report(self.template_path, temp_file_path, word_data)
            if success:
                generated_files.append(temp_file_path)
            else:
                self.log_signal.emit(f"❌ Word 生成失败 ({signal_name}): {msg}")

        # 6. 合并报告
        if generated_files and self.is_running:
            self.progress_signal.emit(total, total, "正在合并测试报告...")
            final_report_path = os.path.join(self.output_dir, "Final_Variable_Test_Report.docx")
            success, msg = WordReportGenerator.merge_reports(generated_files, final_report_path)
            
            if success:
                self.finished_signal.emit(True, f"测试完成！报告已生成: {final_report_path}")
            else:
                self.finished_signal.emit(False, f"合并失败: {msg}")
            
            for f in generated_files:
                try:
                    os.remove(f)
                except:
                    pass
        else:
            self.finished_signal.emit(False, "未生成任何有效文件或任务被停止")

    def stop(self):
        self.is_running = False


class VariableTestTab(QWidget):
    """变量表智能测试 Tab"""
    def __init__(self, app_parent):
        super().__init__()
        self.app = app_parent
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # 1. 设置区域
        config_group = QGroupBox("1. 测试配置")
        form_layout = QFormLayout()

        # 变量 Excel 选择
        file_layout = QHBoxLayout()
        self.excel_path_edit = QLineEdit()
        self.excel_path_edit.setPlaceholderText("选择包含 '信号名称' 的 Excel 变量表...")
        btn_excel = QPushButton("📂")
        btn_excel.clicked.connect(lambda: self.browse_file(self.excel_path_edit, "Excel (*.xlsx)"))
        file_layout.addWidget(self.excel_path_edit)
        file_layout.addWidget(btn_excel)
        
        # Word 模板选择
        tpl_layout = QHBoxLayout()
        self.word_tpl_edit = QLineEdit()
        self.word_tpl_edit.setPlaceholderText("选择包含 {num_id}, {信号名称} 等占位符的 Word 模板...")
        btn_tpl = QPushButton("📂")
        btn_tpl.clicked.connect(lambda: self.browse_file(self.word_tpl_edit, "Word (*.docx)"))
        tpl_layout.addWidget(self.word_tpl_edit)
        tpl_layout.addWidget(btn_tpl)

        # 参数设置
        self.top_n_spin = QSpinBox()
        self.top_n_spin.setRange(1, 1000)
        self.top_n_spin.setValue(5)
        self.top_n_spin.setSuffix(" 个变量")
        
        self.kb_combo = QComboBox()
        self.kb_combo.addItems(self.app.rag_manager.knowledge_bases) # 加载现有知识库

        # 刷新知识库按钮
        refresh_btn = QPushButton("🔄")
        refresh_btn.setFixedSize(30, 20)
        refresh_btn.clicked.connect(self.refresh_kbs)
        
        kb_layout = QHBoxLayout()
        kb_layout.addWidget(self.kb_combo)
        kb_layout.addWidget(refresh_btn)

        form_layout.addRow("变量表 (Excel):", file_layout)
        form_layout.addRow("测试模板 (Word):", tpl_layout)
        form_layout.addRow("测试数量 (Top N):", self.top_n_spin)
        form_layout.addRow("测试目标知识库:", kb_layout)
        
        config_group.setLayout(form_layout)
        layout.addWidget(config_group)

        # 2. 控制区域
        ctrl_layout = QHBoxLayout()
        self.start_btn = QPushButton("▶ 开始自动化测试")
        self.start_btn.setStyleSheet("background-color: #07C160; color: white; font-weight: bold; padding: 10px;")
        self.start_btn.clicked.connect(self.start_test)
        
        self.stop_btn = QPushButton("⏹ 停止")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_test)
        
        ctrl_layout.addWidget(self.start_btn)
        ctrl_layout.addWidget(self.stop_btn)
        layout.addLayout(ctrl_layout)

        # 3. 进度与日志
        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)
        
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setStyleSheet("font-size: 12px; color: #333; background: #f9f9f9;")
        layout.addWidget(self.log_area)

    def browse_file(self, line_edit, filters):
        path, _ = QFileDialog.getOpenFileName(self, "选择文件", "", filters)
        if path:
            line_edit.setText(path)

    def refresh_kbs(self):
        self.kb_combo.clear()
        self.kb_combo.addItems(self.app.rag_manager.knowledge_bases)

    def log(self, msg):
        from datetime import datetime
        time_str = datetime.now().strftime("%H:%M:%S")
        self.log_area.append(f"[{time_str}] {msg}")

    def start_test(self):
        excel_path = self.excel_path_edit.text().strip()
        tpl_path = self.word_tpl_edit.text().strip()
        kb_name = self.kb_combo.currentText()
        top_n = self.top_n_spin.value()

        if not os.path.exists(excel_path) or not os.path.exists(tpl_path):
            QMessageBox.warning(self, "错误", "请检查 Excel 或 Word 模板路径是否正确！")
            return

        try:
            # 读取 Excel 前 N 行
            df = pd.read_excel(excel_path, engine='openpyxl')
            # 简单清洗列名
            df.columns = [str(col).strip() for col in df.columns]
            
            if "信号名称" not in df.columns:
                 QMessageBox.warning(self, "格式错误", "Excel 中必须包含列名 '信号名称'！")
                 return

            test_data = df.head(top_n).to_dict('records')
            
            if not test_data:
                QMessageBox.warning(self, "数据为空", "未读取到有效数据。")
                return

            self.log(f"已加载 {len(test_data)} 条测试数据，准备连接知识库 [{kb_name}]...")
            
            # 准备输出目录
            output_dir = os.path.join(self.app.config.project_root, "test_reports")
            os.makedirs(output_dir, exist_ok=True)

            # 启动线程
            self.thread = BatchTestThread(
                self.app.config, 
                self.app.rag_manager, 
                test_data, 
                tpl_path, 
                output_dir,
                kb_name
            )
            self.thread.progress_signal.connect(self.update_progress)
            self.thread.log_signal.connect(self.log)
            self.thread.finished_signal.connect(self.on_finished)
            
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.progress_bar.setValue(0)
            self.thread.start()

        except Exception as e:
            self.log(f"启动失败: {e}")
            QMessageBox.critical(self, "错误", str(e))

    def update_progress(self, current, total, msg):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.app.status_label.setText(msg)
        self.log(msg)

    def on_finished(self, success, msg):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_bar.setValue(self.progress_bar.maximum())
        if success:
            QMessageBox.information(self, "成功", msg)
            self.log("✅ 测试全部完成")
        else:
            QMessageBox.warning(self, "完成", msg)
            self.log("⚠️ 测试结束 (有错误或中断)")

    def stop_test(self):
        if hasattr(self, 'thread'):
            self.thread.stop()
            self.log("正在停止...")
            self.stop_btn.setEnabled(False)