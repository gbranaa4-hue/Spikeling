#!/usr/bin/env python3
"""Spikeling Desktop — PyQt5 GUI front end for the Ollama-backed assistant.

Clean dark/light themed chat window with a settings panel:
  - Model switch (llama3.2 / qwen2.5-coder:7b / custom)
  - Temperature + max response length
  - Fact management (view / add / delete) — the RAG memory
  - Theme (dark/light) + font size

Requires Ollama running locally with the chosen model pulled.
Run:  python spikeling_gui.py
Build exe:  python -m PyInstaller --onefile --windowed --name Spikeling spikeling_gui.py
"""

import sys
import os
import re
import sqlite3
import datetime

import requests
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt5.QtGui import QFont, QIcon, QTextCursor
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QLineEdit, QPushButton, QLabel, QComboBox, QSlider,
    QSpinBox, QListWidget, QDialog, QDialogButtonBox, QFormLayout,
    QInputDialog, QMessageBox, QScrollArea, QFrame, QSizePolicy,
)

# ------------------------------------------------------------
# Code extraction + language detection (for "Save to file")
# ------------------------------------------------------------
LANG_EXT = {
    "python": ".py", "py": ".py",
    "gdscript": ".gd", "gd": ".gd", "godot": ".gd",
    "javascript": ".js", "js": ".js", "node": ".js",
    "typescript": ".ts", "ts": ".ts",
    "rust": ".rs", "rs": ".rs",
    "c": ".c", "cpp": ".cpp", "c++": ".cpp",
    "java": ".java", "csharp": ".cs", "cs": ".cs",
    "html": ".html", "css": ".css",
    "bash": ".sh", "sh": ".sh", "shell": ".sh",
    "json": ".json", "sql": ".sql", "go": ".go", "ruby": ".rb",
}


def extract_code_blocks(text):
    blocks = re.findall(r"```([a-zA-Z+#]*)\s*\n(.*?)```", text, re.DOTALL)
    return [(lang.lower().strip(), code.strip()) for lang, code in blocks]


def detect_extension(lang_hint, code):
    if lang_hint in LANG_EXT:
        return LANG_EXT[lang_hint]
    c = code
    if "extends " in c and ("func " in c or "@export" in c or "var " in c):
        return ".gd"
    if re.search(r"\bdef \w+\(.*\):", c) or ("import " in c and "println!" not in c):
        return ".py"
    if "fn main()" in c or "println!" in c or "let mut " in c:
        return ".rs"
    if "function " in c or "const " in c or "=>" in c or "console.log" in c:
        return ".js"
    if "#include" in c:
        return ".c"
    if "<html" in c or "<!DOCTYPE" in c:
        return ".html"
    return ".txt"


def suggest_name(code, ext):
    m = (re.search(r"class_name\s+(\w+)", code)
         or re.search(r"\bclass\s+(\w+)", code)
         or re.search(r"\bdef\s+(\w+)", code)
         or re.search(r"\bfunction\s+(\w+)", code)
         or re.search(r"\bfn\s+(\w+)", code))
    base = m.group(1) if m else "snippet"
    return base + ext


def collision_safe_path(folder, filename):
    """Never overwrite: if name exists, append _1, _2, ..."""
    base, ext = os.path.splitext(filename)
    candidate = os.path.join(folder, filename)
    n = 1
    while os.path.exists(candidate):
        candidate = os.path.join(folder, f"{base}_{n}{ext}")
        n += 1
    return candidate


OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/chat")
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "spikeling_memory.db")

DEFAULT_SYSTEM_PROMPT = (
    "You are Spikeling, a helpful AI assistant. You answer general questions, "
    "explain concepts, and solve and write code. Be direct and concise. When "
    "writing GDScript, target Godot 4 (CharacterBody3D/2D, signal.connect(callable) "
    "syntax) and never use Godot 3 APIs or Python f-strings. If the user has taught "
    "you facts, they appear under KNOWN FACTS — treat them as authoritative and "
    "prefer them over your own assumptions."
)


