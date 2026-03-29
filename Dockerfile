FROM python:3.12-slim AS base

# Install ffmpeg (static binary, no bloat)
COPY --from=mwader/static-ffmpeg:7.1 /ffmpeg /usr/local/bin/
COPY --from=mwader/static-ffmpeg:7.1 /ffprobe /usr/local/bin/

WORKDIR /app

COPY pyproject.toml .
COPY quran_clip/ quran_clip/
COPY data/ data/
COPY tests/ tests/

RUN pip install --no-cache-dir ".[dev]"

# Output directory as a volume
VOLUME /app/output

ENTRYPOINT ["quran-clip"]
