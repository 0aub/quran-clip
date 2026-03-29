"""Tests for surah and reciter metadata registry."""

from quran_clip.metadata import SurahRegistry, ReciterRegistry


class TestSurahRegistry:
    def test_loads_114_surahs(self, surah_registry):
        assert len(surah_registry.all()) == 114

    def test_get_fatiha(self, surah_registry):
        s = surah_registry.get(1)
        assert s.name_en == "Al-Fatiha"
        assert s.ayah_count == 7

    def test_get_baqarah(self, surah_registry):
        s = surah_registry.get(2)
        assert s.name_en == "Al-Baqarah"
        assert s.ayah_count == 286

    def test_get_nas(self, surah_registry):
        s = surah_registry.get(114)
        assert s.name_en == "An-Nas"
        assert s.ayah_count == 6

    def test_slug_generation(self, surah_registry):
        s = surah_registry.get(23)
        assert s.slug == "al-muminun"

    def test_absolute_ayah_fatiha(self, surah_registry):
        # First ayah of Quran
        assert surah_registry.to_absolute(1, 1) == 1
        assert surah_registry.to_absolute(1, 7) == 7

    def test_absolute_ayah_baqarah(self, surah_registry):
        # Surah 2 starts after 7 ayahs of Fatiha
        assert surah_registry.to_absolute(2, 1) == 8
        assert surah_registry.to_absolute(2, 286) == 293

    def test_absolute_ayah_al_muminun(self, surah_registry):
        # Surah 23, ayah 1
        abs_ayah = surah_registry.to_absolute(23, 1)
        assert abs_ayah > 0

    def test_total_ayahs_is_6236(self, surah_registry):
        """Verify total ayah count matches known Quran total."""
        total = sum(s.ayah_count for s in surah_registry.all())
        assert total == 6236


class TestReciterRegistry:
    def test_loads_reciters(self, reciter_registry):
        assert len(reciter_registry.all()) > 0

    def test_get_alafasy(self, reciter_registry):
        r = reciter_registry.get("ar.alafasy")
        assert r is not None
        assert r.name_en == "Mishary Rashid Al-Afasy"

    def test_get_unknown_returns_none(self, reciter_registry):
        assert reciter_registry.get("nonexistent") is None

    def test_all_have_everyayah_folder(self, reciter_registry):
        for r in reciter_registry.all():
            assert r.everyayah_folder, f"{r.id} missing everyayah_folder"
