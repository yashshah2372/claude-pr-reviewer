"""Parse a unified diff into per-file chunks and the new-file lines GitHub lets us comment on."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


@dataclass
class FileDiff:
    path: str
    text: str
    commentable: set[int] = field(default_factory=set)  # new-file line numbers inside hunks


def parse(diff: str) -> list[FileDiff]:
    files: list[FileDiff] = []
    cur: FileDiff | None = None
    new_line = 0
    for raw in diff.splitlines():
        if raw.startswith("diff --git "):
            cur = None
            continue
        if raw.startswith("+++ "):
            path = raw[4:].strip()
            if path == "/dev/null":  # deleted file, nothing to comment on
                cur = None
                continue
            cur = FileDiff(path=path.removeprefix("b/"), text="")
            files.append(cur)
            continue
        if cur is None or raw.startswith("--- "):
            continue
        m = HUNK.match(raw)
        if m:
            new_line = int(m.group(1))
            cur.text += raw + "\n"
            continue
        if raw.startswith("+"):
            cur.commentable.add(new_line)
            cur.text += f"{new_line:>5} {raw}\n"
            new_line += 1
        elif raw.startswith("-"):
            cur.text += f"{'':>5} {raw}\n"
        elif raw.startswith("\\"):
            continue  # "\ No newline at end of file"
        else:
            cur.commentable.add(new_line)
            cur.text += f"{new_line:>5} {raw}\n"
            new_line += 1
    return files


def select(files: list[FileDiff], max_chars: int, skip_globs: tuple[str, ...]) -> tuple[list[FileDiff], list[str]]:
    """Keep files in order until the budget is used. Returns (kept, skipped) so skips can be reported, never hidden."""
    from fnmatch import fnmatch

    kept, skipped, used = [], [], 0
    for f in files:
        if any(fnmatch(f.path, g) for g in skip_globs):
            skipped.append(f"{f.path} (ignored pattern)")
        elif used + len(f.text) > max_chars:
            skipped.append(f"{f.path} (diff too large for one review)")
        else:
            kept.append(f)
            used += len(f.text)
    return kept, skipped
