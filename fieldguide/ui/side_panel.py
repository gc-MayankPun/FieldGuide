
"""Guidance panel with object instructions, speech controls and YouTube tutorials."""
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
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    QStyle,
)

from ..models import Entry, Video
from ..tutorials import TutorialResult


STYLE = """
QWidget#sidePanel {
    background: palette(window);
}

QLabel {
    color: palette(window-text);
    background: transparent;
}

QLabel#eyebrow {
    color: palette(mid);
    font-size: 10px;
    font-weight: bold;
    letter-spacing: 1px;
}

QLabel#objectTitle {
    font-size: 21px;
    font-weight: 700;
}

QLabel#confidence {
    background: palette(alternate-base);
    border: 1px solid palette(mid);
    border-radius: 5px;
    padding: 5px 8px;
    font-size: 11px;
    font-weight: bold;
}

QLabel#body {
    font-size: 12px;
}

QFrame#separator {
    background: palette(mid);
    max-height: 1px;
    border: none;
}

QFrame#videoCard {
    background: palette(base);
    border: 1px solid palette(mid);
    border-radius: 7px;
}

QFrame#videoCard:hover {
    border: 1px solid #2699b5;
}

QLabel#videoTitle {
    font-size: 11px;
    font-weight: 600;
}

QLabel#channel {
    color: palette(mid);
    font-size: 10px;
}

QLabel#recommended {
    color: #16845b;
    font-size: 9px;
    font-weight: bold;
}

QPushButton#speakButton {
    background: palette(base);
    color: palette(window-text);
    border: 1px solid #2699b5;
    border-radius: 6px;
    padding: 9px 12px;
    font-size: 11px;
    font-weight: 600;
    text-align: left;
}

QPushButton#speakButton:hover {
    background: palette(alternate-base);
}

QPushButton#speakButton:disabled {
    color: palette(mid);
    border-color: palette(mid);
}

QPushButton#searchButton {
    background: palette(base);
    color: palette(window-text);
    border: 1px solid palette(mid);
    border-radius: 6px;
    padding: 10px;
    font-size: 11px;
    font-weight: 600;
}

QPushButton#searchButton:hover {
    border-color: #2699b5;
    background: palette(alternate-base);
}

QScrollArea {
    border: none;
    background: transparent;
}

QScrollBar:vertical {
    background: transparent;
    width: 7px;
    margin: 2px;
}

QScrollBar::handle:vertical {
    background: palette(mid);
    border-radius: 3px;
    min-height: 30px;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {
    background: transparent;
}
"""


