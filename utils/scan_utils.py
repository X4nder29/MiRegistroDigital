"""Escaneo del arbol de directorios de Registros Civiles y emparejamiento por serial.

Estructura esperada:
    root/{categoria}/{subcategoria}/Caja N/Carpeta N/{serial}.pdf

Funciones puras, sin dependencias de Qt.
"""
from __future__ import annotations
import json
import re
import unicodedata
from pathlib import Path
from typing import Callable

from models.visualization_model import (
    Category, Subcategory, PdfEntry, MatchPair, DuplicateEntry, ScanResult, CategoryBatch,
)

_SERIAL_RE = re.compile(r"^\d+$")

_CATEGORY_ALIASES: dict[str, Category] = {
    "defuncion": Category.DEFUNCION,
    "nacimiento": Category.NACIMIENTO,
    "matrimonio": Category.MATRIMONIO,
}
_SUBCATEGORY_ALIASES: dict[str, Subcategory] = {
    "antecedentes": Subcategory.ANTECEDENTES,
    "registros": Subcategory.REGISTROS,
}

CACHE_PATH = Path.home() / ".miregistrodigital" / "visualization_cache.json"
ANNOTATIONS_PATH = Path.home() / ".miregistrodigital" / "visualization_annotations.json"


def normalize_name(name: str) -> str:
    """casefold + elimina acentos, solo para comparar nombres de carpetas."""
    decomposed = unicodedata.normalize("NFKD", name)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return stripped.strip().casefold()


def match_category(folder_name: str) -> Category | None:
    return _CATEGORY_ALIASES.get(normalize_name(folder_name))


def match_subcategory(folder_name: str) -> Subcategory | None:
    return _SUBCATEGORY_ALIASES.get(normalize_name(folder_name))


