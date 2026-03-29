"""CLI layer — Typer commands with Rich TUI, animated ASCII art banner, and interactive flow."""

from __future__ import annotations

import asyncio
import math
import time
import tempfile
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.live import Live
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, MofNCompleteColumn

from . import __version__
from .config import (
    DEFAULT_BITRATE,
    DEFAULT_FORMAT,
    DEFAULT_GAP,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_RECITER,
    SUPPORTED_FORMATS,
)
from .concatenator import ConcatError, concatenate, get_duration
from .downloader import DownloadError, download_ayahs, check_reciter_availability
from .metadata import Reciter, ReciterRegistry, SurahRegistry
from .resolver import resolve_reciter
from .validators import ValidationError, validate_ayah_range, validate_format, validate_surah

app = typer.Typer(
    name="quran-clip",
    help="Download Quran audio recitations by surah, ayah range, and reciter.",
    add_completion=False,
    invoke_without_command=True,
    no_args_is_help=False,
)

console = Console()

# ──────────────────────────────────────────────────────────────
# Animated ASCII Art Banner
# ──────────────────────────────────────────────────────────────

BANNER_LINES = [
    r"██████╗ ██╗   ██╗██████╗  █████╗ ███╗   ██╗",
    r"██╔═══██╗██║   ██║██╔══██╗██╔══██╗████╗  ██║",
    r"██║   ██║██║   ██║██████╔╝███████║██╔██╗ ██║",
    r"██║▄▄ ██║██║   ██║██╔══██╗██╔══██║██║╚██╗██║",
    r"╚██████╔╝╚██████╔╝██║  ██║██║  ██║██║ ╚████║",
    r" ╚══▀▀═╝  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝",
    r"            ██████╗██╗     ██╗██████╗ ",
    r"           ██╔════╝██║     ██║██╔══██╗",
    r"           ██║     ██║     ██║██████╔╝",
    r"           ██║     ██║     ██║██╔═══╝ ",
    r"           ╚██████╗███████╗██║██║     ",
    r"            ╚═════╝╚══════╝╚═╝╚═╝    ",
]

# Gradient palette: deep forest green <-> bright emerald wave
_GRADIENT = [
    "#003d1a", "#004d20", "#005c26", "#006b2c",
    "#007a33", "#008a3a", "#009940", "#00a848",
    "#00b850", "#00c858", "#00d860", "#00e868",
    "#10f070", "#30f880", "#50ff90", "#70ffa0",
    "#90ffb0", "#70ffa0", "#50ff90", "#30f880",
    "#10f070", "#00e868", "#00d860", "#00c858",
    "#00b850", "#00a848", "#009940", "#008a3a",
    "#007a33", "#006b2c", "#005c26", "#004d20",
]


def _colorize_banner(frame: int) -> Text:
    """Build a single frame of the animated banner with a diagonal color wave."""
    result = Text()
    total_colors = len(_GRADIENT)

    for row_idx, line in enumerate(BANNER_LINES):
        for col_idx, char in enumerate(line):
            if char == " ":
                result.append(char)
            else:
                # Diagonal wave: color index shifts with row + col + frame
                idx = (col_idx + row_idx * 2 + frame) % total_colors
                result.append(char, style=f"bold {_GRADIENT[idx]}")
        result.append("\n")

    return result


def show_banner(animate: bool | None = None) -> None:
    """Display the animated Quran-Clip banner."""
    # Auto-detect: animate only if we have a real TTY
    if animate is None:
        animate = console.is_terminal

    subtitle = Text()
    subtitle.append(f"\n  v{__version__}", style="dim")
    subtitle.append(" — Download Quran audio recitations with ease\n", style="dim")
    subtitle.append("  ﷽\n", style="bold cyan")

    if not animate:
        # Static colored banner (for non-TTY / piped output)
        console.print()
        console.print(_colorize_banner(0))
        console.print(subtitle)
        return

    # Animate: cycle colors across the banner for ~2 seconds
    frames = 40
    frame_delay = 0.05  # 50ms per frame = 2 seconds total

    with Live(console=console, refresh_per_second=20, transient=True) as live:
        for frame in range(frames):
            banner_text = _colorize_banner(frame)
            live.update(banner_text)
            time.sleep(frame_delay)

    # Print final static frame + subtitle
    console.print()
    console.print(_colorize_banner(frames))
    console.print(subtitle)