# ------------------------------------------------------------
# Memory (SQLite) — facts for RAG + conversation history
# ------------------------------------------------------------
class Memory:
    def __init__(self, db_path=DB_PATH):
        self.c = sqlite3.connect(db_path, check_same_thread=False)
        with self.c:
            self.c.execute("""CREATE TABLE IF NOT EXISTS facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT, fact TEXT, ts TEXT)""")
            self.c.execute("""CREATE TABLE IF NOT EXISTS conv (
                id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT, content TEXT, ts TEXT)""")

    def add_fact(self, fact):
        with self.c:
            self.c.execute("INSERT INTO facts (fact, ts) VALUES (?, ?)",
                           (fact, datetime.datetime.now().isoformat()))

    def delete_fact(self, fact_id):
        with self.c:
            self.c.execute("DELETE FROM facts WHERE id=?", (fact_id,))

    def all_facts(self):
        return self.c.execute("SELECT id, fact FROM facts ORDER BY id").fetchall()

    def retrieve(self, query, k=6):
        facts = self.all_facts()
        if not facts:
            return []
        qw = set(query.lower().split())
        scored = sorted(facts, key=lambda f: len(qw & set(f[1].lower().split())), reverse=True)
        hits = [f[1] for f in scored if qw & set(f[1].lower().split())][:k]
        return hits if hits else [f[1] for f in facts[-k:]]

    def add_turn(self, role, content):
        with self.c:
            self.c.execute("INSERT INTO conv (role, content, ts) VALUES (?, ?, ?)",
                           (role, content, datetime.datetime.now().isoformat()))

    def recent_turns(self, n=6):
        rows = self.c.execute("SELECT role, content FROM conv ORDER BY id DESC LIMIT ?",
                              (n,)).fetchall()
        return list(reversed(rows))

    def clear_conversation(self):
        with self.c:
            self.c.execute("DELETE FROM conv")


# ------------------------------------------------------------
# Model worker — runs the Ollama request off the UI thread
# ------------------------------------------------------------
class ModelWorker(QThread):
    finished = pyqtSignal(str)

    def __init__(self, model, messages, options):
        super().__init__()
        self.model = model
        self.messages = messages
        self.options = options

    def run(self):
        try:
            resp = requests.post(OLLAMA_URL, json={
                "model": self.model,
                "messages": self.messages,
                "stream": False,
                "options": self.options,
            }, timeout=300)
            resp.raise_for_status()
            self.finished.emit(resp.json()["message"]["content"])
        except requests.RequestException as e:
            self.finished.emit(
                f"⚠️ Can't reach the model. Is Ollama running and '{self.model}' pulled?\n\n{e}")
        except (KeyError, ValueError) as e:
            self.finished.emit(f"⚠️ Unexpected response: {e}")


