#!/usr/bin/env python3
"""Course linter. Run from the repository root:

    python3 tools/lint.py

Five checks, all of which have caught real defects in this course:

1. Python code blocks parse. A missing dot once turned a whole example
   into a SyntaxError that sat in the course unnoticed.
2. ASCII box diagrams have sound geometry. Every row inside a ┌…┐/└…┘
   box must carry a border at BOTH the box's left and right columns.
   Drift here is invisible while editing and obvious once rendered.
3. Relative links resolve. Module renumbering silently breaks these.
4. Anchor fragments resolve. A Table of Contents entry or cross-module
   `#some-heading` link is invisible-while-editing in the same way the
   diagram geometry is — it only breaks when a reader clicks it.
5. Mermaid blocks are well-formed. GitHub renders a broken Mermaid block
   as a red error box, which looks worse than no diagram at all — and
   the failure is invisible until the page is viewed on GitHub.

Exits non-zero if anything fails, so it works as a CI step or a
pre-commit hook.
"""
import ast
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

# --- diagram geometry -------------------------------------------------

BOXCHARS = set("─│┌┐└┘├┤┬┴┼╭╮╰╯┏┓┗┛┃━")
LEFT_BORDER = "│├╞┝┟┢┃"
RIGHT_BORDER = "│┤╡┥┧┪┃"
BOTTOM_RIGHT = "┘┙┚┛"
TOP_RUN = set("─┬▼▲")   # legal inside a box's top border
BOT_RUN = set("─┬┴")    # legal inside a box's bottom border


def fences(lines):
    """Yield (start, end) index pairs for the interior of ``` fences."""
    inside, start = False, 0
    for i, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            if inside:
                yield start, i
                inside = False
            else:
                inside, start = True, i + 1


def find_boxes(lines, lo, hi):
    """Real boxes only: a solid ┌───┐ top with a solid └───┘ bottom.

    `┌────┼────┐` is a fan-out connector, not a box top — the ┼ is an
    incoming edge from the row above. Excluding those keeps the linter
    from demanding borders on rows that correctly have none.
    """
    boxes = []
    for top in range(lo, hi):
        line = lines[top]
        col = -1
        while True:
            col = line.find("┌", col + 1)
            if col == -1:
                break
            right = line.find("┐", col + 1)
            if right == -1 or not set(line[col + 1:right]) <= TOP_RUN:
                continue
            for j in range(top + 1, hi):
                cand = lines[j]
                if len(cand) > col and cand[col] == "└":
                    if (len(cand) > right and cand[right] in BOTTOM_RIGHT
                            and set(cand[col + 1:right]) <= BOT_RUN):
                        boxes.append((top, j, col, right))
                    break
    return boxes


def check_diagrams():
    failures = []
    diagrams = 0
    for md in sorted(ROOT.glob("*/README.md")):
        lines = md.read_text().split("\n")
        for lo, hi in fences(lines):
            if not any(set(l) & BOXCHARS for l in lines[lo:hi]):
                continue
            diagrams += 1
            for top, bottom, left, right in find_boxes(lines, lo, hi):
                for r in range(top + 1, bottom):
                    line = lines[r]
                    if not line.strip():
                        continue
                    if len(line) <= left or line[left] not in LEFT_BORDER:
                        failures.append(
                            f"{md.relative_to(ROOT)}:{r + 1} "
                            f"missing left border at col {left}")
                    if len(line) <= right or line[right] not in RIGHT_BORDER:
                        failures.append(
                            f"{md.relative_to(ROOT)}:{r + 1} "
                            f"missing right border at col {right}")
    return diagrams, failures


# --- python blocks ----------------------------------------------------

PY_FENCE = re.compile(r"```python\n(.*?)```", re.S)


def check_python():
    failures = []
    blocks = 0
    for md in sorted(ROOT.glob("*/README.md")):
        text = md.read_text()
        for m in PY_FENCE.finditer(text):
            blocks += 1
            body = m.group(1)
            offset = text[:m.start(1)].count("\n") + 1
            try:
                ast.parse(body)
            except SyntaxError as exc:
                line = offset + (exc.lineno or 1) - 1
                failures.append(
                    f"{md.relative_to(ROOT)}:{line} {exc.msg}")
    return blocks, failures


# --- links ------------------------------------------------------------

REL_LINK = re.compile(r"\]\((\.\./[0-9A-Za-z._/-]+?)\)")
ROOT_LINK = re.compile(r"\]\(([0-9]{2}-[a-z-]+/README\.md)\)")


def check_links():
    failures = []
    count = 0
    for md in sorted(ROOT.glob("*/README.md")):
        for target in REL_LINK.findall(md.read_text()):
            count += 1
            if not (md.parent / target).exists():
                failures.append(f"{md.relative_to(ROOT)} -> {target}")
    readme = ROOT / "README.md"
    for target in ROOT_LINK.findall(readme.read_text()):
        count += 1
        if not (ROOT / target).exists():
            failures.append(f"README.md -> {target}")
    return count, failures


# --- anchors ------------------------------------------------------------

ATX_HEADING = re.compile(r"^(#{1,6})\s+(\S.*?)\s*$")
LINK_TARGET = re.compile(r"\]\(([^()\s]+)\)")
ROOT_PATH = re.compile(r"^[0-9]{2}-[a-z-]+/README\.md$")


