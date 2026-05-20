"""
OCRModel — Resultado de una operación OCR sobre una página.
"""
import re
from dataclasses import dataclass, field
from typing import Optional


SERIAL_PATTERN = re.compile(r"\b\d{8}\b")
DATE_PATTERN = re.compile(
    r"\b(\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{4}[-/]\d{1,2}[-/]\d{1,2})\b"
)


@dataclass
class OCRResult:
    """Resultado de OCR para una sola región de imagen."""
    raw_text: str = ""
    serial: Optional[str] = None
    date: Optional[str] = None
    confidence: float = 0.0
    all_candidates: list[str] = field(default_factory=list)

    @classmethod
    def from_easyocr(cls, results: list) -> "OCRResult":
        """
        Construye un OCRResult desde la salida de EasyOCR.
        results: lista de (bbox, text, confidence)
        """
        texts = []
        confidences = []
        for _, text, conf in results:
            texts.append(text.strip())
            confidences.append(conf)

        raw = " ".join(texts)
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0

        serial = cls._extract_serial(raw)
        date = cls._extract_date(raw)
        candidates = SERIAL_PATTERN.findall(raw)

        return cls(
            raw_text=raw,
            serial=serial,
            date=date,
            confidence=avg_conf,
            all_candidates=candidates,
        )

    @staticmethod
    def _extract_serial(text: str) -> Optional[str]:
        match = SERIAL_PATTERN.search(text)
        return match.group() if match else None

    @staticmethod
    def _extract_date(text: str) -> Optional[str]:
        match = DATE_PATTERN.search(text)
        return match.group() if match else None

    @property
    def is_valid(self) -> bool:
        return self.serial is not None

    def __str__(self) -> str:
        return (
            f"Serial: {self.serial or 'N/A'} | "
            f"Fecha: {self.date or 'N/A'} | "
            f"Confianza: {self.confidence:.2%}"
        )


class OCRModel:
    """Almacena los resultados OCR de todas las páginas procesadas."""

    def __init__(self):
        self._results: dict[int, OCRResult] = {}

    def set_result(self, page_index: int, result: OCRResult) -> None:
        self._results[page_index] = result

    def get_result(self, page_index: int) -> Optional[OCRResult]:
        return self._results.get(page_index)

    def clear(self) -> None:
        self._results.clear()

    def get_all(self) -> dict[int, OCRResult]:
        return dict(self._results)

    def serials_found(self) -> int:
        return sum(1 for r in self._results.values() if r.is_valid)

    def total_processed(self) -> int:
        return len(self._results)
