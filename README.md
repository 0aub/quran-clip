```
██████╗ ██╗   ██╗██████╗  █████╗ ███╗   ██╗
██╔═══██╗██║   ██║██╔══██╗██╔══██╗████╗  ██║
██║   ██║██║   ██║██████╔╝███████║██╔██╗ ██║
██║▄▄ ██║██║   ██║██╔══██╗██╔══██║██║╚██╗██║
╚██████╔╝╚██████╔╝██║  ██║██║  ██║██║ ╚████║
 ╚══▀▀═╝  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝
            ██████╗██╗     ██╗██████╗
           ██╔════╝██║     ██║██╔══██╗
           ██║     ██║     ██║██████╔╝
           ██║     ██║     ██║██╔═══╝
           ╚██████╗███████╗██║██║
            ╚═════╝╚══════╝╚═╝╚═╝
```

A Dockerized CLI tool that downloads Quran audio recitations by surah number, ayah range, and reciter — then merges them into a single audio file.

**No more** finding recitations on YouTube, downloading full videos, manually cutting segments, and converting formats. Just one command:

```bash
./run.sh download 23 --from 1 --to 11 --reciter alafasy
```

---

## Quick Start

```bash
# Clone
git clone https://github.com/0aub/quran-clip.git
cd quran-clip

# Run interactive mode
./run.sh
```

That's it. Docker handles everything — Python, ffmpeg, dependencies.

---

## Usage

### Interactive Mode

```bash
./run.sh
```

Launches a full TUI with animated banner, menus, and guided workflow:

1. Pick a surah (by number, name search, or browse the full list)
2. Set ayah range (from/to)
3. Pick a reciter (browse, search, or test availability with green/red status)
4. Download + merge with progress bar

### Direct Commands

```bash
# Download specific ayahs
./run.sh download <SURAH> [OPTIONS]

# Examples
./run.sh download 23 --from 1 --to 11 --reciter alafasy
./run.sh download 67 --reciter yasseraddussary --gap 1.0
./run.sh download 36 --include-basmala --format opus

# Browse surahs
./run.sh list-surahs
./run.sh list-surahs --search "fatiha"

# Browse reciters
./run.sh list-reciters
./run.sh list-reciters --search "mishary"

# Surah info
./run.sh info 23
```

### Download Options

| Option | Default | Description |
|--------|---------|-------------|
| `--from` | `1` | Starting ayah number |
| `--to` | last ayah | Ending ayah number |
| `--reciter`, `-r` | `alafasy` | Reciter name or ID |
| `--bitrate`, `-b` | `128` | Audio bitrate in kbps |
| `--gap`, `-g` | `0.5` | Silence gap between ayahs (seconds) |
| `--format`, `-f` | `mp3` | Output format: mp3, opus, ogg, wav |
| `--output`, `-o` | auto | Output file path |
| `--include-basmala` | off | Prepend Bismillah before first ayah |
| `--quiet`, `-q` | off | Suppress progress output |

### Other Commands

```bash
./run.sh build       # Build/rebuild the Docker image
./run.sh test        # Run the test suite (51 tests)
./run.sh rebuild     # Rebuild image then run with args
```

---

## Output

Files are saved to the `output/` directory:

```
output/
├── al-muminun_1-11_alafasy.mp3
├── al-isra_23-27_yasseraddussary.mp3
├── at-takwir_15-29_muhsinalqasim.mp3
└── ...
```

Filename format: `{surah-name}_{from}-{to}_{reciter}.{format}`

Each file includes ID3 metadata (title, artist, album, track number).

---

## Reciters

47 reciters available, including:

| Reciter | ID |
|---------|----|
| Mishary Rashid Al-Afasy | `alafasy` |
| Abdul Basit (Murattal) | `abdulbasitmurattal` |
| Abdul Basit (Mujawwad) | `abdulsamad` |
| Abdurrahman As-Sudais | `abdurrahmaansudais` |
| Saud Ash-Shuraym | `saoodshuraym` |
| Mahmoud Khalil Al-Husary | `husary` |
| Mohamed Siddiq Al-Minshawi | `minshawi` |
| Yasser Ad-Dossari | `yasseraddussary` |
| Abdulmohsen Al-Qasim | `muhsinalqasim` |
| Maher Al-Muaiqly | `mahermuaiqly` |

Run `./run.sh list-reciters` for the full list. Fuzzy matching works — type "mishary" or "العفاسي" and it resolves.

---

## How It Works

```
CLI (Typer + Rich TUI)
  │
  ├─ Validate input (surah, ayah range, reciter, format)
  │
  ├─ Resolve reciter (exact → fuzzy → interactive prompt)
  │
  ├─ Download ayahs (async, 10 concurrent, retry with backoff)
  │    ├─ Primary: cdn.islamic.network (alquran.cloud)
  │    └─ Fallback: everyayah.com
  │
  ├─ Concatenate (ffmpeg concat demuxer, stream copy)
  │    ├─ Optional silence gaps between ayahs
  │    ├─ Optional Basmala prepend
  │    └─ ID3 metadata tagging
  │
  └─ Output file → ./output/
```

- **Dual-source fallback**: if the primary CDN returns 403/404, it transparently falls back to everyayah.com
- **No re-encoding**: ffmpeg stream-copies the audio segments (lossless, fast)
- **Availability testing**: interactive mode can probe all 47 reciters and show green/red status

---

## Project Structure

```
quran-clip/
├── run.sh                  # Entry point — build & run via Docker
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── Makefile
│
├── quran_clip/
│   ├── __init__.py
│   ├── __main__.py         # python -m quran_clip
│   ├── cli.py              # Typer commands + Rich TUI + animated banner
│   ├── downloader.py       # Async httpx downloads with fallback
│   ├── concatenator.py     # ffmpeg subprocess wrapper
│   ├── metadata.py         # Surah/reciter registries
│   ├── resolver.py         # Fuzzy reciter name matching
│   ├── validators.py       # Input validation
│   ├── config.py           # URLs, defaults, constants
│   ├── surahs.json         # 114 surahs (bundled)
│   └── reciters.json       # 47 reciters (bundled)
│
├── data/
│   ├── surahs.json         # Source data
│   └── reciters.json       # Source data
│
├── tests/                  # 51 tests
│   ├── test_cli.py
│   ├── test_downloader.py
│   ├── test_concatenator.py
│   ├── test_metadata.py
│   ├── test_resolver.py
│   └── test_validators.py
│
└── output/                 # Downloaded audio files
```

---

## Requirements

- **Docker** — that's it. Everything else is inside the container.

---

## License

MIT
