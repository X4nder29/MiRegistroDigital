"""Modelos de datos para la sección de Visualización (emparejar Registros con Antecedentes)."""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class Category(str, Enum):
    DEFUNCION = "Defuncion"
    NACIMIENTO = "Nacimiento"
    MATRIMONIO = "Matrimonio"


class Subcategory(str, Enum):
    ANTECEDENTES = "Antecedentes"
    REGISTROS = "Registros"


@dataclass(frozen=True)
class PdfEntry:
    """Un PDF encontrado en disco bajo una categoria/subcategoria."""
    serial: str
    path: Path
    box: str
    folder: str
    category: Category
    subcategory: Subcategory


@dataclass
class MatchPair:
    """Un serial dentro de una categoria: su Registro, su Antecedente, o ambos."""
    category: Category
    serial: str
    registro: PdfEntry | None = None
    antecedente: PdfEntry | None = None
    cancelado: bool = False

    @property
    def is_matched(self) -> bool:
        return self.registro is not None and self.antecedente is not None

    @property
    def is_orphan_registro(self) -> bool:
        return self.registro is not None and self.antecedente is None

    @property
    def is_orphan_antecedente(self) -> bool:
        return self.antecedente is not None and self.registro is None

    @property
    def status(self) -> str:
        if self.cancelado:
            return "cancelado"
        if self.is_matched:
            return "matched"
        if self.registro is not None:
            return "orphan_registro"
        return "orphan_antecedente"


@dataclass
class DuplicateEntry:
    """Anomalia: el mismo serial aparece mas de una vez en una categoria+subcategoria."""
    category: Category
    subcategory: Subcategory
    serial: str
    paths: list[Path] = field(default_factory=list)


@dataclass
class CategoryBatch:
    """Resultado incremental de una categoria, emitido apenas termina de escanearse."""
    category: Category
    pairs: list[MatchPair]
    duplicates: list[DuplicateEntry]
    skipped_non_numeric: list[Path]


@dataclass
class ScanResult:
    """Resultado completo de un escaneo de directorio, agrupado por categoria."""
    root: Path
    pairs: dict[Category, list[MatchPair]] = field(default_factory=dict)
    duplicates: list[DuplicateEntry] = field(default_factory=list)
    skipped_non_numeric: list[Path] = field(default_factory=list)
    scanned_categories: list[Category] = field(default_factory=list)

    def pairs_flat(self) -> list[MatchPair]:
        return [p for lst in self.pairs.values() for p in lst]

    def counts(self, category: Category | None = None) -> dict[str, int]:
        pairs = self.pairs.get(category, []) if category else self.pairs_flat()
        return {
            "total_registros": sum(1 for p in pairs if p.registro),
            "total_antecedentes": sum(1 for p in pairs if p.antecedente),
            "matched": sum(1 for p in pairs if p.is_matched),
            "orphan_registro": sum(1 for p in pairs if p.is_orphan_registro),
            "orphan_antecedente": sum(1 for p in pairs if p.is_orphan_antecedente),
            "cancelado": sum(1 for p in pairs if p.status == "cancelado"),
        }
