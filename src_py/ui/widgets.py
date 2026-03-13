"""
自定义 UI 控件：ChatBubble, AutoExpandTextEdit, CCppHighlighter, FileDragTextEdit
"""

import markdown
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLabel, QTextEdit
from PyQt5.QtCore import Qt, QRegExp, pyqtSignal
from PyQt5.QtGui import QFont, QSyntaxHighlighter, QTextCharFormat, QColor


class ChatBubble(QWidget):
    """自定义聊天气泡控件"""

    def __init__(self, text, is_user=False, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 5, 10, 5)
        self.setLayout(layout)

        self.label = QLabel()
        self.label.setWordWrap(True)
        self.label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.label.setFont(QFont("Microsoft YaHei", 10))

        if not is_user:
            try:
                html = markdown.markdown(text)
                self.label.setText(html)
                self.label.setOpenExternalLinks(True)
            except Exception:
                self.label.setText(text)
        else:
            self.label.setText(text)

        if is_user:
            bg_color = "#95EC69"
            text_color = "black"
            layout.addStretch()
            layout.addWidget(self.label)
        else:
            bg_color = "#FFFFFF"
            text_color = "black"
            layout.addWidget(self.label)
            layout.addStretch()

        self.label.setStyleSheet(f"""
            QLabel {{
                background-color: {bg_color};
                color: {text_color};
                border-radius: 10px;
                padding: 10px;
                border: 1px solid #E0E0E0;
            }}
        """)
        self.label.setMaximumWidth(600)
        self.label.setAlignment(Qt.AlignLeft)


class AutoExpandTextEdit(QTextEdit):
    """自动根据内容高度调整大小的输入框"""
    submit_signal = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.min_height = 40
        self.max_height = 220
        self.setFixedHeight(self.min_height)
        self.textChanged.connect(self.fit_height_to_content)
        self.setStyleSheet("""
            QTextEdit {
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 5px;
                background-color: white;
                font-size: 14px;
            }
        """)

    def fit_height_to_content(self):
        doc_height = self.document().size().height()
        new_height = max(self.min_height, min(int(doc_height + 10), self.max_height))
        self.setFixedHeight(new_height)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if event.modifiers() & Qt.ControlModifier:
                self.submit_signal.emit()
                return
        super().keyPressEvent(event)


class FileDragTextEdit(QTextEdit):
    """支持拖入文件路径的文本框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def insertFromMimeData(self, source):
        if source.hasUrls():
            paths = []
            for url in source.urls():
                if url.isLocalFile():
                    paths.append(url.toLocalFile())
            if paths:
                self.insertPlainText("\n".join(paths) + "\n")
        else:
            super().insertFromMimeData(source)


class CCppHighlighter(QSyntaxHighlighter):
    """C/C++ 语法高亮器"""

    def __init__(self, document):
        super().__init__(document)
        self.highlighting_rules = []

        # 变量 / 标识符 (浅蓝)
        variable_format = QTextCharFormat()
        variable_format.setForeground(QColor("#9CDCFE"))
        self.highlighting_rules.append((QRegExp("\\b[A-Za-z_][A-Za-z0-9_]*\\b"), variable_format))

        # 运算符 / 标点 (金色)
        operator_format = QTextCharFormat()
        operator_format.setForeground(QColor("#FFD700"))
        self.highlighting_rules.append((QRegExp("[\\(\\)\\[\\]\\{\\};,=\\+\\-\\*\\/<>]"), operator_format))

        # 关键字 (深蓝 + 粗体)
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#569CD6"))
        keyword_format.setFontWeight(QFont.Bold)
        keywords = [
            "char", "class", "const", "double", "enum", "explicit",
            "friend", "inline", "int", "long", "namespace", "operator",
            "private", "protected", "public", "short", "signals", "signed",
            "slots", "static", "struct", "template", "typedef", "typename",
            "union", "unsigned", "virtual", "void", "volatile", "bool",
            "uint8_t", "uint16_t", "uint32_t", "int8_t", "size_t", "float",
        ]
        for word in keywords:
            self.highlighting_rules.append((QRegExp(f"\\b{word}\\b"), keyword_format))

        # 控制流 (紫色)
        control_format = QTextCharFormat()
        control_format.setForeground(QColor("#C586C0"))
        for word in [
            "asm", "break", "case", "catch", "continue", "default", "delete",
            "do", "else", "for", "goto", "if", "new", "return", "switch",
            "throw", "try", "while",
        ]:
            self.highlighting_rules.append((QRegExp(f"\\b{word}\\b"), control_format))

        # 数字 (浅绿)
        number_format = QTextCharFormat()
        number_format.setForeground(QColor("#B5CEA8"))
        self.highlighting_rules.append((QRegExp("\\b[0-9]+\\b"), number_format))
        self.highlighting_rules.append((QRegExp("\\b0x[0-9a-fA-F]+\\b"), number_format))
        self.highlighting_rules.append((QRegExp("\\b[0-9]*\\.[0-9]+\\b"), number_format))

        # 函数名 (浅黄)
        function_format = QTextCharFormat()
        function_format.setForeground(QColor("#DCDCAA"))
        self.highlighting_rules.append((QRegExp("\\b[A-Za-z0-9_]+(?=\\()"), function_format))

        # 预处理指令 (紫)
        preprocessor_format = QTextCharFormat()
        preprocessor_format.setForeground(QColor("#C586C0"))
        self.highlighting_rules.append((QRegExp("^#[^\\n]*"), preprocessor_format))

        # 字符串 (橙色)
        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#CE9178"))
        self.highlighting_rules.append((QRegExp('".*"'), string_format))
        self.highlighting_rules.append((QRegExp("'.*'"), string_format))

        # 注释 (绿色)
        self.comment_format = QTextCharFormat()
        self.comment_format.setForeground(QColor("#6A9955"))
        self.highlighting_rules.append((QRegExp("//[^\\n]*"), self.comment_format))

        self.comment_start_expression = QRegExp("/\\*")
        self.comment_end_expression = QRegExp("\\*/")

    def highlightBlock(self, text):
        for pattern, fmt in self.highlighting_rules:
            expression = QRegExp(pattern)
            index = expression.indexIn(text)
            while index >= 0:
                length = expression.matchedLength()
                self.setFormat(index, length, fmt)
                index = expression.indexIn(text, index + length)

        self.setCurrentBlockState(0)
        if self.previousBlockState() == 1:
            start_index = 0
        else:
            start_index = self.comment_start_expression.indexIn(text)

        while start_index >= 0:
            end_index = self.comment_end_expression.indexIn(text, start_index)
            if end_index == -1:
                self.setCurrentBlockState(1)
                comment_length = len(text) - start_index
            else:
                comment_length = end_index - start_index + self.comment_end_expression.matchedLength()
            self.setFormat(start_index, comment_length, self.comment_format)
            start_index = self.comment_start_expression.indexIn(text, start_index + comment_length)
