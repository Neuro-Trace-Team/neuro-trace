from pathlib import Path


def find_project_root(marker="database"):
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / marker).exists():
            return parent
        if parent == parent.parent:
            break
    raise FileNotFoundError(f"Could not find project root containing '{marker}'")