"""Live video with the detection overlay, drawn at the display rate (not the inference rate)."""
from __future__ import annotations

import zlib

import cv2
from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen
from PySide6.QtWidgets import QWidget

from ..geometry import box_to_view, fit_rect, hit_test, view_to_frame
from ..models import Track


def label_color(label: str) -> QColor:
    h = zlib.crc32(label.encode()) % 360
    return QColor.fromHsv(h, 200, 245)


class VideoWidget(QWidget):
    object_clicked = Signal(int)   # track id, or -1 for empty space

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumSize(480, 300)
        self._image: QImage | None = None
        self._size = (0, 0)
        self._tracks: list[Track] = []
        self._selected = -1
        self._message = "Camera is off. Press Start."

    # -- data in ---------------------------------------------------------
    def set_frame(self, bgr) -> None:
        h, w = bgr.shape[:2]
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        self._image = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888).copy()
        self._size = (w, h)

    def set_tracks(self, tracks: list[Track], selected: int = -1) -> None:
        self._tracks = tracks
        self._selected = selected

    def set_message(self, text: str) -> None:
        self._message = text

    def clear(self) -> None:
        self._image = None
        self._tracks = []
        self._selected = -1
        self.update()

    # -- painting --------------------------------------------------------
    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.fillRect(self.rect(), QColor(24, 24, 24))
        if self._image is None:
            p.setPen(QColor(200, 200, 200))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._message)
            return
        fw, fh = self._size
        s, ox, oy = fit_rect(fw, fh, self.width(), self.height())

        # Mirror the camera preview horizontally.
        image_rect = QRectF(ox, oy, fw * s, fh * s)

        p.save()
        p.translate(2 * ox + fw * s, 0)
        p.scale(-1, 1)
        p.drawImage(image_rect, self._image)
        p.restore()

        font = QFont(self.font())
        font.setPointSize(10)
        font.setBold(True)
        p.setFont(font)
        for t in self._tracks:
            x1, y1, x2, y2 = box_to_view(t.box, s, ox, oy)

            # Mirror bounding box to match the camera preview.
            mirror_axis = 2 * ox + fw * s

            x1, x2 = mirror_axis - x2, mirror_axis - x1
            
            col = label_color(t.label)
            selected = t.id == self._selected
            pen = QPen(col, 4 if selected else 2)
            if not t.stable:
                pen.setStyle(Qt.PenStyle.DashLine)
                col.setAlpha(150)
                pen.setColor(col)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(QRectF(x1, y1, x2 - x1, y2 - y1))
            text = f"{t.label} {int(t.confidence * 100)}%  #{t.id}"
            fm = p.fontMetrics()
            tw, th = fm.horizontalAdvance(text) + 8, fm.height() + 4
            ty = y1 - th if y1 - th > 0 else y1
            p.fillRect(QRectF(x1, ty, tw, th), QColor(0, 0, 0, 170))
            p.setPen(QColor(255, 255, 255) if t.stable else QColor(200, 200, 200))
            p.drawText(QRectF(x1 + 4, ty, tw, th), Qt.AlignmentFlag.AlignVCenter, text)

    # -- clicks ----------------------------------------------------------
    def mousePressEvent(self, event) -> None:
        if self._image is None:
            return
        s, ox, oy = fit_rect(self._size[0], self._size[1], self.width(), self.height())
        pos = event.position()
        fx, fy = view_to_frame(pos.x(), pos.y(), s, ox, oy)

        # Convert mirrored preview coordinates back to original frame coordinates.
        fx = self._size[0] - fx
        
        hit = hit_test(self._tracks, fx, fy)
        self.object_clicked.emit(hit.id if hit else -1)
