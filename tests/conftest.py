"""Shared test fixtures."""

import pytest
from quran_clip.metadata import SurahRegistry, ReciterRegistry


@pytest.fixture
def surah_registry():
    return SurahRegistry()


@pytest.fixture
def reciter_registry():
    return ReciterRegistry()
