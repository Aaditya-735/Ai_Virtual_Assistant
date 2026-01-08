# GUI.py - corrected version
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTextEdit, QStackedWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFrame, QLabel, QSizePolicy
)
from PyQt5.QtGui import QIcon, QMovie, QColor, QTextCharFormat, QFont, QPixmap, QTextBlockFormat, QPainter
from PyQt5.QtCore import Qt, QSize, QTimer
from dotenv import dotenv_values
import sys
import os

# Load env
env_vars = dotenv_values(".env")
Assistantname = env_vars.get("Assistantname", "Assistant")

# Resolve directories in a safe, cross-platform way
current_dir = os.getcwd()
TempDirPath = os.path.join(current_dir, "Frontend", "Files")
GraphDirPath = os.path.join(current_dir, "Frontend", "Graphics")

# Ensure directories exist (creates if missing)
os.makedirs(TempDirPath, exist_ok=True)
os.makedirs(GraphDirPath, exist_ok=True)

# State
old_chat_message = ""

# Utility functions ---------------------------------------------------------
def AnswerModifier(Answer):
    lines = Answer.split("\n")
    non_empty_lines = [line for line in lines if line.strip()]
    modified_answer = "\n".join(non_empty_lines)
    return modified_answer

def QueryModifier(Query):
    if not isinstance(Query, str):
        return ""

    new_query = Query.lower().strip()
    if not new_query:
        return ""

    question_words = ["how", "what", "who", "where", "when", "why", "which", "whose", "whom", "can you", "what's", "where's", "how's"]
    last_char = new_query[-1]
    is_question = any(qword in new_query for qword in question_words)

    if is_question:
        if last_char in [".", "?", "!"]:
            new_query = new_query[:-1] + "?"
        else:
            new_query += "?"
    else:
        if last_char in [".", "?", "!"]:
            new_query = new_query[:-1] + "."
        else:
            new_query += "."

    return new_query.capitalize()

def GraphicsDirectoryPath(Filename):
    return os.path.join(GraphDirPath, Filename)

def TempDirectoryPath(Filename):
    return os.path.join(TempDirPath, Filename)

def setMicrophoneStatus(command):
    try:
        with open(TempDirectoryPath("Mic.data"), "w", encoding="utf-8") as file:
            file.write(str(command))
    except Exception:
        # fail silently here — GUI should not crash
        pass

def GetMicrophoneStatus():
    try:
        with open(TempDirectoryPath("Mic.data"), "r", encoding="utf-8") as file:
            Status = file.read()
        return Status
    except Exception:
        return "False"

def SetAssistantStatus(Status):
    try:
        with open(TempDirectoryPath("Status.data"), "w", encoding="utf-8") as file:
            file.write(str(Status))
    except Exception:
        pass

def GetAssistantStatus():
    try:
        with open(TempDirectoryPath("Status.data"), "r", encoding="utf-8") as file:
            Status = file.read()
        return Status
    except Exception:
        return ""

def MicButtonInitialed():
    setMicrophoneStatus("False")

def MicButtonClosed():
    setMicrophoneStatus("True")

def ShowTextToScreen(Text):
    try:
        with open(TempDirectoryPath("Responses.data"), "w", encoding="utf-8") as file:
            file.write(str(Text))
    except Exception:
        pass

