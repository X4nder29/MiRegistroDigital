from __future__ import annotations
import cv2
import numpy as np
from typing import Optional, Tuple


def detect_corners(image: np.ndarray) -> Optional[np.ndarray]:
    gray = _gray(image)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edged = cv2.Canny(blurred, 50, 150)
    edged = cv2.dilate(edged, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)), iterations=1)
    cnts, _ = cv2.findContours(edged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in sorted(cnts, key=cv2.contourArea, reverse=True)[:5]:
        approx = cv2.approxPolyDP(c, 0.02 * cv2.arcLength(c, True), True)
        if len(approx) == 4:
            return _order(approx.reshape(4, 2).astype(np.float32))
    return None


def correct_perspective(image: np.ndarray, corners: Optional[np.ndarray] = None) -> np.ndarray:
    pts = corners if corners is not None else detect_corners(image)
    if pts is None:
        return image
    tl, tr, br, bl = pts
    W = int(max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl)))
    H = int(max(np.linalg.norm(bl - tl), np.linalg.norm(br - tr)))
    dst = np.array([[0, 0], [W - 1, 0], [W - 1, H - 1], [0, H - 1]], dtype=np.float32)
    return cv2.warpPerspective(image, cv2.getPerspectiveTransform(pts, dst), (W, H))


def deskew(image: np.ndarray, angle: Optional[float] = None) -> Tuple[np.ndarray, float]:
    if angle is None:
        gray = _gray(image)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        coords = np.column_stack(np.where(thresh > 0))
        if len(coords) < 10:
            return image, 0.0
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = 90 + angle
    if abs(angle) < 0.3:
        return image, 0.0
    h, w = image.shape[:2]
    M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
    cos, sin = abs(M[0, 0]), abs(M[0, 1])
    nw, nh = int(h * sin + w * cos), int(h * cos + w * sin)
    M[0, 2] += (nw - w) / 2
    M[1, 2] += (nh - h) / 2
    return cv2.warpAffine(image, M, (nw, nh), flags=cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_REPLICATE), float(angle)


def crop_right_margin(image: np.ndarray, pct: float = 0.15) -> np.ndarray:
    h, w = image.shape[:2]
    crop = image[:, int(w * (1 - pct)):]
    return cv2.rotate(crop, cv2.ROTATE_90_COUNTERCLOCKWISE)


def crop_to_area(image: np.ndarray, area: tuple[float, float, float, float]) -> np.ndarray:
    h, w = image.shape[:2]
    x1, y1, x2, y2 = area
    l = int(x1 * w); t = int(y1 * h); r = int(x2 * w); b = int(y2 * h)
    l = max(0, min(l, w - 1))
    r = max(l + 1, min(r, w))
    t = max(0, min(t, h - 1))
    b = max(t + 1, min(b, h))
    return image[t:b, l:r]


def enhance_for_ocr(image: np.ndarray) -> np.ndarray:
    gray = _gray(image)
    h, w = gray.shape
    if min(h, w) < 500:
        scale = max(2.0, 500 / min(h, w))
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    denoised = cv2.bilateralFilter(enhanced, 7, 50, 50)
    _, binary = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    return cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)


def ndarray_to_qpixmap(image: np.ndarray, max_size: Optional[Tuple[int, int]] = None):
    """Convierte ndarray BGR a QPixmap, redimensionando si se indica max_size."""
    from PySide6.QtGui import QImage, QPixmap
    if max_size:
        h, w = image.shape[:2]
        mw, mh = max_size
        scale = min(mw / w, mh / h, 1.0)
        if scale < 1.0:
            image = cv2.resize(image, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    h, w = image.shape[:2]
    if image.ndim == 2:
        qimg = QImage(image.data, w, h, w, QImage.Format_Grayscale8)
    else:
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        qimg = QImage(rgb.data, w, h, w * 3, QImage.Format_RGB888)
    return QPixmap.fromImage(qimg)


def overlay_comment(image: np.ndarray, text: str) -> np.ndarray:
    """Overlay comment text at the bottom of the image. Returns a copy."""
    if not text.strip():
        return image.copy()
    out = image.copy()
    h, w = out.shape[:2]
    lines = text.strip().split("\n")
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = max(0.5, min(1.0, w / 1200))
    thickness = max(1, int(font_scale * 1.5))
    line_h = cv2.getTextSize("Ag", font, font_scale, thickness)[0][1] + 8
    bar_h = len(lines) * line_h + 16
    bar_h = min(bar_h, h // 3)
    overlay = out.copy()
    cv2.rectangle(overlay, (0, h - bar_h), (w, h), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.6, out, 0.4, 0, out)
    for i, line in enumerate(lines):
        tw = cv2.getTextSize(line, font, font_scale, thickness)[0][0]
        x = (w - tw) // 2
        y = h - bar_h + 16 + i * line_h + line_h - 4
        cv2.putText(out, line, (x, y), font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)
    return out


def _gray(img: np.ndarray) -> np.ndarray:
    if img.ndim == 2:
        return img
    if img.shape[2] == 4:
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def _order(pts: np.ndarray) -> np.ndarray:
    rect = np.zeros((4, 2), dtype=np.float32)
    s = pts.sum(1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    d = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(d)]
    rect[3] = pts[np.argmax(d)]
    return rect
