"""Guidance + tutorial panel shown on the right of the window."""
from __future__ import annotations

import html
import webbrowser

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QLabel, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget)

from ..models import Entry, Video
from ..tutorials import TutorialResult


class SidePanel(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(320)
        self._search_url = ""
        lay = QVBoxLayout(self)
        self.title = QLabel()
        self.title.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.title.setWordWrap(True)
        self.body = QLabel()
        self.body.setWordWrap(True)
        self.body.setTextFormat(Qt.TextFormat.RichText)
        self.body.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.videos_title = QLabel("<b>Tutorial videos</b>")
        self.videos = QListWidget()
        self.videos.setWordWrap(True)
        self.videos.itemActivated.connect(self._open_item)
        self.videos.itemClicked.connect(self._open_item)
        self.note = QLabel()
        self.note.setWordWrap(True)
        self.note.setStyleSheet("color: #666;")
        self.search_btn = QPushButton("Open YouTube search")
        self.search_btn.clicked.connect(self._open_search)
        for w in (self.title, self.body, self.videos_title, self.videos, self.note, self.search_btn):
            lay.addWidget(w)
        lay.setStretchFactor(self.body, 3)
        lay.setStretchFactor(self.videos, 2)
        self.show_idle()

    # -- states ----------------------------------------------------------
    def show_idle(self) -> None:
        self.title.setText("FieldGuide")
        self.body.setText("Point the camera at an object. When its box turns solid, click it to see "
                          "how to use it and to find tutorial videos.")
        self._set_videos_visible(False)

    def show_message(self, title: str, text: str) -> None:
        self.title.setText(title)
        self.body.setText(html.escape(text))
        self._set_videos_visible(False)

    def show_entry(self, entry: Entry, confidence: float) -> None:
        self.title.setText(f"{entry.display_name}  ({int(confidence * 100)}%)")
        parts = []
        if entry.summary:
            parts.append(f"<p>{html.escape(entry.summary)}</p>")
        if entry.steps:
            parts.append("<p><b>How to use it</b></p><ol>" +
                         "".join(f"<li>{html.escape(s)}</li>" for s in entry.steps) + "</ol>")
        if entry.cautions:
            parts.append("<p><b>Caution</b></p><ul>" +
                         "".join(f"<li>{html.escape(c)}</li>" for c in entry.cautions) + "</ul>")
        self.body.setText("".join(parts))
        self.videos.clear()
        self.note.setText("Looking for tutorials...")
        self._set_videos_visible(True)

    def set_tutorials(self, result: TutorialResult) -> None:
        self._search_url = result.search_url
        self.videos.clear()
        for v in result.videos:
            tag = "  (recommended)" if v.curated else ""
            item = QListWidgetItem(f"{v.title}\n{v.channel}{tag}")
            item.setData(Qt.ItemDataRole.UserRole, v.url)
            self.videos.addItem(item)
        self.note.setText(result.message or ("Click a video to open it in your browser."
                                              if result.videos else "No videos found."))

    # -- actions ---------------------------------------------------------
    def _set_videos_visible(self, on: bool) -> None:
        for w in (self.videos_title, self.videos, self.note, self.search_btn):
            w.setVisible(on)

    def _open_item(self, item: QListWidgetItem) -> None:
        url = item.data(Qt.ItemDataRole.UserRole)
        if url:
            webbrowser.open(url)

    def _open_search(self) -> None:
        if self._search_url:
            webbrowser.open(self._search_url)