def slugify(text):
    """GitHub's heading-to-anchor algorithm: lowercase, drop punctuation
    (not word chars, spaces, or hyphens), then turn each space into a
    hyphen. Whitespace left behind by a removed character (e.g. the
    "&" in "Rate Limiting & Throttling") becomes its own hyphen, which
    is why some real anchors below have a double dash.
    """
    text = text.strip().lower()
    text = re.sub(r"[^\w\- ]", "", text)
    return text.replace(" ", "-")


def heading_slugs(lines):
    """Ordered GitHub anchor slugs for a document's ATX headings, with
    GitHub's own -1, -2, ... suffixing for repeated slugs on one page.
    """
    fenced = set()
    for lo, hi in fences(lines):
        fenced.update(range(lo, hi))
    seen = {}
    slugs = []
    for i, line in enumerate(lines):
        if i in fenced:
            continue
        m = ATX_HEADING.match(line)
        if not m:
            continue
        slug = slugify(m.group(2))
        n = seen.get(slug, 0)
        seen[slug] = n + 1
        slugs.append(slug if n == 0 else f"{slug}-{n}")
    return slugs


def check_anchors():
    failures = []
    count = 0
    slug_cache = {}

    def slugs_for(path):
        if path not in slug_cache:
            slug_cache[path] = (
                set(heading_slugs(path.read_text().split("\n")))
                if path.exists() else None
            )
        return slug_cache[path]

    for md in sorted(ROOT.glob("*/README.md")) + [ROOT / "README.md"]:
        lines = md.read_text().split("\n")
        fenced = set()
        for lo, hi in fences(lines):
            fenced.update(range(lo, hi))
        text = "\n".join(lines)
        for m in LINK_TARGET.finditer(text):
            target = m.group(1)
            if "#" not in target or "://" in target:
                continue
            line_no = text[:m.start()].count("\n")
            if line_no in fenced:
                continue
            path_part, frag = target.split("#", 1)
            if not frag:
                continue
            if path_part == "":
                target_path = md
            elif path_part.startswith("../") or ROOT_PATH.match(path_part):
                target_path = (md.parent / path_part).resolve()
            else:
                continue
            count += 1
            valid = slugs_for(target_path)
            if valid is None or frag not in valid:
                failures.append(
                    f"{md.relative_to(ROOT)}:{line_no + 1} -> {target}")
    return count, failures


# --- mermaid ---------------------------------------------------------

MERMAID_TYPES = (
    "flowchart", "graph", "stateDiagram-v2", "stateDiagram", "sequenceDiagram",
    "classDiagram", "erDiagram", "journey", "gantt", "pie", "mindmap",
    "timeline", "gitGraph", "quadrantChart", "sankey-beta", "block-beta",
)


def check_mermaid():
    """Catch the errors that render as a red box on GitHub.

    Not a parser — a parser would need mermaid itself. These are the
    three mistakes that actually happen when hand-writing these blocks.
    """
    failures = []
    blocks = 0
    for md in sorted(ROOT.glob("*/README.md")) + [ROOT / "README.md"]:
        lines = md.read_text().split("\n")
        inside, start, is_mermaid = False, 0, False
        for i, line in enumerate(lines):
            if not line.lstrip().startswith("```"):
                continue
            if inside:
                if is_mermaid:
                    blocks += 1
                    failures.extend(
                        _mermaid_problems(md, lines[start:i], start))
                inside = False
            else:
                inside = True
                start = i + 1
                is_mermaid = line.strip() == "```mermaid"
    return blocks, failures


def _mermaid_problems(md, body, offset):
    problems = []
    rel = md.relative_to(ROOT)
    content = [l for l in body if l.strip()]
    if not content:
        return [f"{rel}:{offset + 1} empty mermaid block"]

    header = content[0].strip()
    if not header.startswith(MERMAID_TYPES):
        problems.append(
            f"{rel}:{offset + 1} unknown diagram type: {header[:40]!r}")

    for n, line in enumerate(body):
        ln = offset + n + 1
        # Unbalanced label brackets/quotes are the usual hand-editing slip.
        for open_c, close_c in (("[", "]"), ("(", ")"), ("{", "}")):
            if line.count(open_c) != line.count(close_c):
                problems.append(
                    f"{rel}:{ln} unbalanced {open_c}{close_c} in mermaid line")
        if line.count('"') % 2:
            problems.append(f"{rel}:{ln} odd number of quotes in mermaid line")
        # A bare `#` inside a label is a mermaid comment and eats the line.
        if "%%" not in line and line.strip().startswith("#"):
            problems.append(f"{rel}:{ln} mermaid comments use %%, not #")
    return problems


def main():
    ok = True
    for label, (count, failures), noun in (
        ("Python blocks", check_python(), "blocks"),
        ("Diagrams", check_diagrams(), "diagrams"),
        ("Links", check_links(), "links"),
        ("Anchors", check_anchors(), "anchors"),
        ("Mermaid", check_mermaid(), "blocks"),
    ):
        if failures:
            ok = False
            print(f"FAIL  {label}: {len(failures)} problem(s) in {count} {noun}")
            for f in failures[:25]:
                print(f"        {f}")
            if len(failures) > 25:
                print(f"        … and {len(failures) - 25} more")
        else:
            print(f"ok    {label}: {count} {noun} checked")
    if not ok:
        print("\nlint failed")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
