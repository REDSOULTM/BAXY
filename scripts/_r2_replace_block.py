"""Helper for R2 block-replacement (used by Claude during the sprint).

Usage:
  python scripts/_r2_replace_block.py <file> <start_line_1based> <end_line_1based> <new_text_file>

Replaces lines [start..end] (1-based, inclusive) of <file> with the content
of <new_text_file>. Useful for the R2 refactor pattern where blocks are
extracted to sibling modules and the original is replaced by a re-export
comment. Cross-platform; works around the bash quoting issues we keep
hitting with multi-line python -c invocations.
"""
from __future__ import annotations
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 5:
        print("usage: <file> <start_1based> <end_1based> <new_text_file>")
        return 1
    target = Path(sys.argv[1])
    start = int(sys.argv[2])
    end = int(sys.argv[3])
    new_text_file = Path(sys.argv[4])
    lines = target.read_text(encoding="utf-8").splitlines(keepends=True)
    new_text = new_text_file.read_text(encoding="utf-8")
    # Show what's at the boundary for sanity
    print(f"pre (kept):   {start-1}: {lines[start-2][:80]!r}")
    print(f"start (cut):  {start}: {lines[start-1][:80]!r}")
    print(f"end (cut):    {end}: {lines[end-1][:80]!r}")
    print(f"post (kept):  {end+1}: {lines[end][:80]!r}")
    out = lines[:start-1] + [new_text] + lines[end:]
    target.write_text("".join(out), encoding="utf-8")
    print(f"after: {sum(1 for _ in open(target, encoding='utf-8'))} lines")
    return 0


if __name__ == "__main__":
    sys.exit(main())
