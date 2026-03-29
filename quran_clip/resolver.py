"""Reciter name resolution: exact -> fuzzy -> interactive prompt."""

from __future__ import annotations

from thefuzz import fuzz, process
from rich.console import Console
from rich.prompt import IntPrompt

from .metadata import Reciter, ReciterRegistry

console = Console()

FUZZY_THRESHOLD = 60


def resolve_reciter(query: str, registry: ReciterRegistry) -> Reciter | None:
    """Resolve a reciter query string to a Reciter object.

    Resolution order:
    1. Exact ID match (e.g., "ar.alafasy")
    2. Exact short ID match (e.g., "alafasy" -> "ar.alafasy")
    3. Fuzzy match against English and Arabic names
    4. Interactive prompt if ambiguous
    """
    # 1. Exact full ID match
    exact = registry.get(query)
    if exact:
        return exact

    # 2. Short ID match — try prefixing with "ar."
    if not query.startswith("ar."):
        prefixed = registry.get(f"ar.{query}")
        if prefixed:
            return prefixed

    # 3. Fuzzy match against all names
    candidates = _fuzzy_search(query, registry)

    if not candidates:
        return None

    if len(candidates) == 1:
        match = candidates[0]
        console.print(f"  [green]-> Resolved to:[/green] {match.name_en} ({match.id})")
        return match

    # 4. Ambiguous — interactive prompt
    return _interactive_select(candidates)


def _fuzzy_search(query: str, registry: ReciterRegistry) -> list[Reciter]:
    """Search reciters by fuzzy matching against English/Arabic names and IDs."""
    query_lower = query.lower()
    scored: list[tuple[Reciter, int]] = []

    for reciter in registry.all():
        # Score against multiple fields
        scores = [
            fuzz.partial_ratio(query_lower, reciter.name_en.lower()),
            fuzz.partial_ratio(query_lower, reciter.name_ar),
            fuzz.partial_ratio(query_lower, reciter.id.lower()),
        ]
        best = max(scores)
        if best >= FUZZY_THRESHOLD:
            scored.append((reciter, best))

    # Sort by score descending
    scored.sort(key=lambda x: x[1], reverse=True)
    return [r for r, _ in scored]


def _interactive_select(candidates: list[Reciter]) -> Reciter | None:
    """Show numbered list and let user pick."""
    console.print("\n  [yellow]Multiple matches found:[/yellow]")
    for i, reciter in enumerate(candidates, 1):
        style_tag = f" ({reciter.style})" if reciter.style else ""
        console.print(f"    [cyan]{i}.[/cyan] {reciter.name_en}{style_tag} — [dim]{reciter.id}[/dim]")

    console.print()
    choice = IntPrompt.ask(
        "  [bold]Select[/bold]",
        choices=[str(i) for i in range(1, len(candidates) + 1)],
    )
    return candidates[choice - 1]