# ──────────────────────────────────────────────────────────────
# Callback for bare `quran-clip` invocation (interactive mode)
# ──────────────────────────────────────────────────────────────


@app.callback()
def main(ctx: typer.Context) -> None:
    """Quran-Clip: Download Quran audio recitations."""
    if ctx.invoked_subcommand is None:
        show_banner()
        _interactive_menu()


def _interactive_menu() -> None:
    """Show main menu and loop until user exits."""
    surah_registry = SurahRegistry()
    reciter_registry = ReciterRegistry()

    while True:
        console.print()
        console.print(Panel(
            "[bold cyan]1.[/bold cyan] Download ayahs\n"
            "[bold cyan]2.[/bold cyan] List surahs\n"
            "[bold cyan]3.[/bold cyan] List reciters\n"
            "[bold cyan]4.[/bold cyan] Surah info\n"
            "[bold cyan]5.[/bold cyan] Exit",
            title="[bold green]Main Menu[/bold green]",
            border_style="green",
            padding=(1, 2),
        ))

        choice = console.input("\n  [bold]Select an option [1-5]: [/bold]").strip()

        if choice == "1":
            _interactive_download(surah_registry, reciter_registry)
        elif choice == "2":
            _cmd_list_surahs()
        elif choice == "3":
            _cmd_list_reciters()
        elif choice == "4":
            _interactive_info(surah_registry)
        elif choice == "5":
            console.print("\n  [bold green]Ma'a salama![/bold green]\n")
            raise typer.Exit()
        else:
            console.print("  [red]Invalid choice. Please select 1-5.[/red]")


# ──────────────────────────────────────────────────────────────
# Interactive Surah Selection (browse or direct)
# ──────────────────────────────────────────────────────────────


def _pick_surah(registry: SurahRegistry):
    """Let user pick a surah by number, name search, or browsing the list."""
    console.print()
    console.print(
        "  [bold cyan]a)[/bold cyan] Enter surah number directly\n"
        "  [bold cyan]b)[/bold cyan] Search by name\n"
        "  [bold cyan]c)[/bold cyan] Browse full list"
    )
    mode = console.input("\n  [bold]How to select surah? [a/b/c]: [/bold]").strip().lower()

    if mode == "c":
        _cmd_list_surahs()
        console.print()
        raw = console.input("  [bold]Enter surah number from the list: [/bold]").strip()
    elif mode == "b":
        query = console.input("  [bold]Search surah name: [/bold]").strip()
        if not query:
            return None
        _cmd_list_surahs(search=query)
        console.print()
        raw = console.input("  [bold]Enter surah number from results: [/bold]").strip()
    else:
        raw = console.input("  [bold]Surah number (1-114): [/bold]").strip()

    if not raw:
        return None
    try:
        num = int(raw)
    except ValueError:
        console.print("  [red]Please enter a valid number (1-114).[/red]")
        return None
    try:
        validate_surah(num)
        return registry.get(num)
    except (ValidationError, KeyError) as e:
        console.print(f"  [red]Error:[/red] {e}")
        return None


# ──────────────────────────────────────────────────────────────
# Interactive Reciter Selection (browse, search, test, or direct)
# ──────────────────────────────────────────────────────────────


