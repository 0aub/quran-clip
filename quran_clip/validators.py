"""Input validation — all checks happen before any network call."""

from __future__ import annotations

from .config import SUPPORTED_FORMATS
from .metadata import SurahRegistry


class ValidationError(Exception):
    pass


def validate_surah(surah_number: int) -> None:
    if surah_number < 1 or surah_number > 114:
        raise ValidationError("Surah number must be between 1 and 114")


def validate_ayah_range(
    surah_number: int,
    from_ayah: int,
    to_ayah: int,
    registry: SurahRegistry,
) -> None:
    surah = registry.get(surah_number)

    if from_ayah < 1:
        raise ValidationError("Ayah number must be >= 1")

    if from_ayah > surah.ayah_count:
        raise ValidationError(
            f"Surah {surah.name_en} has only {surah.ayah_count} ayahs"
        )

    if to_ayah > surah.ayah_count:
        raise ValidationError(
            f"Surah {surah.name_en} has only {surah.ayah_count} ayahs"
        )

    if from_ayah > to_ayah:
        raise ValidationError(
            f"from-ayah ({from_ayah}) must be <= to-ayah ({to_ayah})"
        )


def validate_format(fmt: str) -> None:
    if fmt not in SUPPORTED_FORMATS:
        raise ValidationError(
            f"Unsupported format '{fmt}'. Supported: {', '.join(SUPPORTED_FORMATS)}"
        )
