from __future__ import annotations
import json
from pathlib import Path
from typing import Any

DEFAULTS: dict[str, Any] = {
    "correction":   {"auto_perspective": False, "auto_rotation": False},
    "ocr":          {"languages": ["es", "en"], "margin_right_pct": 0.15,
                     "confidence_threshold": 0.4, "gpu": False, "parallel_workers": 4},
    "output":       {"default_folder": str(Path.home() / "Documentos" / "DocScanPro"),
                     "pdf_dpi": 200},
    "antecedentes": {"serial_inicial": 1, "serial_padding": 5},
    "ui":           {"last_page": "import"},
}
CONFIG_PATH = Path.home() / ".docscanpro" / "config.json"


class ConfigModel:
    def __init__(self, path: Path = CONFIG_PATH):
        self._path = path
        self._data: dict = {}
        self.load()

    def load(self):
        if self._path.exists():
            try:
                saved = json.loads(self._path.read_text("utf-8"))
                self._data = self._merge(DEFAULTS, saved)
                return
            except Exception:
                pass
        self._data = self._merge({}, DEFAULTS)

    def save(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._data, indent=2, ensure_ascii=False), "utf-8")

    def get(self, section: str, key: str, default: Any = None) -> Any:
        return self._data.get(section, {}).get(key, default)

    def set(self, section: str, key: str, value: Any):
        self._data.setdefault(section, {})[key] = value

    def section(self, name: str) -> dict:
        return dict(self._data.get(name, {}))

    def reset(self):
        self._data = self._merge({}, DEFAULTS)
        self.save()

    @staticmethod
    def _merge(base: dict, override: dict) -> dict:
        r = dict(base)
        for k, v in override.items():
            r[k] = ConfigModel._merge(r[k], v) if (
                k in r and isinstance(r[k], dict) and isinstance(v, dict)
            ) else v
        return r