# ChatSection widget -------------------------------------------------------
class ChatSection(QWidget):
    def __init__(self):
        super(ChatSection, self).__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 40, 0, 100)
        layout.setSpacing(10)

        # Chat text area
        self.chat_text_edit = QTextEdit()
        self.chat_text_edit.setReadOnly(True)
        # disable selection/copy if desired:
        self.chat_text_edit.setTextInteractionFlags(Qt.NoTextInteraction)
        self.chat_text_edit.setFrameStyle(QFrame.NoFrame)
        layout.addWidget(self.chat_text_edit)

        # Styling
        self.setStyleSheet("background-color: black;")
        self.setSizePolicy(QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding))

        # Text default format
        text_color_text = QTextCharFormat()
        text_color_text.setForeground(QColor(Qt.blue))
        self.chat_text_edit.setCurrentCharFormat(text_color_text)

        # Gif label (on the right/bottom)
        self.gif_label = QLabel()
        self.gif_label.setStyleSheet("border: none;")
        movie_path = GraphicsDirectoryPath("jarvis.gif")
        if os.path.exists(movie_path):
            movie = QMovie(movie_path)
            max_gif_size_W = 480
            max_gif_size_H = 270
            movie.setScaledSize(QSize(max_gif_size_W, max_gif_size_H))
            self.gif_label.setAlignment(Qt.AlignRight | Qt.AlignBottom)
            self.gif_label.setMovie(movie)
            movie.start()
        layout.addWidget(self.gif_label, alignment=Qt.AlignRight)

        # A small status label
        self.label = QLabel("")
        self.label.setStyleSheet("color: white; font-size:16px; border: none;")
        self.label.setAlignment(Qt.AlignRight)
        layout.addWidget(self.label)

        # Font for the chat area
        font = QFont()
        font.setPointSize(13)
        self.chat_text_edit.setFont(font)

        # Timer - poll every 500 ms (not 5 ms)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.loadMessages)
        self.timer.timeout.connect(self.SpeechRecogText)
        self.timer.start(500)

        # scrollbar style
        self.chat_text_edit.setStyleSheet("""
            QScrollBar:vertical {
                border: none;
                background: black;
                width: 10px;
                margin: 0px 0px 0px 0px;
            }
            QScrollBar::handle:vertical {
                background: white;
                min-height: 20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                background: black;
                height: 10px;
            }
            QScrollBar::up-arrow:vertical, QScrollBar::down-arrow:vertical {
                border: none;
                background: none;
                color: none;
            }
        """)

    def loadMessages(self):
        global old_chat_message
        try:
            path = TempDirectoryPath("Responses.data")
            if not os.path.exists(path):
                return
            with open(path, "r", encoding="utf-8") as file:
                messages = file.read()

            if not messages or len(messages) <= 1:
                return

            if str(old_chat_message) == str(messages):
                return

            self.addMessage(message=messages, color="white")
            old_chat_message = messages
        except Exception:
            # don't crash GUI on read errors
            return

    def SpeechRecogText(self):
        try:
            path = TempDirectoryPath("Status.data")
            if not os.path.exists(path):
                self.label.setText("")
                return
            with open(path, "r", encoding="utf-8") as file:
                messages = file.read()
            self.label.setText(messages)
        except Exception:
            self.label.setText("")

    def addMessage(self, message, color="white"):
        cursor = self.chat_text_edit.textCursor()
        fmt = QTextCharFormat()
        block_fmt = QTextBlockFormat()
        block_fmt.setTopMargin(10)
        block_fmt.setLeftMargin(10)
        fmt.setForeground(QColor(color))
        cursor.setCharFormat(fmt)
        cursor.setBlockFormat(block_fmt)
        cursor.insertText(str(message) + "\n")
        self.chat_text_edit.setTextCursor(cursor)

# Initial screen -----------------------------------------------------------
class InitialScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        desktop = QApplication.desktop()
        screen_width = desktop.screenGeometry().width()
        screen_height = desktop.screenGeometry().height()

        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)

        gif_label = QLabel()
        movie_path = GraphicsDirectoryPath("jarvis.gif")
        if os.path.exists(movie_path):
            movie = QMovie(movie_path)
            max_gif_size_H = int(screen_width / 16 * 9)
            movie.setScaledSize(QSize(screen_width, max_gif_size_H))
            gif_label.setMovie(movie)
            movie.start()
        gif_label.setAlignment(Qt.AlignCenter)
        gif_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # mic icon label
        self.icon_label = QLabel()
        pixmap_path = GraphicsDirectoryPath("mic_on.png")
        if os.path.exists(pixmap_path):
            pixmap = QPixmap(pixmap_path)
            new_pixmap = pixmap.scaled(60, 60)
            self.icon_label.setPixmap(new_pixmap)
        self.icon_label.setFixedSize(150, 150)
        self.icon_label.setAlignment(Qt.AlignCenter)

        # toggled state
        self.toggled = True
        self.icon_label.mousePressEvent = self.toggle_icon

        # status label
        self.label = QLabel("")
        self.label.setStyleSheet("color: white; font-size:16px; margin-bottom:0;")
        self.label.setAlignment(Qt.AlignCenter)

        content_layout.addWidget(gif_label, alignment=Qt.AlignCenter)
        content_layout.addWidget(self.label, alignment=Qt.AlignCenter)
        content_layout.addWidget(self.icon_label, alignment=Qt.AlignCenter)
        content_layout.setContentsMargins(0, 0, 0, 150)
        self.setLayout(content_layout)

        # Make full-screen-ish sizes (same as original approach)
        self.setFixedHeight(screen_height)
        self.setFixedWidth(screen_width)
        self.setStyleSheet("background-color: black;")

        # Timer to update status (every 500ms)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.SpeechRecogText)
        self.timer.start(500)

    def SpeechRecogText(self):
        try:
            path = TempDirectoryPath("Status.data")
            if not os.path.exists(path):
                self.label.setText("")
                return
            with open(path, "r", encoding="utf-8") as file:
                messages = file.read()
            self.label.setText(messages)
        except Exception:
            self.label.setText("")

    def load_icon(self, path, width=60, height=60):
        if not os.path.exists(path):
            return
        pixmap = QPixmap(path)
        new_pixmap = pixmap.scaled(width, height)
        self.icon_label.setPixmap(new_pixmap)

    def toggle_icon(self, event=None):
        if self.toggled:
            self.load_icon(GraphicsDirectoryPath("mic_on.png"), 60, 60)
            MicButtonInitialed()
        else:
            self.load_icon(GraphicsDirectoryPath("mic_off.png"), 60, 60)
            MicButtonClosed()
        self.toggled = not self.toggled

