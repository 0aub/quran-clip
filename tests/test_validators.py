"""Tests for input validation."""

import pytest
from quran_clip.validators import ValidationError, validate_surah, validate_ayah_range, validate_format


class TestValidateSurah:
    def test_valid_range(self):
        for n in (1, 57, 114):
            validate_surah(n)  # should not raise

    def test_zero(self):
        with pytest.raises(ValidationError, match="between 1 and 114"):
            validate_surah(0)

    def test_negative(self):
        with pytest.raises(ValidationError, match="between 1 and 114"):
            validate_surah(-1)

    def test_too_high(self):
        with pytest.raises(ValidationError, match="between 1 and 114"):
            validate_surah(115)


class TestValidateAyahRange:
    def test_valid_range(self, surah_registry):
        validate_ayah_range(1, 1, 7, surah_registry)

    def test_from_exceeds_count(self, surah_registry):
        with pytest.raises(ValidationError, match="has only 7 ayahs"):
            validate_ayah_range(1, 8, 8, surah_registry)

    def test_to_exceeds_count(self, surah_registry):
        with pytest.raises(ValidationError, match="has only 7 ayahs"):
            validate_ayah_range(1, 1, 10, surah_registry)

    def test_from_greater_than_to(self, surah_registry):
        with pytest.raises(ValidationError, match="must be <="):
            validate_ayah_range(23, 10, 5, surah_registry)

    def test_negative_ayah(self, surah_registry):
        with pytest.raises(ValidationError, match=">= 1"):
            validate_ayah_range(2, -1, 5, surah_registry)

    def test_full_surah_range(self, surah_registry):
        # Baqarah: 286 ayahs
        validate_ayah_range(2, 1, 286, surah_registry)


class TestValidateFormat:
    def test_valid_formats(self):
        for fmt in ("mp3", "opus", "ogg", "wav"):
            validate_format(fmt)

    def test_invalid_format(self):
        with pytest.raises(ValidationError, match="Unsupported format 'flac'"):
            validate_format("flac")
