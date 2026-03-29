"""Tests for the downloader module."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest
import respx

from quran_clip.downloader import _closest_bitrate, _fetch_with_fallback


class TestClosestBitrate:
    def test_exact_match(self):
        assert _closest_bitrate(128, (128, 64)) == 128

    def test_closest_higher(self):
        assert _closest_bitrate(100, (128, 64)) == 128

    def test_closest_lower(self):
        assert _closest_bitrate(80, (128, 64)) == 64

    def test_single_option(self):
        assert _closest_bitrate(256, (128,)) == 128


class TestFetchWithFallback:
    @respx.mock
    @pytest.mark.asyncio
    async def test_primary_success(self, tmp_path):
        primary = "https://cdn.example.com/audio/1.mp3"
        fallback = "https://fallback.example.com/audio/001001.mp3"
        out = tmp_path / "test.mp3"

        respx.get(primary).mock(return_value=httpx.Response(200, content=b"audio-data"))

        sem = asyncio.Semaphore(10)
        async with httpx.AsyncClient() as client:
            await _fetch_with_fallback(client, sem, primary, fallback, out)

        assert out.read_bytes() == b"audio-data"

    @respx.mock
    @pytest.mark.asyncio
    async def test_fallback_on_404(self, tmp_path):
        primary = "https://cdn.example.com/audio/1.mp3"
        fallback = "https://fallback.example.com/audio/001001.mp3"
        out = tmp_path / "test.mp3"

        respx.get(primary).mock(return_value=httpx.Response(404))
        respx.get(fallback).mock(return_value=httpx.Response(200, content=b"fallback-data"))

        sem = asyncio.Semaphore(10)
        async with httpx.AsyncClient() as client:
            await _fetch_with_fallback(client, sem, primary, fallback, out)

        assert out.read_bytes() == b"fallback-data"