# Message screen -----------------------------------------------------------
class MessageScreen(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        desktop = QApplication.desktop()
        screen_width = desktop.screenGeometry().width()
        screen_height = desktop.screenGeometry().height()

        layout = QVBoxLayout()
        label = QLabel("")
        layout.addWidget(label)
        chat_section = ChatSection()
        layout.addWidget(chat_section)
        self.setLayout(layout)
        self.setStyleSheet("background-color: black;")
        self.setFixedHeight(screen_height)
        self.setFixedWidth(screen_width)

# Custom top bar -----------------------------------------------------------
class CustomTopBar(QWidget):
    def __init__(self, parent, stacked_widget):
        super().__init__(parent)
        self.stacked_widget = stacked_widget
        self.initUI()

    def initUI(self):
        self.setFixedHeight(50)
        layout = QHBoxLayout(self)
        layout.setAlignment(Qt.AlignRight)

        # Home button
        home_button = QPushButton()
        home_icon = QIcon(GraphicsDirectoryPath("home.jpg"))
        home_button.setIcon(home_icon)
        home_button.setText(" Home")
        home_button.setStyleSheet("height:40px; line-height:40px; background-color:white; color:black")

        # Message button
        message_button = QPushButton()
        message_icon = QIcon(GraphicsDirectoryPath("chat.png"))
        message_button.setIcon(message_icon)
        message_button.setText(" Chat")
        message_button.setStyleSheet("height:40px; line-height:40px; background-color:white; color:black")

        # Minimize
        minimize_button = QPushButton()
        minimize_icon = QIcon(GraphicsDirectoryPath("minimise2.png"))
        minimize_button.setIcon(minimize_icon)
        minimize_button.setStyleSheet("background-color:white")
        minimize_button.clicked.connect(self.minimizeWindow)

        # Maximize/restore
        self.maximize_button = QPushButton()
        self.maximize_icon = QIcon(GraphicsDirectoryPath("maximise.png"))
        self.restore_icon = QIcon(GraphicsDirectoryPath("minimise.png"))
        self.maximize_button.setIcon(self.maximize_icon)
        self.maximize_button.setFlat(True)
        self.maximize_button.setStyleSheet("background-color:white")
        self.maximize_button.clicked.connect(self.maximizeWindow)

        # Close
        close_button = QPushButton()
        close_icon = QIcon(GraphicsDirectoryPath("cross.png"))
        close_button.setIcon(close_icon)
        close_button.setStyleSheet("background-color:white")
        close_button.clicked.connect(self.closeWindow)

        title_label = QLabel(f" {str(Assistantname).capitalize()} AI   ")
        title_label.setStyleSheet("color: black; font-size: 18px; background-color:white")

        # connect stacked widget buttons
        home_button.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(0))
        message_button.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(1))

        # layout placement
        layout.addWidget(title_label)
        layout.addStretch(1)
        layout.addWidget(home_button)
        layout.addWidget(message_button)
        layout.addStretch(1)
        layout.addWidget(minimize_button)
        layout.addWidget(self.maximize_button)
        layout.addWidget(close_button)

        # draggable window support
        self.draggable = True
        self.offset = None

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.white)
        super().paintEvent(event)

    def minimizeWindow(self):
        self.parent().showMinimized()

    def maximizeWindow(self):
        if self.parent().isMaximized():
            self.parent().showNormal()
            self.maximize_button.setIcon(self.maximize_icon)
        else:
            self.parent().showMaximized()
            self.maximize_button.setIcon(self.restore_icon)

    def closeWindow(self):
        self.parent().close()

    def mousePressEvent(self, event):
        if self.draggable:
            self.offset = event.pos()

    def mouseMoveEvent(self, event):
        # move the parent window while dragging the top bar
        if self.draggable and self.offset and event.buttons() & Qt.LeftButton:
            new_pos = event.globalPos() - self.offset
            # Move the parent (MainWindow)
            try:
                self.parent().move(new_pos)
            except Exception:
                pass

# Main window --------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # Frameless window like original
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.initUI()

    def initUI(self):
        desktop = QApplication.desktop()
        screen_width = desktop.screenGeometry().width()
        screen_height = desktop.screenGeometry().height()

        stacked_widget = QStackedWidget(self)
        initial_screen = InitialScreen()
        message_screen = MessageScreen()
        stacked_widget.addWidget(initial_screen)
        stacked_widget.addWidget(message_screen)

        self.setGeometry(0, 0, screen_width, screen_height)
        self.setStyleSheet("background-color: black;")
        top_bar = CustomTopBar(self, stacked_widget)
        self.setMenuWidget(top_bar)
        self.setCentralWidget(stacked_widget)

# Entry point --------------------------------------------------------------
def GraphicalUserInterface():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    GraphicalUserInterface()