def scan_root(
    root: Path,
    on_category_done: Callable[[CategoryBatch], None] | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> ScanResult:
    """Escanea recursivamente root/{categoria}/{subcategoria}/Caja */Carpeta */*.pdf.

    Procesa una categoria completa a la vez y, si se provee on_category_done,
    invoca el callback con el resultado de esa categoria apenas termina -
    permite mostrar resultados incrementalmente sin esperar el escaneo completo.

    Funcion sincrona pura - segura para ejecutar dentro de un QRunnable.run().
    """
    result = ScanResult(root=root)
    if not root.exists() or not root.is_dir():
        return result

    for cat_dir in [d for d in root.iterdir() if d.is_dir()]:
        if should_stop and should_stop():
            return result
        category = match_category(cat_dir.name)
        if category is None:
            continue

        registros: dict[str, PdfEntry] = {}
        antecedentes: dict[str, PdfEntry] = {}
        buckets = {Subcategory.REGISTROS: registros, Subcategory.ANTECEDENTES: antecedentes}
        dup_tracker: dict[tuple[Subcategory, str], list[Path]] = {}
        cat_skipped: list[Path] = []

        for sub_dir in [d for d in cat_dir.iterdir() if d.is_dir()]:
            subcat = match_subcategory(sub_dir.name)
            if subcat is None:
                continue
            bucket = buckets[subcat]
            for box_dir in [d for d in sub_dir.iterdir() if d.is_dir()]:
                for folder_dir in [d for d in box_dir.iterdir() if d.is_dir()]:
                    for pdf_path in folder_dir.glob("*.pdf"):
                        if should_stop and should_stop():
                            return result
                        stem = pdf_path.stem.strip()
                        if not _SERIAL_RE.match(stem):
                            cat_skipped.append(pdf_path)
                            continue
                        if stem in bucket:
                            key = (subcat, stem)
                            if key not in dup_tracker:
                                dup_tracker[key] = [bucket[stem].path]
                            dup_tracker[key].append(pdf_path)
                            continue
                        bucket[stem] = PdfEntry(
                            serial=stem, path=pdf_path,
                            box=box_dir.name, folder=folder_dir.name,
                            category=category, subcategory=subcat,
                        )

        cat_duplicates = [
            DuplicateEntry(category=category, subcategory=subcat, serial=serial, paths=paths)
            for (subcat, serial), paths in dup_tracker.items()
        ]

        serials = sorted(set(registros) | set(antecedentes))
        pairs = [
            MatchPair(category=category, serial=s,
                      registro=registros.get(s), antecedente=antecedentes.get(s))
            for s in serials
        ]

        result.scanned_categories.append(category)
        result.pairs[category] = pairs
        result.duplicates.extend(cat_duplicates)
        result.skipped_non_numeric.extend(cat_skipped)

        if on_category_done:
            on_category_done(CategoryBatch(
                category=category, pairs=pairs,
                duplicates=cat_duplicates, skipped_non_numeric=cat_skipped,
            ))

    return result


def _entry_to_dict(e: PdfEntry | None) -> dict | None:
    if e is None:
        return None
    return {
        "serial": e.serial, "path": str(e.path), "box": e.box, "folder": e.folder,
        "category": e.category.value, "subcategory": e.subcategory.value,
    }


def _entry_from_dict(d: dict | None) -> PdfEntry | None:
    if d is None:
        return None
    return PdfEntry(
        serial=d["serial"], path=Path(d["path"]), box=d["box"], folder=d["folder"],
        category=Category(d["category"]), subcategory=Subcategory(d["subcategory"]),
    )


def save_cache(result: ScanResult, path: Path = CACHE_PATH) -> None:
    """Guarda el resultado de un escaneo completo en el folder de sistema de la app."""
    data = {
        "root": str(result.root),
        "pairs": {
            cat.value: [
                {
                    "serial": p.serial,
                    "registro": _entry_to_dict(p.registro),
                    "antecedente": _entry_to_dict(p.antecedente),
                }
                for p in pairs
            ]
            for cat, pairs in result.pairs.items()
        },
        "duplicates": [
            {
                "category": d.category.value, "subcategory": d.subcategory.value,
                "serial": d.serial, "paths": [str(p) for p in d.paths],
            }
            for d in result.duplicates
        ],
        "skipped_non_numeric": [str(p) for p in result.skipped_non_numeric],
        "scanned_categories": [c.value for c in result.scanned_categories],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def load_cache(path: Path = CACHE_PATH) -> ScanResult | None:
    """Carga el ultimo escaneo guardado en disco, o None si no existe o esta corrupto."""
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        result = ScanResult(root=Path(data["root"]))
        for cat_value, pairs_data in data.get("pairs", {}).items():
            category = Category(cat_value)
            result.pairs[category] = [
                MatchPair(
                    category=category, serial=pd["serial"],
                    registro=_entry_from_dict(pd.get("registro")),
                    antecedente=_entry_from_dict(pd.get("antecedente")),
                )
                for pd in pairs_data
            ]
        result.duplicates = [
            DuplicateEntry(
                category=Category(d["category"]), subcategory=Subcategory(d["subcategory"]),
                serial=d["serial"], paths=[Path(p) for p in d["paths"]],
            )
            for d in data.get("duplicates", [])
        ]
        result.skipped_non_numeric = [Path(p) for p in data.get("skipped_non_numeric", [])]
        result.scanned_categories = [Category(c) for c in data.get("scanned_categories", [])]
        return result
    except Exception:
        return None


def load_cancelled(path: Path = ANNOTATIONS_PATH) -> set[tuple[Category, str]]:
    """Carga el conjunto de (categoria, serial) marcados como anulados por el usuario."""
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {(Category(e["category"]), e["serial"]) for e in data.get("cancelled", [])}
    except Exception:
        return set()


def save_cancelled(cancelled: set[tuple[Category, str]], path: Path = ANNOTATIONS_PATH) -> None:
    """Guarda el conjunto de (categoria, serial) marcados como anulados."""
    data = {
        "cancelled": [
            {"category": category.value, "serial": serial}
            for category, serial in sorted(cancelled, key=lambda x: (x[0].value, x[1]))
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
