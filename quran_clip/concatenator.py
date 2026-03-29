"""ffmpeg concat demuxer wrapper for merging ayah audio files."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from rich.console import Console

console = Console()


class ConcatError(Exception):
    pass


def concatenate(
    audio_files: list[Path],
    output_path: Path,
    surah_name: str,
    surah_number: int,
    from_ayah: int,
    to_ayah: int,
    reciter_name: str,
    gap: float = 0.5,
    quiet: bool = False,
) -> Path:
    """Merge ayah audio files into a single output file using ffmpeg concat demuxer."""
    if len(audio_files) == 1:
        # Single file — just copy, add metadata
        _copy_with_metadata(
            audio_files[0], output_path,
            surah_name, surah_number, from_ayah, to_ayah, reciter_name,
            quiet,
        )
        return output_path

    # Generate silence file if gap > 0
    silence_path = None
    if gap > 0:
        silence_path = audio_files[0].parent / "_silence.mp3"
        _generate_silence(silence_path, gap)

    # Build concat file list
    concat_file = audio_files[0].parent / "_concat.txt"
    _write_concat_file(concat_file, audio_files, silence_path)

    # Run ffmpeg
    title = f"Surah {surah_name} ({surah_number}:{from_ayah}-{to_ayah})"
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_file),
        "-c", "copy",
        "-metadata", f"title={title}",
        "-metadata", f"artist={reciter_name}",
        "-metadata", "album=Quran Recitation",
        "-metadata", f"track={surah_number}",
        str(output_path),
    ]

    if not quiet:
        console.print("  [dim]Merging audio files...[/dim]")

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise ConcatError(f"ffmpeg failed:\n{result.stderr}")

    return output_path


def _copy_with_metadata(
    src: Path,
    dst: Path,
    surah_name: str,
    surah_number: int,
    from_ayah: int,
    to_ayah: int,
    reciter_name: str,
    quiet: bool,
) -> None:
    """Copy single file with metadata tags."""
    title = f"Surah {surah_name} ({surah_number}:{from_ayah}-{to_ayah})"
    cmd = [
        "ffmpeg", "-y",
        "-i", str(src),
        "-c", "copy",
        "-metadata", f"title={title}",
        "-metadata", f"artist={reciter_name}",
        "-metadata", "album=Quran Recitation",
        "-metadata", f"track={surah_number}",
        str(dst),
    ]

    if not quiet:
        console.print("  [dim]Writing output file...[/dim]")

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise ConcatError(f"ffmpeg failed:\n{result.stderr}")


def _generate_silence(path: Path, duration: float) -> None:
    """Generate a silent MP3 file of the given duration."""
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"anullsrc=r=44100:cl=mono",
        "-t", str(duration),
        "-c:a", "libmp3lame",
        "-b:a", "128k",
        str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise ConcatError(f"Failed to generate silence: {result.stderr}")


def _write_concat_file(
    path: Path,
    audio_files: list[Path],
    silence_path: Path | None,
) -> None:
    """Write ffmpeg concat demuxer file list."""
    lines = []
    for i, f in enumerate(audio_files):
        lines.append(f"file '{f}'")
        # Add silence between files (not after last)
        if silence_path and i < len(audio_files) - 1:
            lines.append(f"file '{silence_path}'")

    path.write_text("\n".join(lines) + "\n")


def get_duration(path: Path) -> float:
    """Get audio duration in seconds using ffprobe."""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return 0.0
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0.0