# ------------------------------------------------------------
# Settings dialog
# ------------------------------------------------------------
class SettingsDialog(QDialog):
    def __init__(self, parent, state):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(460)
        self.setMinimumHeight(560)
        self.state = dict(state)

        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        scroll.setWidget(inner)
        outer.addWidget(scroll)
        form = QFormLayout(inner)

        self.model_box = QComboBox()
        self.model_box.addItems(["qwen2.5-coder:7b", "llama3.2", "qwen2.5-coder:1.5b"])
        self.model_box.setEditable(True)
        self.model_box.setCurrentText(state["model"])
        form.addRow("Model:", self.model_box)

        self.temp = QSlider(Qt.Horizontal)
        self.temp.setRange(0, 100)
        self.temp.setValue(int(state["temperature"] * 100))
        self.temp_label = QLabel(f"{state['temperature']:.2f}")
        self.temp.valueChanged.connect(lambda v: self.temp_label.setText(f"{v/100:.2f}"))
        trow = QHBoxLayout()
        trow.addWidget(self.temp)
        trow.addWidget(self.temp_label)
        tw = QWidget(); tw.setLayout(trow)
        form.addRow("Temperature:", tw)

        self.maxtok = QSpinBox()
        self.maxtok.setRange(64, 8192)
        self.maxtok.setSingleStep(64)
        self.maxtok.setValue(state["max_tokens"])
        form.addRow("Max response length:", self.maxtok)

        # --- context window (matters for large files) ---
        self.num_ctx = QSpinBox()
        self.num_ctx.setRange(512, 32768)
        self.num_ctx.setSingleStep(512)
        self.num_ctx.setValue(state["num_ctx"])
        self.num_ctx.setToolTip("Bigger = holds more of a file at once, but slower and uses more RAM.")
        form.addRow("Context size (num_ctx):", self.num_ctx)

        # --- sampling controls ---
        self.top_p = QSlider(Qt.Horizontal)
        self.top_p.setRange(0, 100)
        self.top_p.setValue(int(state["top_p"] * 100))
        self.top_p_label = QLabel(f"{state['top_p']:.2f}")
        self.top_p.valueChanged.connect(lambda v: self.top_p_label.setText(f"{v/100:.2f}"))
        prow = QHBoxLayout(); prow.addWidget(self.top_p); prow.addWidget(self.top_p_label)
        pw = QWidget(); pw.setLayout(prow)
        form.addRow("top_p:", pw)

        self.top_k = QSpinBox()
        self.top_k.setRange(0, 200)
        self.top_k.setValue(state["top_k"])
        form.addRow("top_k:", self.top_k)

        self.repeat_pen = QSlider(Qt.Horizontal)
        self.repeat_pen.setRange(80, 200)  # 0.80 .. 2.00
        self.repeat_pen.setValue(int(state["repeat_penalty"] * 100))
        self.rp_label = QLabel(f"{state['repeat_penalty']:.2f}")
        self.repeat_pen.valueChanged.connect(lambda v: self.rp_label.setText(f"{v/100:.2f}"))
        rrow = QHBoxLayout(); rrow.addWidget(self.repeat_pen); rrow.addWidget(self.rp_label)
        rw = QWidget(); rw.setLayout(rrow)
        form.addRow("Repeat penalty:", rw)

        self.theme_box = QComboBox()
        self.theme_box.addItems(["Dark", "Light"])
        self.theme_box.setCurrentText(state["theme"])
        form.addRow("Theme:", self.theme_box)

        self.font_size = QSpinBox()
        self.font_size.setRange(9, 24)
        self.font_size.setValue(state["font_size"])
        form.addRow("Font size:", self.font_size)

        # --- system prompt editor (highest-value: steers behavior) ---
        self.sys_prompt = QTextEdit()
        self.sys_prompt.setPlainText(state["system_prompt"])
        self.sys_prompt.setMinimumHeight(110)
        self.sys_prompt.setToolTip("Instructions that steer every answer. "
                                   "E.g. 'You are a Godot 4 expert. Never use Godot 3 "
                                   "syntax or Python f-strings.'")
        form.addRow("System prompt:", self.sys_prompt)

        reset_sp = QPushButton("Reset system prompt to default")
        reset_sp.clicked.connect(lambda: self.sys_prompt.setPlainText(DEFAULT_SYSTEM_PROMPT))
        form.addRow("", reset_sp)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def result_state(self):
        return {
            "model": self.model_box.currentText(),
            "temperature": self.temp.value() / 100,
            "max_tokens": self.maxtok.value(),
            "num_ctx": self.num_ctx.value(),
            "top_p": self.top_p.value() / 100,
            "top_k": self.top_k.value(),
            "repeat_penalty": self.repeat_pen.value() / 100,
            "theme": self.theme_box.currentText(),
            "font_size": self.font_size.value(),
            "system_prompt": self.sys_prompt.toPlainText().strip() or DEFAULT_SYSTEM_PROMPT,
        }


