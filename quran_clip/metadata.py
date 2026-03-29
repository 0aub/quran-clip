"""Surah and reciter metadata registry with caching."""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources

from .config import SURAHS_FILE, RECITERS_FILE


@dataclass(frozen=True)
class Surah:
    number: int
    name_en: str
    name_ar: str
    ayah_count: int
    revelation: str

    @property
    def slug(self) -> str:
        """URL-safe lowercase name for filenames, e.g. 'al-muminun'."""
        return self.name_en.lower().replace("'", "").replace(" ", "-")


@dataclass(frozen=True)
class Reciter:
    id: str
    name_en: str
    name_ar: str
    style: str
    everyayah_folder: str
    bitrates: tuple[int, ...]


def _read_json(resource):
    """Read a JSON resource file from the package."""
    return json.loads(resource.read_text(encoding="utf-8"))


class SurahRegistry:
    """Loads and indexes all 114 surahs from surahs.json."""

    def __init__(self, resource=SURAHS_FILE) -> None:
        self._by_number: dict[int, Surah] = {}
        self._cumulative: dict[int, int] = {}
        self._load(resource)

    def _load(self, resource) -> None:
        data = _read_json(resource)

        running_total = 0
        for entry in data:
            surah = Surah(
                number=entry["number"],
                name_en=entry["name_en"],
                name_ar=entry["name_ar"],
                ayah_count=entry["ayah_count"],
                revelation=entry["revelation"],
            )
            self._by_number[surah.number] = surah
            self._cumulative[surah.number] = running_total
            running_total += surah.ayah_count

    def get(self, number: int) -> Surah:
        return self._by_number[number]

    def exists(self, number: int) -> bool:
        return number in self._by_number

    def all(self) -> list[Surah]:
        return list(self._by_number.values())

    def to_absolute(self, surah: int, ayah: int) -> int:
        """Convert (surah, ayah) to absolute ayah number (1-6236)."""
        return self._cumulative[surah] + ayah


class ReciterRegistry:
    """Loads and indexes reciters from reciters.json."""

    def __init__(self, resource=RECITERS_FILE) -> None:
        self._by_id: dict[str, Reciter] = {}
        self._load(resource)

    def _load(self, resource) -> None:
        data = _read_json(resource)

        for entry in data:
            reciter = Reciter(
                id=entry["id"],
                name_en=entry["name_en"],
                name_ar=entry["name_ar"],
                style=entry["style"],
                everyayah_folder=entry["everyayah_folder"],
                bitrates=tuple(entry["bitrates"]),
            )
            self._by_id[reciter.id] = reciter

    def get(self, reciter_id: str) -> Reciter | None:
        return self._by_id.get(reciter_id)

    def all(self) -> list[Reciter]:
        return list(self._by_id.values())

    def ids(self) -> list[str]:
        return list(self._by_id.keys())
