import os
from pathlib import Path
from typing import List, Iterator

def find_files(
    directory: str, patterns: List[str], ignore_patterns: List[str]
) -> Iterator[str]:
    """Find files matching patterns in a directory, excluding ignored ones."""
    from fnmatch import fnmatch

    for root, dirs, files in os.walk(directory):
        # Correctly handle directory pruning
        dirs[:] = [d for d in dirs if not any(
            fnmatch(os.path.relpath(os.path.join(root, d), directory), ignore)
            for ignore in ignore_patterns
        )]

        for basename in files:
            # Check if the file path itself is ignored
            rel_path = os.path.relpath(os.path.join(root, basename), directory)
            if any(fnmatch(rel_path, ignore) for ignore in ignore_patterns):
                continue

            if any(fnmatch(basename, pattern) for pattern in patterns):
                yield os.path.join(root, basename)

def get_project_structure(directory: str, ignore_patterns: List[str]) -> str:
    """Generate a string representing the project structure."""
    from fnmatch import fnmatch

    lines = []
    for root, dirs, files in os.walk(directory, topdown=True):
        rel_root = os.path.relpath(root, directory)
        if rel_root == '.':
            rel_root = ''
        
        # Filter out ignored directories
        dirs[:] = [d for d in dirs if not any(fnmatch(os.path.join(rel_root, d), ignore) for ignore in ignore_patterns)]
        files = [f for f in files if not any(fnmatch(os.path.join(rel_root, f), ignore) for ignore in ignore_patterns)]

        if rel_root:
            level = rel_root.count(os.sep)
            indent = "    " * level
            lines.append(f"{indent}├── {os.path.basename(root)}/")
        else:
            level = -1
            lines.append(f"{os.path.basename(directory)}/")

        sub_indent = "    " * (level + 1)
        for f in sorted(files):
            lines.append(f"{sub_indent}├── {f}")
            
    return "\n".join(lines)

def load_gitignore_patterns(project_dir: str) -> List[str]:
    """Load patterns from .gitignore file."""
    gitignore_path = Path(project_dir) / ".gitignore"
    if gitignore_path.exists():
        with open(gitignore_path, "r") as f:
            return [
                line.strip()
                for line in f
                if line.strip() and not line.startswith("#")
            ]
    return []