def _pick_reciter(
    reciter_registry: ReciterRegistry,
    surah_registry: SurahRegistry,
    surah_number: int,
    test_ayah: int,
) -> Reciter | None:
    """Let user pick a reciter with optional availability testing."""
    console.print()
    console.print(
        "  [bold cyan]a)[/bold cyan] Enter reciter name directly\n"
        "  [bold cyan]b)[/bold cyan] Search by name\n"
        "  [bold cyan]c)[/bold cyan] Browse full list\n"
        "  [bold cyan]d)[/bold cyan] Browse list + test availability for this clip"
    )
    mode = console.input("\n  [bold]How to select reciter? [a/b/c/d]: [/bold]").strip().lower()

    if mode == "d":
        # Test availability then show colored list
        return _pick_reciter_with_test(reciter_registry, surah_registry, surah_number, test_ayah)
    elif mode == "c":
        _cmd_list_reciters()
        return _prompt_reciter_choice(reciter_registry)
    elif mode == "b":
        query = console.input("  [bold]Search reciter name: [/bold]").strip()
        if not query:
            return None
        _cmd_list_reciters(search=query)
        return _prompt_reciter_choice(reciter_registry)
    else:
        raw = console.input("  [bold]Reciter name or ID [default: alafasy]: [/bold]").strip()
        raw = raw or DEFAULT_RECITER
        reciter = resolve_reciter(raw, reciter_registry)
        if reciter is None:
            console.print(f"  [red]Reciter '{raw}' not found.[/red]")
        return reciter


def _prompt_reciter_choice(registry: ReciterRegistry) -> Reciter | None:
    """After showing a list, let user type a reciter number or name."""
    console.print()
    raw = console.input("  [bold]Enter reciter # from list, or name/ID: [/bold]").strip()
    if not raw:
        return None

    # Check if it's a list number
    try:
        idx = int(raw)
        all_reciters = registry.all()
        if 1 <= idx <= len(all_reciters):
            chosen = all_reciters[idx - 1]
            console.print(f"  [green]-> Selected:[/green] {chosen.name_en} ({chosen.id})")
            return chosen
    except ValueError:
        pass

    # Otherwise try fuzzy resolve
    reciter = resolve_reciter(raw, registry)
    if reciter is None:
        console.print(f"  [red]Reciter '{raw}' not found.[/red]")
    return reciter


def _pick_reciter_with_test(
    reciter_registry: ReciterRegistry,
    surah_registry: SurahRegistry,
    surah_number: int,
    test_ayah: int,
) -> Reciter | None:
    """Test all reciters for availability, show colored results, let user pick."""
    all_reciters = reciter_registry.all()

    console.print()
    console.print(f"  [bold]Testing {len(all_reciters)} reciters for Surah {surah_number}, Ayah {test_ayah}...[/bold]")
    console.print()

    # Run availability check with progress bar
    with Progress(
        SpinnerColumn(style="green"),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(bar_width=40, style="cyan", complete_style="green"),
        MofNCompleteColumn(),
        console=console,
    ) as progress:
        task_id = progress.add_task("Testing reciters", total=len(all_reciters))

        async def _run_tests():
            results = {}
            # We run the built-in check but also advance progress per reciter
            availability = await check_reciter_availability(
                all_reciters, surah_number, test_ayah, surah_registry,
            )
            return availability

        availability = asyncio.run(_run_tests())
        progress.update(task_id, completed=len(all_reciters))

    # Show colored table
    available_reciters = []
    table = Table(
        title="Reciter Availability",
        border_style="cyan",
        header_style="bold cyan",
        show_lines=False,
        padding=(0, 1),
    )
    table.add_column("#", justify="right", width=4)
    table.add_column("Status", width=3)
    table.add_column("Name (EN)", min_width=30)
    table.add_column("Name (AR)", min_width=16, justify="right")
    table.add_column("Style", width=10)

    idx = 0
    for reciter in all_reciters:
        is_available = availability.get(reciter.id, False)
        if is_available:
            idx += 1
            available_reciters.append(reciter)
            table.add_row(
                str(idx),
                "[bold green]ON[/bold green]",
                f"[green]{reciter.name_en}[/green]",
                f"[green]{reciter.name_ar}[/green]",
                reciter.style,
            )
        else:
            table.add_row(
                "[dim]-[/dim]",
                "[bold red]--[/bold red]",
                f"[dim]{reciter.name_en}[/dim]",
                f"[dim]{reciter.name_ar}[/dim]",
                f"[dim]{reciter.style}[/dim]",
            )

    console.print()
    console.print(table)
    console.print()

    available_count = len(available_reciters)
    unavailable_count = len(all_reciters) - available_count
    console.print(f"  [green]{available_count} available[/green]  |  [red]{unavailable_count} unavailable[/red]")

    if not available_reciters:
        console.print("  [red]No reciters available for this clip.[/red]")
        return None

    # Let user pick from available ones
    console.print()
    raw = console.input("  [bold]Enter # of available reciter: [/bold]").strip()
    if not raw:
        return None

    try:
        choice = int(raw)
        if 1 <= choice <= len(available_reciters):
            chosen = available_reciters[choice - 1]
            console.print(f"  [green]-> Selected:[/green] {chosen.name_en} ({chosen.id})")
            return chosen
        else:
            console.print(f"  [red]Invalid choice. Pick 1-{len(available_reciters)}.[/red]")
            return None
    except ValueError:
        # Try fuzzy match
        reciter = resolve_reciter(raw, reciter_registry)
        if reciter is None:
            console.print(f"  [red]Reciter '{raw}' not found.[/red]")
        return reciter


