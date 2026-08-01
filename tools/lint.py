#!/usr/bin/env python3
"""Course linter. Run from the repository root:

    python3 tools/lint.py

Three checks, all of which have caught real defects in this course:

1. Python code blocks parse. A missing dot once turned a whole example
   into a SyntaxError that sat in the course unnoticed.
2. ASCII box diagrams have sound geometry. Every row inside a ┌…┐/└…┘
   box must carry a border at BOTH the box's left and right columns.
   Drift here is invisible while editing and obvious once rendered.
3. Relative links resolve. Module renumbering silently breaks these.

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


def main():
    ok = True
    for label, (count, failures), noun in (
        ("Python blocks", check_python(), "blocks"),
        ("Diagrams", check_diagrams(), "diagrams"),
        ("Links", check_links(), "links"),
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
