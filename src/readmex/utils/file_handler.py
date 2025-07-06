import os
from pathlib import Path
from typing import List, Iterator

def find_files(
    directory: str, patterns: List[str], ignore_patterns: List[str]
) -> Iterator[str]:
    """Find files matching patterns in a directory, excluding ignored ones."""
    from fnmatch import fnmatch

    for root, dirs, files in os.walk(directory):
        # 正确处理目录修剪，避免遍历被忽略的目录
        dirs[:] = [d for d in dirs if not any(
            fnmatch(os.path.relpath(os.path.join(root, d), directory), ignore) or
            fnmatch(d, ignore) or
            fnmatch(os.path.join(os.path.relpath(root, directory), d), ignore)
            for ignore in ignore_patterns
        )]

        for basename in files:
            # 获取文件的相对路径
            rel_path = os.path.relpath(os.path.join(root, basename), directory)
            
            # 检查文件是否应该被忽略 - 更全面的忽略检查
            should_ignore = False
            for ignore in ignore_patterns:
                if (fnmatch(rel_path, ignore) or 
                    fnmatch(basename, ignore) or
                    fnmatch(os.path.join(os.path.relpath(root, directory), basename), ignore)):
                    should_ignore = True
                    break
            
            if should_ignore:
                continue

            # 检查文件是否匹配所需的模式
            if any(fnmatch(basename, pattern) for pattern in patterns):
                yield os.path.join(root, basename)

def _should_ignore_path(path: str, basename: str, ignore_patterns: List[str], is_dir: bool = False) -> bool:
    """
    检查路径是否应该被忽略
    
    Args:
        path: 相对路径
        basename: 文件或目录名
        ignore_patterns: 忽略模式列表
        is_dir: 是否为目录
    
    Returns:
        True 如果应该被忽略
    """
    from fnmatch import fnmatch
    
    for ignore in ignore_patterns:
        # 处理以 / 结尾的模式（专门用于目录）
        if ignore.endswith('/'):
            dir_pattern = ignore[:-1]  # 去掉末尾的 /
            if is_dir and (fnmatch(basename, dir_pattern) or fnmatch(path, dir_pattern)):
                return True
        else:
            # 普通模式匹配
            if (fnmatch(path, ignore) or 
                fnmatch(basename, ignore) or
                (is_dir and fnmatch(f"{path}/", ignore)) or
                (is_dir and fnmatch(f"{basename}/", ignore))):
                return True
    
    return False


def get_project_structure(directory: str, ignore_patterns: List[str]) -> str:
    """Generate a string representing the project structure."""
    lines = []
    
    for root, dirs, files in os.walk(directory, topdown=True):
        rel_root = os.path.relpath(root, directory)
        if rel_root == '.':
            rel_root = ''
        
        # 过滤目录 - 使用新的忽略逻辑
        filtered_dirs = []
        for d in dirs:
            dir_path = os.path.join(rel_root, d) if rel_root else d
            if not _should_ignore_path(dir_path, d, ignore_patterns, is_dir=True):
                filtered_dirs.append(d)
        dirs[:] = filtered_dirs
        
        # 过滤文件 - 使用新的忽略逻辑
        filtered_files = []
        for f in files:
            file_path = os.path.join(rel_root, f) if rel_root else f
            if not _should_ignore_path(file_path, f, ignore_patterns, is_dir=False):
                filtered_files.append(f)

        # 添加当前目录到输出（如果不是根目录）
        if rel_root:
            level = rel_root.count(os.sep)
            indent = "    " * level
            lines.append(f"{indent}├── {os.path.basename(root)}/")
        else:
            level = -1
            lines.append(f"{os.path.basename(directory)}/")

        # 添加文件到输出
        sub_indent = "    " * (level + 1)
        for f in sorted(filtered_files):
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