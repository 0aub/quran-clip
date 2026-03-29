"""Tests for reciter name resolution."""

from quran_clip.resolver import _fuzzy_search
from quran_clip.metadata import ReciterRegistry


class TestFuzzySearch:
    def setup_method(self):
        self.registry = ReciterRegistry()

    def test_exact_id_partial(self):
        results = _fuzzy_search("alafasy", self.registry)
        assert any(r.id == "ar.alafasy" for r in results)

    def test_english_name(self):
        results = _fuzzy_search("mishary", self.registry)
        assert any(r.id == "ar.alafasy" for r in results)

    def test_arabic_name(self):
        results = _fuzzy_search("العفاسي", self.registry)
        assert any(r.id == "ar.alafasy" for r in results)

    def test_case_insensitive(self):
        results = _fuzzy_search("ALAFASY", self.registry)
        assert any(r.id == "ar.alafasy" for r in results)

    def test_no_match(self):
        results = _fuzzy_search("xyznonexistent", self.registry)
        assert len(results) == 0

    def test_ambiguous_returns_multiple(self):
        results = _fuzzy_search("abdul", self.registry)
        assert len(results) >= 2
