#!/usr/bin/env python3
"""Build flashcards/README.md from flashcards/cards.tsv.

    python3 tools/build_flashcards.py           # rewrite the README
    python3 tools/build_flashcards.py --check   # exit 1 if it is out of date

cards.tsv is the single source of truth, and Anki imports it directly:
one card per line, three tab-separated fields (question, answer, tag),
where the tag is `module-NN`. Edit cards.tsv, never the generated README.
"""
import html
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE = ROOT / "flashcards" / "cards.tsv"
TARGET = ROOT / "flashcards" / "README.md"


def module_titles() -> dict[str, tuple[str, str]]:
    """'07' -> ('07-reliability', 'Reliability Engineering'), from each H1."""
    titles = {}
    for readme in sorted(ROOT.glob("[0-9][0-9]-*/README.md")):
        first = readme.read_text().splitlines()[0]
        m = re.match(r"# Module (\d+): (.+)", first)
        if m:
            titles[m.group(1).zfill(2)] = (readme.parent.name, m.group(2))
    return titles


def load_cards() -> list[tuple[str, str, str]]:
    cards = []
    for n, line in enumerate(SOURCE.read_text().splitlines(), 1):
        fields = line.split("\t")
        if len(fields) != 3 or not re.fullmatch(r"module-\d\d", fields[2]):
            raise SystemExit(f"cards.tsv:{n}: expected question<TAB>answer<TAB>module-NN")
        cards.append((fields[0], fields[1], fields[2][-2:]))
    return cards


def render() -> str:
    cards, titles = load_cards(), module_titles()
    by_module: dict[str, list] = {}
    for q, a, mod in cards:
        if mod not in titles:
            raise SystemExit(f"cards.tsv: unknown module {mod}")
        by_module.setdefault(mod, []).append((q, a))

    out = [
        "# Flashcards",
        "",
        f"{len(cards)} question-and-answer cards covering all {len(titles)} modules, for",
        "spaced-repetition review. Each answer restates what its module teaches; the",
        "module link takes you to the full explanation.",
        "",
        "**Two ways to use them:**",
        "",
        "- **Here on GitHub**: read each question, answer it out loud or on paper,",
        "  then click it to reveal the answer.",
        "- **In Anki** (or any spaced-repetition app that imports text): download",
        "  [`cards.tsv`](cards.tsv), choose *File → Import*, set the separator to",
        "  *Tab*, and map the three fields to *Front*, *Back* and *Tags*. Anki then",
        "  schedules each card for you.",
        "",
        "Contributing a card? Add a line to `cards.tsv` and run",
        "`python3 tools/build_flashcards.py`; this page is generated from it.",
        "",
        "## Modules",
        "",
    ]
    for mod in sorted(by_module):
        folder, title = titles[mod]
        anchor = re.sub(r"[^\w\- ]", "", f"module {int(mod)}: {title}".lower()).replace(" ", "-")
        out.append(f"- [Module {int(mod)}: {title}](#{anchor}) — {len(by_module[mod])} cards")
    for mod in sorted(by_module):
        folder, title = titles[mod]
        out += ["", "---", "", f"## Module {int(mod)}: {title}", "",
                f"[Read the module](../{folder}/README.md)", ""]
        for q, a in by_module[mod]:
            out += ["<details>",
                    f"<summary>{html.escape(q, quote=False)}</summary>",
                    "",
                    html.escape(a, quote=False),
                    "",
                    "</details>",
                    ""]
        if out[-1] == "":
            out.pop()
    return "\n".join(out) + "\n"


def main() -> int:
    text = render()
    if "--check" in sys.argv:
        if not TARGET.exists() or TARGET.read_text() != text:
            print("flashcards/README.md is out of date: run python3 tools/build_flashcards.py")
            return 1
        return 0
    TARGET.write_text(text)
    print(f"wrote {TARGET.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
