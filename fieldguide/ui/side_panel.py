
"""Guidance + tutorial panel shown on the right of the window."""
from __future__ import annotations

import html
import webbrowser

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtNetwork import (
    QNetworkAccessManager,
    QNetworkReply,
    QNetworkRequest,
)
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..models import Entry, Video
from ..tutorials import TutorialResult


class VideoCard(QFrame):
    """Clickable YouTube tutorial card with thumbnail."""

    clicked = Signal(str)

    def __init__(self, video: Video, parent=None):
        super().__init__(parent)

        self.url = video.url

        self.setObjectName("videoCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.setStyleSheet("""
            QFrame#videoCard {
                background: palette(base);
                border: 1px solid palette(mid);
                border-radius: 8px;
            }

            QFrame#videoCard:hover {
                border: 1px solid #2699b5;
                background: palette(alternate-base);
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        # Thumbnail
        self.thumbnail = QLabel("Loading thumbnail...")
        self.thumbnail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail.setFixedSize(144, 81)
        self.thumbnail.setWordWrap(True)

        self.thumbnail.setStyleSheet("""
            background: #252525;
            color: white;
            border: none;
            border-radius: 5px;
            font-size: 10px;
        """)

        layout.addWidget(self.thumbnail)

        # Video information
        details = QVBoxLayout()
        details.setSpacing(5)

        self.video_title = QLabel(video.title)
        self.video_title.setWordWrap(True)
        self.video_title.setMaximumHeight(42)

        self.video_title.setStyleSheet("""
            font-weight: 600;
            font-size: 12px;
            border: none;
            background: transparent;
        """)

        details.addWidget(self.video_title)

        channel = video.channel.strip() or "YouTube"

        self.channel = QLabel(channel)
        self.channel.setWordWrap(True)

        self.channel.setStyleSheet("""
            color: #888888;
            font-size: 11px;
            border: none;
            background: transparent;
        """)

        details.addWidget(self.channel)

        if video.curated:
            recommended = QLabel("RECOMMENDED")

            recommended.setStyleSheet("""
                color: #16845b;
                font-size: 9px;
                font-weight: bold;
                border: none;
                background: transparent;
            """)

            details.addWidget(recommended)

        details.addStretch()

        layout.addLayout(details, 1)

    def set_thumbnail(self, pixmap: QPixmap):
        if pixmap.isNull():
            self.thumbnail.setText("Thumbnail unavailable")
            return

        scaled = pixmap.scaled(
            self.thumbnail.size(),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )

        x = max(
            0,
            (scaled.width() - self.thumbnail.width()) // 2
        )

        y = max(
            0,
            (scaled.height() - self.thumbnail.height()) // 2
        )

        self.thumbnail.setPixmap(
            scaled.copy(
                x,
                y,
                self.thumbnail.width(),
                self.thumbnail.height(),
            )
        )

        self.thumbnail.setText("")

    def mouseReleaseEvent(self, event):
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self.rect().contains(event.position().toPoint())
        ):
            self.clicked.emit(self.url)

        super().mouseReleaseEvent(event)


