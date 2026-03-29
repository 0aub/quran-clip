"""Constants, API URLs, and default configuration."""

from importlib import resources
from pathlib import Path

# --- Data files (bundled inside the package) ---
_PKG = resources.files("quran_clip")
SURAHS_FILE = _PKG / "surahs.json"
RECITERS_FILE = _PKG / "reciters.json"

# --- Output directory (resolved at runtime) ---
DEFAULT_OUTPUT_DIR = Path.cwd() / "output"

# --- API URLs ---
# Primary CDN: alquran.cloud (uses absolute ayah numbers)
ALQURAN_CDN_URL = "https://cdn.islamic.network/quran/audio/{bitrate}/{edition}/{ayah}.mp3"

# Fallback CDN: everyayah.com (uses SSS/AAA format)
EVERYAYAH_URL = "https://everyayah.com/data/{folder}/{surah:03d}{ayah:03d}.mp3"

# Editions API (for refreshing reciter list)
EDITIONS_API_URL = "https://api.alquran.cloud/v1/edition?format=audio&language=ar"

# Basmala audio (ayah 1 of surah 1 from alquran.cloud, absolute ayah #1)
BASMALA_CDN_URL = "https://cdn.islamic.network/quran/audio/{bitrate}/{edition}/1.mp3"
BASMALA_EVERYAYAH_URL = "https://everyayah.com/data/{folder}/001001.mp3"

# --- Defaults ---
DEFAULT_RECITER = "alafasy"
DEFAULT_BITRATE = 128
DEFAULT_GAP = 0.5
DEFAULT_FORMAT = "mp3"
SUPPORTED_FORMATS = ("mp3", "opus", "ogg", "wav")

# --- Download settings ---
MAX_CONCURRENT_DOWNLOADS = 10
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2  # seconds

# --- Total ayahs in the Quran ---
TOTAL_AYAHS = 6236
