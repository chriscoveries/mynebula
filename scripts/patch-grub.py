#!/usr/bin/env python3
"""Add the unattended autoinstall flag to Ubuntu Server installer GRUB lines."""
from __future__ import annotations
import argparse
from pathlib import Path
import re

INSTALL_ENTRY = re.compile(r"^\s*linux(?:efi)?\s+.*?/casper/(?:hwe-)?vmlinuz(?=\s|$)")


def patch(contents: str) -> tuple[str, int]:
    result = []
    changed = 0
    for line in contents.splitlines(keepends=True):
        if INSTALL_ENTRY.search(line) and not re.search(r"\bautoinstall\b", line):
            newline = "\n" if line.endswith("\n") else ""
            value = line[:-1] if newline else line
            cut = value.find(" ---")
            if cut == -1:
                value += " autoinstall"
            else:
                value = value[:cut] + " autoinstall" + value[cut:]
            line = value + newline
            changed += 1
        result.append(line)
    return "".join(result), changed


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("grub_config")
    args = p.parse_args()
    path = Path(args.grub_config)
    amended, count = patch(path.read_text(encoding="utf-8"))
    if not count:
        raise SystemExit("No installer entry changed. Refusing ISO build.")
    path.write_text(amended, encoding="utf-8")
    print(f"Patched {count} Ubuntu installer GRUB entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
