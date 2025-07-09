import os
from pathlib import Path
from typing import List, Iterator

def find_files(
    directory: str, patterns: List[str], ignore_patterns: List[str]
) -> Iterator[str]:
    """Find files matching patterns in a directory, excluding ignored ones."""
    from fnmatch import fnmatch

    def should_ignore_path(path: str, ignore_patterns: List[str]) -> bool:
        """Check if a path should be ignored based on gitignore patterns."""
        for pattern in ignore_patterns:
            # Handle directory patterns (ending with /)
            if pattern.endswith('/'):
                dir_pattern = pattern.rstrip('/')
                # Check if any part of the path matches the directory pattern
                path_parts = path.split(os.sep)
                for i in range(len(path_parts)):
                    # Check if the directory pattern matches at any level
                    if fnmatch(path_parts[i], dir_pattern):
                        return True
                    # Also check if the full path up to this point matches
                    partial_path = os.sep.join(path_parts[:i+1])
                    if fnmatch(partial_path, dir_pattern):
                        return True
            else:
                # Regular file/path pattern
                if fnmatch(path, pattern):
                    return True
        return False

    for root, dirs, files in os.walk(directory):
        # Correctly handle directory pruning
        dirs[:] = [d for d in dirs if not should_ignore_path(
            os.path.relpath(os.path.join(root, d), directory), ignore_patterns
        )]

        for basename in files:
            # Check if the file path itself is ignored
            rel_path = os.path.relpath(os.path.join(root, basename), directory)
            if should_ignore_path(rel_path, ignore_patterns):
                continue

            if any(fnmatch(basename, pattern) for pattern in patterns):
                yield os.path.join(root, basename)

def get_project_structure(directory: str, ignore_patterns: List[str]) -> str:
    """Generate a string representing the project structure."""
    from fnmatch import fnmatch

    def should_ignore_path(path: str, ignore_patterns: List[str]) -> bool:
        """Check if a path should be ignored based on gitignore patterns."""
        for pattern in ignore_patterns:
            # Handle directory patterns (ending with /)
            if pattern.endswith('/'):
                dir_pattern = pattern.rstrip('/')
                # Check if any part of the path matches the directory pattern
                path_parts = path.split(os.sep)
                for i in range(len(path_parts)):
                    # Check if the directory pattern matches at any level
                    if fnmatch(path_parts[i], dir_pattern):
                        return True
                    # Also check if the full path up to this point matches
                    partial_path = os.sep.join(path_parts[:i+1])
                    if fnmatch(partial_path, dir_pattern):
                        return True
            else:
                # Regular file/path pattern
                if fnmatch(path, pattern):
                    return True
        return False

    lines = []
    for root, dirs, files in os.walk(directory, topdown=True):
        rel_root = os.path.relpath(root, directory)
        if rel_root == '.':
            rel_root = ''
        
        # Filter out ignored directories
        dirs[:] = [d for d in dirs if not should_ignore_path(os.path.join(rel_root, d) if rel_root else d, ignore_patterns)]
        files = [f for f in files if not should_ignore_path(os.path.join(rel_root, f) if rel_root else f, ignore_patterns)]

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