class SidePanel(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setMinimumWidth(320)

        self._search_url = ""

        # Asynchronous thumbnail downloading
        self._network = QNetworkAccessManager(self)
        self._thumbnail_replies = {}

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        self.title = QLabel()
        self.title.setStyleSheet(
            "font-size: 18px; font-weight: bold;"
        )
        self.title.setWordWrap(True)

        self.body = QLabel()
        self.body.setWordWrap(True)
        self.body.setTextFormat(Qt.TextFormat.RichText)
        self.body.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.videos_title = QLabel("<b>Tutorial videos</b>")

        self.videos = QListWidget()
        self.videos.setWordWrap(True)
        self.videos.setSpacing(6)
        self.videos.setFrameShape(QFrame.Shape.NoFrame)

        self.videos.setStyleSheet("""
            QListWidget {
                background: transparent;
                border: none;
            }

            QListWidget::item {
                border: none;
                padding: 2px;
            }
        """)

        self.note = QLabel()
        self.note.setWordWrap(True)
        self.note.setStyleSheet("color: #777;")

        self.search_btn = QPushButton("Open YouTube search")
        self.search_btn.clicked.connect(self._open_search)

        for widget in (
            self.title,
            self.body,
            self.videos_title,
            self.videos,
            self.note,
            self.search_btn,
        ):
            layout.addWidget(widget)

        layout.setStretchFactor(self.body, 3)
        layout.setStretchFactor(self.videos, 2)

        self.show_idle()

    # --------------------------------------------------
    # Panel states
    # --------------------------------------------------

    def show_idle(self):
        self.title.setText("FieldGuide")

        self.body.setText(
            "Point the camera at an object. When its box "
            "turns solid, click it to see how to use it "
            "and to find tutorial videos."
        )

        self._set_videos_visible(False)

    def show_message(self, title: str, text: str):
        self.title.setText(title)
        self.body.setText(html.escape(text))

        self._set_videos_visible(False)

    def show_entry(self, entry: Entry, confidence: float):

        self.title.setText(
            f"{entry.display_name} ({int(confidence * 100)}%)"
        )

        parts = []

        if entry.summary:
            parts.append(
                f"<p>{html.escape(entry.summary)}</p>"
            )

        if entry.steps:
            parts.append(
                "<p><b>How to use it</b></p><ol>"
                + "".join(
                    f"<li>{html.escape(step)}</li>"
                    for step in entry.steps
                )
                + "</ol>"
            )

        if entry.cautions:
            parts.append(
                "<p><b>Caution</b></p><ul>"
                + "".join(
                    f"<li>{html.escape(item)}</li>"
                    for item in entry.cautions
                )
                + "</ul>"
            )

        self.body.setText("".join(parts))

        self._clear_video_cards()

        self.note.setText("Looking for tutorials...")

        self._set_videos_visible(True)

    # --------------------------------------------------
    # YouTube tutorial cards
    # --------------------------------------------------

    def set_tutorials(self, result: TutorialResult):

        self._search_url = result.search_url

        self._clear_video_cards()

        for video in result.videos:

            card = VideoCard(video)

            item = QListWidgetItem()
            item.setSizeHint(card.sizeHint())

            self.videos.addItem(item)
            self.videos.setItemWidget(item, card)

            card.clicked.connect(self._open_video)

            self._load_thumbnail(video, card)

        if result.videos:
            self.note.setText(
                result.message
                or "Select a thumbnail to watch the video."
            )
        else:
            self.note.setText(
                result.message
                or "No videos found. Try a YouTube search."
            )

    def _clear_video_cards(self):

        # Cancel outstanding thumbnail requests
        replies = list(self._thumbnail_replies)

        self._thumbnail_replies.clear()

        for reply in replies:
            reply.abort()
            reply.deleteLater()

        self.videos.clear()

    # --------------------------------------------------
    # Thumbnail loading
    # --------------------------------------------------

    def _load_thumbnail(self, video: Video, card: VideoCard):

        # Use the API thumbnail or YouTube's fallback URL
        url = (
            video.thumbnail
            or f"https://i.ytimg.com/vi/{video.video_id}/mqdefault.jpg"
        )

        if not url.startswith("https://"):
            card.thumbnail.setText("Thumbnail unavailable")
            return

        request = QNetworkRequest(QUrl(url))

        reply = self._network.get(request)

        self._thumbnail_replies[reply] = card

        reply.finished.connect(
            lambda r=reply: self._thumbnail_loaded(r)
        )

    def _thumbnail_loaded(self, reply):

        card = self._thumbnail_replies.pop(reply, None)

        if card is not None:

            pixmap = QPixmap()

            if reply.error() == QNetworkReply.NetworkError.NoError:
                pixmap.loadFromData(reply.readAll())

            card.set_thumbnail(pixmap)

        reply.deleteLater()

    # --------------------------------------------------
    # Actions
    # --------------------------------------------------

    def _set_videos_visible(self, visible: bool):

        for widget in (
            self.videos_title,
            self.videos,
            self.note,
            self.search_btn,
        ):
            widget.setVisible(visible)

    @staticmethod
    def _open_video(url: str):

        if url:
            webbrowser.open(url)

    def _open_search(self):

        if self._search_url:
            webbrowser.open(self._search_url)
