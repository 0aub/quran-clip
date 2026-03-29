"""Tests for the concatenator module."""

from pathlib import Path
from unittest.mock import patch

import pytest

from quran_clip.concatenator import _write_concat_file


class TestWriteConcatFile:
    def test_no_silence(self, tmp_path):
        files = [tmp_path / "001.mp3", tmp_path / "002.mp3", tmp_path / "003.mp3"]
        for f in files:
            f.touch()

        concat_file = tmp_path / "concat.txt"
        _write_concat_file(concat_file, files, silence_path=None)

        content = concat_file.read_text()
        lines = [l for l in content.strip().split("\n") if l]
        assert len(lines) == 3
        assert all(l.startswith("file '") for l in lines)

    def test_with_silence(self, tmp_path):
        files = [tmp_path / "001.mp3", tmp_path / "002.mp3", tmp_path / "003.mp3"]
        silence = tmp_path / "silence.mp3"
        for f in files + [silence]:
            f.touch()

        concat_file = tmp_path / "concat.txt"
        _write_concat_file(concat_file, files, silence_path=silence)

        content = concat_file.read_text()
        lines = [l for l in content.strip().split("\n") if l]
        # 3 audio files + 2 silence gaps = 5 lines
        assert len(lines) == 5

    def test_single_file_no_trailing_silence(self, tmp_path):
        files = [tmp_path / "001.mp3"]
        silence = tmp_path / "silence.mp3"
        for f in files + [silence]:
            f.touch()

        concat_file = tmp_path / "concat.txt"
        _write_concat_file(concat_file, files, silence_path=silence)

        content = concat_file.read_text()
        lines = [l for l in content.strip().split("\n") if l]
        assert len(lines) == 1  # No silence after single file