# ──────────────────────────────────────────────────────────────
# Interactive Download Flow
# ──────────────────────────────────────────────────────────────


def _interactive_download(surah_registry: SurahRegistry, reciter_registry: ReciterRegistry) -> None:
    """Full interactive download wizard."""
    try:
        # Step 1: Pick surah
        surah = _pick_surah(surah_registry)
        if surah is None:
            return

        console.print(f"\n  [green]Surah {surah.number}: {surah.name_en} ({surah.name_ar}) — {surah.ayah_count} ayahs[/green]")

        # Step 2: Ayah range
        console.print()
        from_input = console.input(f"  [bold]From ayah [default: 1]: [/bold]").strip()
        from_ayah = int(from_input) if from_input else 1

        to_input = console.input(f"  [bold]To ayah [default: {surah.ayah_count}]: [/bold]").strip()
        to_ayah = int(to_input) if to_input else surah.ayah_count

        try:
            validate_ayah_range(surah.number, from_ayah, to_ayah, surah_registry)
        except ValidationError as e:
            console.print(f"  [red]Error:[/red] {e}")
            return

        console.print(f"  [green]Range: ayah {from_ayah} to {to_ayah} ({to_ayah - from_ayah + 1} ayahs)[/green]")

        # Step 3: Pick reciter (with optional availability test)
        reciter = _pick_reciter(reciter_registry, surah_registry, surah.number, from_ayah)
        if reciter is None:
            return

        # Step 4: Options
        console.print()
        gap_input = console.input("  [bold]Gap between ayahs in seconds [default: 0.5]: [/bold]").strip()
        gap = float(gap_input) if gap_input else DEFAULT_GAP

        basmala_input = console.input("  [bold]Include Basmala? (y/N): [/bold]").strip().lower()
        include_basmala = basmala_input in ("y", "yes")

    except (ValueError, KeyboardInterrupt):
        console.print("\n  [red]Cancelled.[/red]")
        return

    # Step 5: Run download
    _run_download(
        surah_number=surah.number,
        from_ayah=from_ayah,
        to_ayah=to_ayah,
        reciter_obj=reciter,
        bitrate=DEFAULT_BITRATE,
        gap=gap,
        fmt=DEFAULT_FORMAT,
        output=None,
        include_basmala=include_basmala,
        quiet=False,
        surah_registry=surah_registry,
    )