# ------------------------------------------------------------
# Facts dialog (view / add / delete)
# ------------------------------------------------------------
class FactsDialog(QDialog):
    def __init__(self, parent, memory):
        super().__init__(parent)
        self.memory = memory
        self.setWindowTitle("Known Facts (memory)")
        self.setMinimumSize(480, 360)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Facts Spikeling injects into answers when relevant:"))
        self.listw = QListWidget()
        layout.addWidget(self.listw)

        row = QHBoxLayout()
        add_btn = QPushButton("Add")
        del_btn = QPushButton("Delete selected")
        close_btn = QPushButton("Close")
        add_btn.clicked.connect(self.add_fact)
        del_btn.clicked.connect(self.delete_fact)
        close_btn.clicked.connect(self.accept)
        row.addWidget(add_btn); row.addWidget(del_btn); row.addStretch(); row.addWidget(close_btn)
        layout.addLayout(row)

        self.refresh()

    def refresh(self):
        self.listw.clear()
        self._ids = []
        for fid, fact in self.memory.all_facts():
            self.listw.addItem(fact)
            self._ids.append(fid)

    def add_fact(self):
        text, ok = QInputDialog.getText(self, "Add fact", "Fact:")
        if ok and text.strip():
            self.memory.add_fact(text.strip())
            self.refresh()

    def delete_fact(self):
        idx = self.listw.currentRow()
        if idx < 0:
            return
        self.memory.delete_fact(self._ids[idx])
        self.refresh()


# ------------------------------------------------------------
# Multi-line input box — accepts large pastes, Enter sends,
# Shift+Enter makes a newline. Grows with content up to a cap.
# ------------------------------------------------------------
class ChatInput(QTextEdit):
    submit = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setAcceptRichText(False)  # paste as plain text, strips formatting
        self.setPlaceholderText("Ask anything, or paste code…  (Enter to send, Shift+Enter for newline)")
        self.setTabChangesFocus(False)
        self._min_h = 44
        self._max_h = 200
        self.setFixedHeight(self._min_h)
        self.textChanged.connect(self._autosize)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and not (event.modifiers() & Qt.ShiftModifier):
            self.submit.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def _autosize(self):
        doc_h = int(self.document().size().height()) + 12
        self.setFixedHeight(max(self._min_h, min(self._max_h, doc_h)))


# ------------------------------------------------------------
# Chat message bubble
# ------------------------------------------------------------
class Bubble(QFrame):
    def __init__(self, text, is_user, font_size, theme):
        super().__init__()
        self.setObjectName("userBubble" if is_user else "botBubble")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        label = QLabel(text)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        label.setFont(QFont("Segoe UI", font_size))
        lay.addWidget(label)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)


