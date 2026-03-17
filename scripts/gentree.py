"""
Directory README Tree Generator (Gitignore Aware)

Generates a directory-only tree for a project and inserts it into README.md
files between the markers:

<!-- filetree start -->
<!-- filetree end -->

Each README shows the full tree with the current directory marked as
"(You are here)".

Directories ignored by .gitignore are excluded from both traversal and
tree generation.
"""

import os
from pathlib import Path
import pathspec

START_MARKER = "<!-- filetree start -->"
END_MARKER = "<!-- filetree end -->"


def load_gitignore(root: Path):
    gitignore = root / ".gitignore"

    if not gitignore.exists():
        return pathspec.PathSpec.from_lines("gitwildmatch", [])

    with gitignore.open() as f:
        ignored_lines = f.read().splitlines()
        ignored_lines.append(".git/")
        return pathspec.PathSpec.from_lines("gitwildmatch", ignored_lines)


def is_ignored(path: Path, root: Path, spec):
    rel = path.relative_to(root)

    rel_str = str(rel)
    if rel.is_dir() and not rel_str.endswith("/"):
        rel_str += "/"

    return spec.match_file(rel_str)


def build_tree(root: Path, current: Path, spec):
    lines = [root.name]
    lines.extend(_walk(root, current, root, spec, ""))
    return "\n".join(lines)


def _walk(path: Path, current: Path, root: Path, spec, prefix):
    dirs = [
        p
        for p in sorted(path.iterdir(), key=lambda x: x.name)
        if p.is_dir() and not is_ignored(p, root, spec)
    ]

    lines = []

    for i, d in enumerate(dirs):
        connector = "└── " if i == len(dirs) - 1 else "├── "
        next_prefix = "    " if i == len(dirs) - 1 else "│   "

        label = d.name
        if d.resolve() == current.resolve():
            label += " (You are here)"

        lines.append(prefix + connector + label)

        lines.extend(_walk(d, current, root, spec, prefix + next_prefix))

    return lines


def update_readme(readme_path: Path, tree_text: str) -> bool:
    content = readme_path.read_text()

    start = content.find(START_MARKER)
    end = content.find(END_MARKER)

    if start == -1 or end == -1 or end < start:
        return False

    before = content[: start + len(START_MARKER)]
    after = content[end:]

    new_section = f"\n\n```text\n{tree_text}\n```\n\n"

    updated = before + new_section + after
    readme_path.write_text(updated)

    return True


def main(root_path: str):
    root = Path(root_path).resolve()
    spec = load_gitignore(root)

    for dirpath, dirnames, filenames in os.walk(root):
        dirpath = Path(dirpath)

        if is_ignored(dirpath, root, spec):
            continue

        if "README.md" not in filenames:
            continue

        readme_path = dirpath / "README.md"

        tree = build_tree(root, dirpath, spec)

        updated = update_readme(readme_path, tree)

        if updated:
            print(f"Updated: {readme_path}")
        else:
            print(f"Found but not updated: {readme_path}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("root", help="Project root directory")

    args = parser.parse_args()

    main(args.root)
