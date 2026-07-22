from __future__ import annotations
from dataclasses import dataclass, asdict, fields
from typing import Any


@dataclass
class ScanSettings:
    device_name: str = ""
    dpi: int = 300
    color_mode: str = "color"   # "color" | "grayscale" | "bw"
    duplex: bool = True
    source: str = "adf"         # "adf" | "flatbed"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ScanSettings:
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in names})