# ------------------------------------------------------------
# Main window
# ------------------------------------------------------------
class Spikeling(QMainWindow):
    def __init__(self):
        super().__init__()
        self.memory = Memory()
        self.state = {
            "model": os.environ.get("SPIKELING_MODEL", "qwen2.5-coder:7b"),
            "temperature": 0.3,
            "max_tokens": 1024,
            "num_ctx": 4096,
            "top_p": 0.9,
            "top_k": 40,
            "repeat_penalty": 1.1,
            "theme": "Dark",
            "font_size": 12,
            "system_prompt": DEFAULT_SYSTEM_PROMPT,
        }
        self.worker = None
        self.setWindowTitle("Spikeling")
        self.resize(820, 640)
        self._build_ui()
        self.apply_theme()
        self._check_backend()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header bar
        header = QWidget()
        header.setObjectName("header")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(16, 10, 16, 10)
        title = QLabel("🧠 Spikeling")
        title.setObjectName("title")
        self.status = QLabel("…")
        self.status.setObjectName("status")
        facts_btn = QPushButton("Facts")
        clear_btn = QPushButton("New chat")
        settings_btn = QPushButton("⚙ Settings")
        facts_btn.clicked.connect(self.open_facts)
        clear_btn.clicked.connect(self.clear_conversation)
        settings_btn.clicked.connect(self.open_settings)
        hl.addWidget(title)
        hl.addSpacing(12)
        hl.addWidget(self.status)
        hl.addStretch()
        hl.addWidget(facts_btn)
        hl.addWidget(clear_btn)
        hl.addWidget(settings_btn)
        root.addWidget(header)

        # Chat scroll area
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setObjectName("chatArea")
        self.chat_container = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setAlignment(Qt.AlignTop)
        self.chat_layout.setContentsMargins(16, 16, 16, 16)
        self.chat_layout.setSpacing(10)
        self.scroll.setWidget(self.chat_container)
        root.addWidget(self.scroll, 1)

        # Input row
        inp = QWidget()
        inp.setObjectName("inputbar")
        il = QHBoxLayout(inp)
        il.setContentsMargins(16, 12, 16, 12)
        self.input = ChatInput()
        self.input.submit.connect(self.send)
        send_btn = QPushButton("Send")
        send_btn.clicked.connect(self.send)
        il.addWidget(self.input, 1)
        il.addWidget(send_btn, 0, Qt.AlignBottom)
        root.addWidget(inp)

        self.add_bubble("Hi! I'm Spikeling. Ask me anything, or teach me facts with "
                        "'remember that …'. Open Settings to switch models or themes.",
                        is_user=False)

    # ---- chat helpers ----
    def add_bubble(self, text, is_user):
        col = QVBoxLayout()
        col.setSpacing(4)
        bubble = Bubble(text, is_user, self.state["font_size"], self.state["theme"])
        bubble.setMaximumWidth(int(self.width() * 0.72))
        col.addWidget(bubble)

        # If a bot message contains code blocks, offer to save each
        if not is_user:
            blocks = extract_code_blocks(text)
            if blocks:
                btn_row = QHBoxLayout()
                btn_row.setContentsMargins(2, 0, 2, 0)
                label = "💾 Save to file" if len(blocks) == 1 else f"💾 Save {len(blocks)} files"
                save_btn = QPushButton(label)
                save_btn.setMaximumWidth(180)
                save_btn.clicked.connect(lambda _, b=blocks: self.save_code_blocks(b))
                btn_row.addWidget(save_btn)
                btn_row.addStretch()
                col.addLayout(btn_row)

        row = QHBoxLayout()
        inner = QWidget()
        inner.setLayout(col)
        if is_user:
            row.addStretch()
            row.addWidget(inner)
        else:
            row.addWidget(inner)
            row.addStretch()
        wrap = QWidget()
        wrap.setLayout(row)
        self.chat_layout.addWidget(wrap)
        QApplication.processEvents()
        self.scroll.verticalScrollBar().setValue(self.scroll.verticalScrollBar().maximum())

    def save_code_blocks(self, blocks):
        # Ask for a destination folder (typed path, per your preference)
        folder, ok = QInputDialog.getText(
            self, "Save location",
            "Folder path to save into:",
            text=os.path.expanduser("~"))
        if not ok or not folder.strip():
            return
        folder = folder.strip()
        if not os.path.isdir(folder):
            QMessageBox.warning(self, "Spikeling",
                                f"Folder doesn't exist:\n{folder}")
            return
        saved = []
        for lang_hint, code in blocks:
            ext = detect_extension(lang_hint, code)
            name = suggest_name(code, ext)
            path = collision_safe_path(folder, name)  # never overwrites
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(code + "\n")
                saved.append(os.path.basename(path))
            except OSError as e:
                QMessageBox.warning(self, "Spikeling", f"Couldn't save {name}:\n{e}")
                return
        QMessageBox.information(
            self, "Spikeling",
            "Saved:\n  " + "\n  ".join(saved) + f"\n\nin {folder}")

    # ---- send / receive ----
    def send(self):
        text = self.input.toPlainText().strip()
        if not text:
            return
        self.input.clear()
        self.add_bubble(text, is_user=True)

        low = text.lower()
        if low.startswith("remember that "):
            fact = text[len("remember that "):].strip()
            if fact:
                self.memory.add_fact(fact)
                self.add_bubble(f"✅ Got it. I'll remember: {fact}", is_user=False)
            return
        if low == "facts":
            facts = self.memory.all_facts()
            msg = "\n".join(f"• {f}" for _, f in facts) if facts else "No facts stored yet."
            self.add_bubble("🧠 Known facts:\n" + msg, is_user=False)
            return

        # Build context with retrieved facts
        system = self.state["system_prompt"]
        hits = self.memory.retrieve(text)
        if hits:
            system += "\n\nKNOWN FACTS:\n" + "\n".join(f"- {h}" for h in hits)
        messages = [{"role": "system", "content": system}]
        for role, content in self.memory.recent_turns(6):
            messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": text})

        self.thinking = Bubble("…thinking…", False, self.state["font_size"], self.state["theme"])
        trow = QHBoxLayout(); trow.addWidget(self.thinking); trow.addStretch()
        self.thinking_wrap = QWidget(); self.thinking_wrap.setLayout(trow)
        self.chat_layout.addWidget(self.thinking_wrap)

        options = {
            "temperature": self.state["temperature"],
            "num_predict": self.state["max_tokens"],
            "num_ctx": self.state["num_ctx"],
            "top_p": self.state["top_p"],
            "top_k": self.state["top_k"],
            "repeat_penalty": self.state["repeat_penalty"],
        }
        self.worker = ModelWorker(self.state["model"], messages, options)
        self.worker.finished.connect(lambda ans, q=text: self.on_answer(ans, q))
        self.worker.start()

    def on_answer(self, answer, query):
        self.thinking_wrap.setParent(None)
        self.add_bubble(answer, is_user=False)
        self.memory.add_turn("user", query)
        self.memory.add_turn("assistant", answer)

    # ---- dialogs ----
    def open_settings(self):
        dlg = SettingsDialog(self, self.state)
        if dlg.exec_():
            self.state.update(dlg.result_state())
            self.apply_theme()
            self._check_backend()

    def open_facts(self):
        FactsDialog(self, self.memory).exec_()

    def clear_conversation(self):
        resp = QMessageBox.question(
            self, "New chat",
            "Clear the current conversation? (Your saved facts are kept.)",
            QMessageBox.Yes | QMessageBox.No)
        if resp != QMessageBox.Yes:
            return
        self.memory.clear_conversation()
        # wipe on-screen bubbles
        while self.chat_layout.count():
            item = self.chat_layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
        self.add_bubble("New chat started. Previous messages cleared (facts kept).",
                        is_user=False)

    # ---- backend status ----
    def _check_backend(self):
        try:
            base = OLLAMA_URL.rsplit("/api/", 1)[0]
            requests.get(base, timeout=2)
            self.status.setText(f"● {self.state['model']}")
            self.status.setStyleSheet("color:#4ade80;")
        except requests.RequestException:
            self.status.setText("● Ollama offline")
            self.status.setStyleSheet("color:#f87171;")

    # ---- theming ----
    def apply_theme(self):
        dark = self.state["theme"] == "Dark"
        fs = self.state["font_size"]
        if dark:
            bg, panel, text, user_b, bot_b, accent = (
                "#0f1117", "#171a21", "#e6e6e6", "#2563eb", "#262b36", "#3b82f6")
        else:
            bg, panel, text, user_b, bot_b, accent = (
                "#f5f6f8", "#ffffff", "#1a1a1a", "#2563eb", "#e7eaf0", "#2563eb")
        self.setStyleSheet(f"""
            QMainWindow, QWidget {{ background:{bg}; color:{text}; font-size:{fs}px; }}
            #header {{ background:{panel}; border-bottom:1px solid rgba(128,128,128,0.2); }}
            #title {{ font-size:{fs+5}px; font-weight:600; }}
            #status {{ font-size:{fs-1}px; }}
            #chatArea {{ background:{bg}; border:none; }}
            #inputbar {{ background:{panel}; border-top:1px solid rgba(128,128,128,0.2); }}
            QLineEdit, QTextEdit {{ background:{bg}; color:{text}; border:1px solid rgba(128,128,128,0.3);
                         border-radius:14px; padding:8px 14px; font-size:{fs}px; }}
            QLineEdit:focus, QTextEdit:focus {{ border:1px solid {accent}; }}
            QPushButton {{ background:{accent}; color:white; border:none; border-radius:16px;
                           padding:9px 18px; font-weight:600; }}
            QPushButton:hover {{ background:#1d4ed8; }}
            #userBubble {{ background:{user_b}; color:white; border-radius:16px; }}
            #botBubble {{ background:{bot_b}; color:{text}; border-radius:16px; }}
            QListWidget, QComboBox, QSpinBox {{ background:{panel}; color:{text};
                           border:1px solid rgba(128,128,128,0.3); border-radius:6px; padding:4px; }}
            QScrollBar:vertical {{ background:transparent; width:10px; }}
            QScrollBar::handle:vertical {{ background:rgba(128,128,128,0.4); border-radius:5px; }}
        """)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Spikeling")
    win = Spikeling()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()