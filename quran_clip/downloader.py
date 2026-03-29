"""Async per-ayah audio downloader with dual-source fallback and retry."""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
from rich.progress import (
    Progress,
    SpinnerColumn,
    BarColumn,
    TextColumn,
    MofNCompleteColumn,
    TimeRemainingColumn,
)
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .config import (
    ALQURAN_CDN_URL,
    EVERYAYAH_URL,
    BASMALA_CDN_URL,
    BASMALA_EVERYAYAH_URL,
    MAX_CONCURRENT_DOWNLOADS,
    MAX_RETRIES,
    RETRY_BACKOFF_BASE,
)
from .metadata import Reciter, SurahRegistry


class DownloadError(Exception):
    pass


async def download_ayahs(
    surah_number: int,
    from_ayah: int,
    to_ayah: int,
    reciter: Reciter,
    surah_registry: SurahRegistry,
    temp_dir: Path,
    bitrate: int = 128,
    include_basmala: bool = False,
    quiet: bool = False,
) -> list[Path]:
    """Download all ayah audio files and return ordered list of paths."""
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)
    files: dict[int, Path] = {}
    tasks = []

    # Determine effective bitrate (use closest available)
    effective_bitrate = _closest_bitrate(bitrate, reciter.bitrates)

    ayah_range = list(range(from_ayah, to_ayah + 1))

    # Prepare basmala download if needed
    need_basmala = (
        include_basmala
        and surah_number != 1  # Fatiha: ayah 1 IS basmala
        and surah_number != 9  # Tawbah: never has basmala
        and from_ayah == 1     # Only prepend at start
    )

    total = len(ayah_range) + (1 if need_basmala else 0)

    progress = Progress(
        SpinnerColumn(style="green"),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(bar_width=40, style="cyan", complete_style="green"),
        MofNCompleteColumn(),
        TimeRemainingColumn(),
        disable=quiet,
    )

    with progress:
        task_id = progress.add_task("Downloading ayahs", total=total)

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            if need_basmala:
                tasks.append(
                    _download_basmala(
                        client, semaphore, reciter, effective_bitrate,
                        temp_dir, progress, task_id,
                    )
                )

            for ayah_num in ayah_range:
                tasks.append(
                    _download_single_ayah(
                        client, semaphore, surah_number, ayah_num,
                        reciter, surah_registry, effective_bitrate,
                        temp_dir, progress, task_id,
                    )
                )

            results = await asyncio.gather(*tasks, return_exceptions=True)

    # Process results
    ordered_files: list[Path] = []

    idx = 0
    if need_basmala:
        result = results[0]
        if isinstance(result, Exception):
            raise DownloadError(f"Failed to download Basmala: {result}")
        ordered_files.append(result)
        idx = 1

    for i, ayah_num in enumerate(ayah_range):
        result = results[idx + i]
        if isinstance(result, Exception):
            raise DownloadError(
                f"Failed to download ayah {ayah_num}: {result}"
            )
        ordered_files.append(result)

    return ordered_files


async def _download_basmala(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    reciter: Reciter,
    bitrate: int,
    temp_dir: Path,
    progress: Progress,
    task_id,
) -> Path:
    """Download Bismillah audio (ayah 1 of surah 1)."""
    primary_url = BASMALA_CDN_URL.format(bitrate=bitrate, edition=reciter.id)
    fallback_url = BASMALA_EVERYAYAH_URL.format(folder=reciter.everyayah_folder)
    out_path = temp_dir / "000_basmala.mp3"

    await _fetch_with_fallback(client, semaphore, primary_url, fallback_url, out_path)
    progress.advance(task_id)
    return out_path


async def _download_single_ayah(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    surah_number: int,
    ayah_number: int,
    reciter: Reciter,
    surah_registry: SurahRegistry,
    bitrate: int,
    temp_dir: Path,
    progress: Progress,
    task_id,
) -> Path:
    """Download a single ayah audio file with primary/fallback sources."""
    abs_ayah = surah_registry.to_absolute(surah_number, ayah_number)

    primary_url = ALQURAN_CDN_URL.format(
        bitrate=bitrate, edition=reciter.id, ayah=abs_ayah,
    )
    fallback_url = EVERYAYAH_URL.format(
        folder=reciter.everyayah_folder,
        surah=surah_number,
        ayah=ayah_number,
    )

    out_path = temp_dir / f"{ayah_number:03d}.mp3"
    await _fetch_with_fallback(client, semaphore, primary_url, fallback_url, out_path)
    progress.advance(task_id)
    return out_path


# HTTP status codes that trigger fallback to secondary source
_FALLBACK_CODES = {401, 403, 404, 410, 451}


@retry(
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential(multiplier=RETRY_BACKOFF_BASE, min=1, max=30),
    retry=retry_if_exception_type(httpx.TransportError),
    reraise=True,
)
async def _fetch_with_fallback(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    primary_url: str,
    fallback_url: str,
    out_path: Path,
) -> None:
    """Try primary URL, fall back to secondary on client errors (403, 404, etc.)."""
    async with semaphore:
        # Try primary
        try:
            resp = await client.get(primary_url)
            if resp.status_code in _FALLBACK_CODES:
                # Don't retry — go straight to fallback
                pass
            else:
                resp.raise_for_status()
                out_path.write_bytes(resp.content)
                return
        except httpx.HTTPStatusError:
            # Server error (5xx) — will be retried by tenacity
            raise
        except httpx.TransportError:
            raise

        # Fallback source
        resp = await client.get(fallback_url)
        resp.raise_for_status()
        out_path.write_bytes(resp.content)


async def check_reciter_availability(
    reciters: list[Reciter],
    surah_number: int,
    ayah_number: int,
    surah_registry: SurahRegistry,
) -> dict[str, bool]:
    """Probe one test ayah per reciter to check availability. Returns {reciter_id: available}."""
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)
    results: dict[str, bool] = {}

    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        tasks = []
        for reciter in reciters:
            tasks.append(_probe_reciter(client, semaphore, reciter, surah_number, ayah_number, surah_registry))

        probe_results = await asyncio.gather(*tasks)
        for reciter, available in zip(reciters, probe_results):
            results[reciter.id] = available

    return results


async def _probe_reciter(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    reciter: Reciter,
    surah_number: int,
    ayah_number: int,
    surah_registry: SurahRegistry,
) -> bool:
    """Check if a reciter has audio for a specific ayah (HEAD request)."""
    abs_ayah = surah_registry.to_absolute(surah_number, ayah_number)
    bitrate = reciter.bitrates[0] if reciter.bitrates else 128

    primary_url = ALQURAN_CDN_URL.format(bitrate=bitrate, edition=reciter.id, ayah=abs_ayah)
    fallback_url = EVERYAYAH_URL.format(
        folder=reciter.everyayah_folder, surah=surah_number, ayah=ayah_number,
    )

    async with semaphore:
        try:
            resp = await client.head(primary_url)
            if resp.status_code == 200:
                return True
        except httpx.TransportError:
            pass

        if reciter.everyayah_folder:
            try:
                resp = await client.head(fallback_url)
                if resp.status_code == 200:
                    return True
            except httpx.TransportError:
                pass

    return False


def _closest_bitrate(requested: int, available: tuple[int, ...]) -> int:
    """Pick the closest available bitrate."""
    return min(available, key=lambda b: abs(b - requested))