class VideoCard(QFrame):
    """Clickable YouTube video card."""

    clicked = Signal(str)

    def __init__(self, video: Video, parent=None):
        super().__init__(parent)

        self.url = video.url

        self.setObjectName("videoCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        self.thumbnail = QLabel("Loading...")
        self.thumbnail.setFixedSize(120, 76)
        self.thumbnail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail.setWordWrap(True)
        self.thumbnail.setStyleSheet("""
            background: #252525;
            color: white;
            border-radius: 5px;
            font-size: 10px;
        """)

        layout.addWidget(self.thumbnail)

        details = QVBoxLayout()
        details.setSpacing(5)

        self.video_title = QLabel(video.title)
        self.video_title.setObjectName("videoTitle")
        self.video_title.setWordWrap(True)
        self.video_title.setMaximumHeight(48)

        details.addWidget(self.video_title)

        self.channel = QLabel(video.channel.strip() or "YouTube")
        self.channel.setObjectName("channel")
        self.channel.setWordWrap(True)

        details.addWidget(self.channel)

        if video.curated:
            recommended = QLabel("RECOMMENDED")
            recommended.setObjectName("recommended")
            details.addWidget(recommended)

        details.addStretch()

        layout.addLayout(details, 1)

        for widget in (
            self.thumbnail,
            self.video_title,
            self.channel,
        ):
            widget.setAttribute(
                Qt.WidgetAttribute.WA_TransparentForMouseEvents
            )

    def set_thumbnail(self, pixmap: QPixmap):
        if pixmap.isNull():
            self.thumbnail.setText("Preview unavailable")
            return

        scaled = pixmap.scaled(
            self.thumbnail.size(),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )

        x = max(0, (scaled.width() - self.thumbnail.width()) // 2)
        y = max(0, (scaled.height() - self.thumbnail.height()) // 2)

        self.thumbnail.setPixmap(
            scaled.copy(
                x,
                y,
                self.thumbnail.width(),
                self.thumbnail.height(),
            )
        )

    def mouseReleaseEvent(self, event):
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self.rect().contains(event.position().toPoint())
        ):
            self.clicked.emit(self.url)

        super().mouseReleaseEvent(event)


class SidePanel(QWidget):

    speak_requested = Signal(str, list)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setObjectName("sidePanel")
        self.setMinimumWidth(300)
        self.setStyleSheet(STYLE)

        self._search_url = ""
        self._speech_title = ""
        self._speech_steps: list[str] = []

        self._network = QNetworkAccessManager(self)
        self._thumbnail_replies = {}

        # --------------------------------------------------
        # Main layout
        # --------------------------------------------------

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 16, 16)
        root.setSpacing(14)

        # --------------------------------------------------
        # Header
        # --------------------------------------------------

        eyebrow = QLabel("FIELDGUIDE  /  OBJECT DETAILS")
        eyebrow.setObjectName("eyebrow")

        root.addWidget(eyebrow)

        header = QHBoxLayout()
        header.setSpacing(8)

        self.title = QLabel("FieldGuide")
        self.title.setObjectName("objectTitle")
        self.title.setWordWrap(True)

        self.confidence = QLabel()
        self.confidence.setObjectName("confidence")
        self.confidence.hide()

        header.addWidget(self.title, 1)
        header.addWidget(
            self.confidence,
            0,
            Qt.AlignmentFlag.AlignTop,
        )

        root.addLayout(header)

        # --------------------------------------------------
        # Scrollable content
        # --------------------------------------------------

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)

        self.scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        self.content = QWidget()

        self.content.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 5, 0)
        self.content_layout.setSpacing(14)

        # --------------------------------------------------
        # Object description and instructions
        # --------------------------------------------------

        self.body = QLabel()
        self.body.setObjectName("body")
        self.body.setWordWrap(True)
        self.body.setTextFormat(Qt.TextFormat.RichText)
        self.body.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.body.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        self.content_layout.addWidget(self.body)

        # --------------------------------------------------
        # Speech button
        # --------------------------------------------------

        self.speak_button = QPushButton("  Listen to instructions")

        self.speak_button.setObjectName("speakButton")

        self.speak_button.setIcon(
            self.style().standardIcon(
                QStyle.StandardPixmap.SP_MediaPlay
            )
        )

        self.speak_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        self.speak_button.setFixedHeight(40)

        self.speak_button.setEnabled(False)
        self.speak_button.hide()

        self.speak_button.clicked.connect(self._request_speech)

        # IMPORTANT: Actually add the button to the layout.
        self.content_layout.addWidget(self.speak_button)

        # --------------------------------------------------
        # Tutorial separator
        # --------------------------------------------------

        self.separator = self._separator()

        self.content_layout.addWidget(self.separator)

        # --------------------------------------------------
        # Tutorial section
        # --------------------------------------------------

        self.tutorial_section = QWidget()

        self.tutorial_layout = QVBoxLayout(self.tutorial_section)
        self.tutorial_layout.setContentsMargins(0, 0, 0, 0)
        self.tutorial_layout.setSpacing(9)

        tutorial_header = QHBoxLayout()

        self.videos_title = QLabel("VIDEO TUTORIALS")
        self.videos_title.setObjectName("eyebrow")

        tutorial_header.addWidget(self.videos_title)
        tutorial_header.addStretch()

        self.video_count = QLabel()
        self.video_count.setObjectName("channel")

        tutorial_header.addWidget(self.video_count)

        self.tutorial_layout.addLayout(tutorial_header)

        self.videos = QWidget()

        self.videos_layout = QVBoxLayout(self.videos)
        self.videos_layout.setContentsMargins(0, 0, 0, 0)
        self.videos_layout.setSpacing(8)

        self.tutorial_layout.addWidget(self.videos)

        self.note = QLabel()
        self.note.setObjectName("channel")
        self.note.setWordWrap(True)

        self.tutorial_layout.addWidget(self.note)

        self.content_layout.addWidget(self.tutorial_section)
        self.content_layout.addStretch()

        self.scroll.setWidget(self.content)

        root.addWidget(self.scroll, 1)

        # --------------------------------------------------
        # Footer
        # --------------------------------------------------

        self.search_btn = QPushButton(
            "Search more on YouTube  ↗"
        )

        self.search_btn.setObjectName("searchButton")

        self.search_btn.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        self.search_btn.clicked.connect(self._open_search)

        root.addWidget(self.search_btn)

        self.show_idle()

    # ------------------------------------------------------
    # Speech controls
    # ------------------------------------------------------

    def _request_speech(self):
        """Request playback or stop through MainWindow."""

        if not self._speech_steps:
            return

        self.speak_requested.emit(
            self._speech_title,
            self._speech_steps,
        )

    def set_speech_state(self, speaking: bool):
        """Synchronize the button with playback state."""

        self.speak_button.setEnabled(not speaking)

        if speaking:
            self.speak_button.setText("  Reading instructions...")
        else:
            self.speak_button.setText("  Listen to instructions")

        icon = (
            QStyle.StandardPixmap.SP_MediaPlay
        )

        self.speak_button.setIcon(
            self.style().standardIcon(icon)
        )

    def _reset_speech(self):
        self._speech_title = ""
        self._speech_steps = []

        self.speak_button.hide()
        self.speak_button.setEnabled(False)

        self.set_speech_state(False)

    # ------------------------------------------------------
    # Helpers
    # ------------------------------------------------------

    @staticmethod
    def _separator():
        line = QFrame()

        line.setObjectName("separator")
        line.setFrameShape(QFrame.Shape.HLine)

        return line

    def _clear_video_cards(self):

        replies = list(self._thumbnail_replies)

        self._thumbnail_replies.clear()

        for reply in replies:
            reply.abort()
            reply.deleteLater()

        while self.videos_layout.count():

            item = self.videos_layout.takeAt(0)
            widget = item.widget()

            if widget:
                widget.deleteLater()

    def _set_videos_visible(self, visible: bool):

        self.separator.setVisible(visible)
        self.tutorial_section.setVisible(visible)
        self.search_btn.setVisible(visible)

    # ------------------------------------------------------
    # Panel states
    # ------------------------------------------------------

    def show_idle(self):

        self._clear_video_cards()
        self._reset_speech()

        self.title.setText("FieldGuide")
        self.confidence.hide()

        self.body.setText(
            "<p>Welcome to FieldGuide.</p>"
            "<p>Point your camera at an object. "
            "When its detection box turns solid, click it "
            "to explore instructions and useful tutorials.</p>"
        )

        self.note.clear()
        self.video_count.clear()

        self._set_videos_visible(False)

    def show_message(self, title: str, text: str):

        self._clear_video_cards()
        self._reset_speech()

        self.title.setText(title)
        self.confidence.hide()

        self.body.setText(
            f"<p>{html.escape(text)}</p>"
        )

        self.note.clear()
        self.video_count.clear()

        self._set_videos_visible(False)

    def show_entry(self, entry: Entry, confidence: float):

        self._clear_video_cards()
        self._reset_speech()

        self.title.setText(entry.display_name)

        self.confidence.setText(
            f"{int(confidence * 100)}% confidence"
        )

        self.confidence.show()

        # Store the selected object's speech instructions.
        self._speech_title = entry.display_name
        self._speech_steps = list(entry.steps)

        if self._speech_steps:
            self.speak_button.setEnabled(True)
            self.speak_button.show()

        parts = []

        if entry.summary:
            parts.append(
                f"<p>{html.escape(entry.summary)}</p>"
            )

        if entry.steps:

            parts.append(
                '<p style="font-weight:700; margin-top:18px;">'
                "HOW TO USE IT</p>"
            )

            parts.append("<ol>")

            for step in entry.steps:
                parts.append(
                    f"<li style='margin-bottom:7px;'>"
                    f"{html.escape(step)}</li>"
                )

            parts.append("</ol>")

        if entry.cautions:

            parts.append(
                '<p style="font-weight:700; margin-top:18px;">'
                "CAUTION</p>"
            )

            parts.append(
                "<ul>"
                + "".join(
                    f"<li style='margin-bottom:6px;'>"
                    f"{html.escape(item)}</li>"
                    for item in entry.cautions
                )
                + "</ul>"
            )

        self.body.setText("".join(parts))

        self.note.setText("Finding useful tutorials...")
        self.video_count.clear()

        self._set_videos_visible(True)

    # ------------------------------------------------------
    # YouTube tutorials
    # ------------------------------------------------------

    def set_tutorials(self, result: TutorialResult):

        self._search_url = result.search_url

        self._clear_video_cards()

        count = len(result.videos)

        self.video_count.setText(
            f"{count} videos" if count else ""
        )

        for video in result.videos:

            card = VideoCard(video)

            self.videos_layout.addWidget(card)

            card.clicked.connect(self._open_video)

            self._load_thumbnail(video, card)

        if result.videos:

            self.note.setText(
                result.message
                or "Select a video to start watching."
            )

        else:

            self.note.setText(
                result.message or "No tutorials found."
            )

    # ------------------------------------------------------
    # Thumbnail loading
    # ------------------------------------------------------

    def _load_thumbnail(self, video: Video, card: VideoCard):

        url = (
            video.thumbnail
            or f"https://i.ytimg.com/vi/{video.video_id}/mqdefault.jpg"
        )

        if not url.startswith("https://"):

            card.set_thumbnail(QPixmap())
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

    # ------------------------------------------------------
    # Actions
    # ------------------------------------------------------

    @staticmethod
    def _open_video(url: str):

        if url:
            webbrowser.open(url)

    def _open_search(self):

        if self._search_url:
            webbrowser.open(self._search_url)