def _interactive_info(surah_registry: SurahRegistry) -> None:
    """Show surah info interactively."""
    surah = _pick_surah(surah_registry)
    if surah is None:
        return
    _print_surah_info(surah)


# ──────────────────────────────────────────────────────────────
# CLI Commands (direct / non-interactive)
# ──────────────────────────────────────────────────────────────


@app.command()
def download(
    surah_number: int = typer.Argument(..., help="Surah number (1-114)"),
    from_ayah: int = typer.Option(1, "--from", help="Starting ayah number"),
    to_ayah: int | None = typer.Option(None, "--to", help="Ending ayah number (default: last ayah)"),
    reciter: str = typer.Option(DEFAULT_RECITER, "--reciter", "-r", help="Reciter name or ID"),
    bitrate: int = typer.Option(DEFAULT_BITRATE, "--bitrate", "-b", help="Audio bitrate in kbps"),
    gap: float = typer.Option(DEFAULT_GAP, "--gap", "-g", help="Silence gap between ayahs (seconds)"),
    fmt: str = typer.Option(DEFAULT_FORMAT, "--format", "-f", help="Output format: mp3, opus, ogg, wav"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Output file path"),
    include_basmala: bool = typer.Option(False, "--include-basmala", help="Prepend Bismillah audio"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress progress output"),
) -> None:
    """Download and merge Quran ayah audio into a single file."""
    if not quiet:
        show_banner()

    surah_registry = SurahRegistry()
    reciter_registry = ReciterRegistry()

    # Validate
    try:
        validate_surah(surah_number)
        surah = surah_registry.get(surah_number)

        if to_ayah is None:
            to_ayah = surah.ayah_count

        validate_ayah_range(surah_number, from_ayah, to_ayah, surah_registry)
        validate_format(fmt)
    except ValidationError as e:
        console.print(f"\n  [red]Error:[/red] {e}")
        raise typer.Exit(code=1)

    # Resolve reciter
    reciter_obj = resolve_reciter(reciter, reciter_registry)
    if reciter_obj is None:
        console.print(
            f"\n  [red]Error:[/red] Reciter '{reciter}' not found. "
            "Use 'list-reciters' to see available reciters."
        )
        raise typer.Exit(code=1)

    _run_download(
        surah_number=surah_number,
        from_ayah=from_ayah,
        to_ayah=to_ayah,
        reciter_obj=reciter_obj,
        bitrate=bitrate,
        gap=gap,
        fmt=fmt,
        output=output,
        include_basmala=include_basmala,
        quiet=quiet,
        surah_registry=surah_registry,
    )


# ──────────────────────────────────────────────────────────────
# Core download logic
# ──────────────────────────────────────────────────────────────


def _run_download(
    *,
    surah_number: int,
    from_ayah: int,
    to_ayah: int,
    reciter_obj: Reciter,
    bitrate: int,
    gap: float,
    fmt: str,
    output: Path | None,
    include_basmala: bool,
    quiet: bool,
    surah_registry: SurahRegistry,
) -> None:
    """Core download logic shared between CLI and interactive mode."""
    surah = surah_registry.get(surah_number)

    # Build output path
    if output is None:
        DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        filename = f"{surah.slug}_{from_ayah}-{to_ayah}_{reciter_obj.id.split('.')[-1]}.{fmt}"
        output = DEFAULT_OUTPUT_DIR / filename

    if not quiet:
        console.print()
        console.print(Panel(
            f"[bold]Surah:[/bold]    {surah.name_en} — #{surah.number}\n"
            f"[bold]          [/bold]\u200F{surah.name_ar}\n"
            f"[bold]Ayahs:[/bold]    {from_ayah} to {to_ayah} ({to_ayah - from_ayah + 1} ayahs)\n"
            f"[bold]Reciter:[/bold]  {reciter_obj.name_en}\n"
            f"[bold]          [/bold]\u200F{reciter_obj.name_ar}\n"
            f"[bold]Format:[/bold]   {fmt} @ {bitrate}kbps\n"
            f"[bold]Gap:[/bold]      {gap}s between ayahs\n"
            f"[bold]Basmala:[/bold]  {'Yes' if include_basmala else 'No'}\n"
            f"[bold]Output:[/bold]   {output}",
            title="[bold green]Download Plan[/bold green]",
            border_style="cyan",
            padding=(1, 2),
        ))
        console.print()

    # Download
    with tempfile.TemporaryDirectory(prefix="quran_clip_") as tmp:
        tmp_path = Path(tmp)

        try:
            audio_files = asyncio.run(
                download_ayahs(
                    surah_number=surah_number,
                    from_ayah=from_ayah,
                    to_ayah=to_ayah,
                    reciter=reciter_obj,
                    surah_registry=surah_registry,
                    temp_dir=tmp_path,
                    bitrate=bitrate,
                    include_basmala=include_basmala,
                    quiet=quiet,
                )
            )
        except DownloadError as e:
            console.print(f"\n  [red]Download failed:[/red] {e}")
            raise typer.Exit(code=1)

        # Concatenate
        try:
            output.parent.mkdir(parents=True, exist_ok=True)
            concatenate(
                audio_files=audio_files,
                output_path=output,
                surah_name=surah.name_en,
                surah_number=surah_number,
                from_ayah=from_ayah,
                to_ayah=to_ayah,
                reciter_name=reciter_obj.name_en,
                gap=gap,
                quiet=quiet,
            )
        except ConcatError as e:
            console.print(f"\n  [red]Merge failed:[/red] {e}")
            raise typer.Exit(code=1)

    # Summary
    if not quiet:
        duration = get_duration(output)
        size_mb = output.stat().st_size / (1024 * 1024)
        minutes = int(duration // 60)
        seconds = int(duration % 60)

        console.print()
        console.print(Panel(
            f"[bold green]Done![/bold green]\n\n"
            f"  [bold]File:[/bold]     {output}\n"
            f"  [bold]Duration:[/bold] {minutes}:{seconds:02d}\n"
            f"  [bold]Size:[/bold]     {size_mb:.1f} MB",
            title="[bold green]Output[/bold green]",
            border_style="green",
            padding=(1, 2),
        ))
        console.print()


# ──────────────────────────────────────────────────────────────
# List / Info Commands
# ──────────────────────────────────────────────────────────────


@app.command("list-surahs")
def list_surahs(
    search: str | None = typer.Option(None, "--search", "-s", help="Filter by partial surah name"),
    lang: str = typer.Option("en", "--lang", "-l", help="Display language: en, ar"),
) -> None:
    """Browse all 114 surahs."""
    show_banner()
    _cmd_list_surahs(search=search, lang=lang)


def _normalize_arabic(text: str) -> str:
    """Normalize Arabic text for search: strip diacritics, normalize alef/taa forms."""
    import unicodedata
    # Remove diacritics (tashkeel)
    result = "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )
    # Normalize common Arabic letter variants
    result = result.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ٱ", "ا")
    result = result.replace("ة", "ه").replace("ى", "ي")
    return result.strip()


def _arabic_match(query: str, target: str, threshold: int = 50) -> bool:
    """Check if Arabic query matches target using normalized fuzzy matching."""
    from thefuzz import fuzz
    nq = _normalize_arabic(query)
    nt = _normalize_arabic(target)
    # Direct substring check first (fastest)
    if nq in nt or nt in nq:
        return True
    return fuzz.partial_ratio(nq, nt) >= threshold


def _is_arabic(text: str) -> bool:
    """Check if text contains Arabic characters."""
    return any("\u0600" <= c <= "\u06FF" for c in text)


def _cmd_list_surahs(search: str | None = None, lang: str = "en") -> None:
    """Shared list-surahs logic."""
    registry = SurahRegistry()
    surahs = registry.all()

    if search:
        from thefuzz import fuzz
        search = search.strip()
        surahs = [
            s for s in surahs
            if fuzz.partial_ratio(search.lower(), s.name_en.lower()) >= 60
            or _arabic_match(search, s.name_ar)
        ]
        if not surahs:
            console.print(f"\n  [yellow]No surahs matching '{search}'[/yellow]")
            return

    table = Table(
        title="Surahs of the Quran",
        border_style="cyan",
        header_style="bold cyan",
        show_lines=False,
        padding=(0, 1),
    )
    table.add_column("#", style="bold green", justify="right", width=4)
    table.add_column("Name (EN)", style="white", min_width=18)
    table.add_column("Name (AR)", style="bold", min_width=14, justify="right")
    table.add_column("Ayahs", style="yellow", justify="right", width=6)
    table.add_column("Type", style="dim", width=8)

    for s in surahs:
        table.add_row(
            str(s.number),
            s.name_en,
            s.name_ar,
            str(s.ayah_count),
            s.revelation,
        )

    console.print()
    console.print(table)
    console.print()


@app.command("list-reciters")
def list_reciters(
    search: str | None = typer.Option(None, "--search", "-s", help="Filter by partial name"),
    refresh: bool = typer.Option(False, "--refresh", help="Refresh from API (not yet implemented)"),
) -> None:
    """Browse available reciters."""
    show_banner()
    _cmd_list_reciters(search=search)


def _cmd_list_reciters(search: str | None = None) -> None:
    """Shared list-reciters logic."""
    registry = ReciterRegistry()
    reciters = registry.all()

    if search:
        from thefuzz import fuzz
        search = search.strip()
        reciters = [
            r for r in reciters
            if fuzz.partial_ratio(search.lower(), r.name_en.lower()) >= 60
            or _arabic_match(search, r.name_ar)
            or fuzz.partial_ratio(search.lower(), r.id.lower()) >= 60
        ]
        if not reciters:
            console.print(f"\n  [yellow]No reciters matching '{search}'[/yellow]")
            return

    table = Table(
        title="Available Reciters",
        border_style="cyan",
        header_style="bold cyan",
        show_lines=False,
        padding=(0, 1),
    )
    table.add_column("#", style="bold green", justify="right", width=4)
    table.add_column("ID", style="green", min_width=24)
    table.add_column("Name (EN)", style="white", min_width=30)
    table.add_column("Name (AR)", style="bold", min_width=20, justify="right")
    table.add_column("Style", style="yellow", width=10)

    for i, r in enumerate(reciters, 1):
        table.add_row(str(i), r.id, r.name_en, r.name_ar, r.style)

    console.print()
    console.print(table)
    console.print()


@app.command()
def info(
    surah_number: int = typer.Argument(..., help="Surah number (1-114)"),
) -> None:
    """Show detailed surah information."""
    show_banner()

    registry = SurahRegistry()
    try:
        validate_surah(surah_number)
        surah = registry.get(surah_number)
    except ValidationError as e:
        console.print(f"\n  [red]Error:[/red] {e}")
        raise typer.Exit(code=1)

    _print_surah_info(surah)


def _print_surah_info(surah) -> None:
    """Display surah info panel."""
    console.print()
    console.print(Panel(
        f"[bold]Number:[/bold]     {surah.number}\n"
        f"[bold]Name:[/bold]       {surah.name_en}\n"
        f"[bold]             [/bold]\u200F{surah.name_ar}\n"
        f"[bold]Revelation:[/bold] {surah.revelation}\n"
        f"[bold]Ayahs:[/bold]      {surah.ayah_count}",
        title=f"[bold green]Surah {surah.name_en}[/bold green]",
        border_style="cyan",
        padding=(1, 2),
    ))
    console.print()
