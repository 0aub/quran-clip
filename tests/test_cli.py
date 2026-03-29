"""Tests for CLI argument parsing and validation errors."""

from typer.testing import CliRunner

from quran_clip.cli import app

runner = CliRunner()


class TestDownloadValidation:
    def test_surah_zero(self):
        result = runner.invoke(app, ["download", "0"])
        assert result.exit_code != 0
        assert "between 1 and 114" in result.stdout

    def test_surah_115(self):
        result = runner.invoke(app, ["download", "115"])
        assert result.exit_code != 0
        assert "between 1 and 114" in result.stdout

    def test_from_exceeds_surah_length(self):
        result = runner.invoke(app, ["download", "1", "--from", "8"])
        assert result.exit_code != 0
        assert "has only 7 ayahs" in result.stdout

    def test_to_exceeds_surah_length(self):
        result = runner.invoke(app, ["download", "1", "--from", "1", "--to", "10"])
        assert result.exit_code != 0
        assert "has only 7 ayahs" in result.stdout

    def test_from_greater_than_to(self):
        result = runner.invoke(app, ["download", "23", "--from", "10", "--to", "5"])
        assert result.exit_code != 0
        assert "must be <=" in result.stdout

    def test_unsupported_format(self):
        result = runner.invoke(app, ["download", "23", "--format", "flac"])
        assert result.exit_code != 0
        assert "Unsupported format" in result.stdout

    def test_unknown_reciter(self):
        result = runner.invoke(app, ["download", "23", "--reciter", "xyznonexistent", "--quiet"])
        assert result.exit_code != 0
        assert "not found" in result.stdout


class TestListCommands:
    def test_list_surahs(self):
        result = runner.invoke(app, ["list-surahs"])
        assert result.exit_code == 0
        assert "Al-Fatiha" in result.stdout
        assert "Al-Baqarah" in result.stdout

    def test_list_surahs_search(self):
        result = runner.invoke(app, ["list-surahs", "--search", "fatiha"])
        assert result.exit_code == 0
        assert "Al-Fatiha" in result.stdout

    def test_list_reciters(self):
        result = runner.invoke(app, ["list-reciters"])
        assert result.exit_code == 0
        assert "Mishary" in result.stdout

    def test_info(self):
        result = runner.invoke(app, ["info", "23"])
        assert result.exit_code == 0
        assert "Al-Mu'minun" in result.stdout
        assert "118" in result.stdout
