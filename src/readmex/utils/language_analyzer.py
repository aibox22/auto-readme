import os
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Any, Optional
import fnmatch


class LanguageAnalyzer:
    """Project Language Analyzer - Detect programming language distribution in projects"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize language analyzer
        
        Args:
            config_path: Language mapping config file path, if None use default path
        """
        self.language_mapping = self._load_language_mapping(config_path)
        self.extension_to_language = self._build_extension_mapping()
        
        # Load ignore patterns
        self.ignore_dirs, self.ignore_files = self._load_ignore_patterns()
    
    def _load_language_mapping(self, config_path: Optional[str] = None) -> Dict[str, List[str]]:
        """Load language mapping config"""
        if config_path is None:
            # Use default path
            current_dir = Path(__file__).parent.parent
            config_path = current_dir / "config" / "language_mapping.json"
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Warning: Language mapping config file {config_path} not found, using default config")
            return self._get_default_mapping()
        except json.JSONDecodeError as e:
            print(f"Warning: Language mapping config file format error: {e}, using default config")
            return self._get_default_mapping()
    
    def _get_default_mapping(self) -> Dict[str, List[str]]:
        """Get default language mapping"""
        return {
            "Python": [".py", ".pyx", ".pyi", ".pyw"],
            "JavaScript": [".js", ".jsx", ".mjs"],
            "TypeScript": [".ts", ".tsx"],
            "Java": [".java", ".class", ".jar"],
            "C": [".c"],
            "C++": [".cpp", ".cc", ".cxx", ".hpp", ".hxx", ".h++"],
            "C/C++": [".h"],
            "Go": [".go"],
            "Rust": [".rs"],
            "PHP": [".php", ".phtml"],
            "Ruby": [".rb", ".erb", ".rake"],
            "HTML": [".html", ".htm"],
            "CSS": [".css"],
            "JSON": [".json"],
            "Markdown": [".md", ".markdown"],
            "Text": [".txt"],
            "Shell": [".sh", ".bash", ".zsh", ".fish"],
            "SQL": [".sql"],
            "YAML": [".yaml", ".yml"],
            "XML": [".xml"]
        }
    
    def _build_extension_mapping(self) -> Dict[str, str]:
        """Build extension to language mapping"""
        extension_map = {}
        for language, extensions in self.language_mapping.items():
            for ext in extensions:
                # Handle special filenames (e.g. Dockerfile, Makefile)
                if not ext.startswith('.'):
                    extension_map[ext] = language
                else:
                    extension_map[ext.lower()] = language
        return extension_map
    
    def _load_ignore_patterns(self) -> tuple[set, set]:
        """Load ignore patterns config"""
        # Use default path
        current_dir = Path(__file__).parent.parent
        config_path = current_dir / "config" / "ignore_patterns.json"
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                ignore_dirs = set(config.get('ignore_dirs', []))
                ignore_files = set(config.get('ignore_files', []))
                return ignore_dirs, ignore_files
        except FileNotFoundError:
            print(f"Warning: Ignore patterns config file {config_path} not found, using default config")
            return self._get_default_ignore_patterns()
        except json.JSONDecodeError as e:
            print(f"Warning: Ignore patterns config file format error: {e}, using default config")
            return self._get_default_ignore_patterns()
    
    def _get_default_ignore_patterns(self) -> tuple[set, set]:
        """Get default ignore patterns"""
        ignore_dirs = {
            '.git', '__pycache__', 'node_modules', '.venv', 'venv',
            'env', '.pytest_cache', '.idea', '.vscode', 'build',
            'dist', 'target', 'bin', 'obj', '.DS_Store', '.mypy_cache',
            'coverage', '.coverage', 'htmlcov', '.tox', '.eggs',
            '*.egg-info', '*.egg', '.pytest_cache', '.cache',
            '.next', '.nuxt', 'out', '.output', '.vercel'
        }
        
        ignore_files = {
            '.DS_Store', '.gitignore', '.gitattributes', '.editorconfig',
            'Thumbs.db', 'desktop.ini', '.env', '.env.local', '.env.production'
        }
        
        return ignore_dirs, ignore_files
    
    def analyze_project(self, project_path: str) -> Dict[str, Any]:
        """
        Analyze language distribution in the project
        
        Args:
            project_path: Project path
            
        Returns:
            Dictionary containing language analysis results
        """
        project_path = Path(project_path)
        if not project_path.exists():
            raise FileNotFoundError(f"Project path does not exist: {project_path}")
        
        language_stats = defaultdict(lambda: {'files': 0, 'lines': 0, 'bytes': 0})
        
        # Traverse all files in the project
        for file_path in project_path.rglob('*'):
            if file_path.is_file():
                # Check if the file should be ignored
                if self._should_ignore(file_path):
                    continue
                
                # Determine language type
                language = self._get_language(file_path)
                
                if language:
                    # Count file info
                    try:
                        file_size = file_path.stat().st_size
                        line_count = self._count_lines(file_path)
                        
                        language_stats[language]['files'] += 1
                        language_stats[language]['lines'] += line_count
                        language_stats[language]['bytes'] += file_size
                        
                    except (OSError, UnicodeDecodeError):
                        # Skip unreadable files
                        continue
        
        return self._calculate_percentages(language_stats)
    
    def _should_ignore(self, file_path: Path) -> bool:
        """Check if the file or directory should be ignored"""
        # Check directory names
        for part in file_path.parts:
            if part in self.ignore_dirs:
                return True
            # Check wildcard patterns
            for pattern in self.ignore_dirs:
                if '*' in pattern and fnmatch.fnmatch(part, pattern):
                    return True
        
        # Check file names
        if file_path.name in self.ignore_files:
            return True
        
        return False
    
    def _get_language(self, file_path: Path) -> Optional[str]:
        """Determine language type by file extension and content"""
        # Check special filenames (e.g. Dockerfile, Makefile)
        if file_path.name in self.extension_to_language:
            return self.extension_to_language[file_path.name]
        
        # Check file extension
        extension = file_path.suffix.lower()
        if extension in self.extension_to_language:
            return self.extension_to_language[extension]
        
        # Check shebang line for script language
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                first_line = f.readline().strip()
                if first_line.startswith('#!'):
                    return self._detect_shebang_language(first_line)
        except:
            pass
        
        return None
    
    def _detect_shebang_language(self, shebang_line: str) -> str:
        """Detect language by shebang line"""
        shebang = shebang_line.lower()
        
        if 'python' in shebang:
            return 'Python'
        elif 'bash' in shebang or 'sh' in shebang:
            return 'Shell'
        elif 'node' in shebang:
            return 'JavaScript'
        elif 'ruby' in shebang:
            return 'Ruby'
        elif 'perl' in shebang:
            return 'Perl'
        elif 'php' in shebang:
            return 'PHP'
        
        return 'Shell'  # Default to Shell
    
    def _count_lines(self, file_path: Path) -> int:
        """Count file lines"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return sum(1 for _ in f)
        except:
            return 0
    
    def _calculate_percentages(self, language_stats: Dict) -> Dict[str, Any]:
        """Calculate percentages for each language"""
        total_files = sum(stats['files'] for stats in language_stats.values())
        total_lines = sum(stats['lines'] for stats in language_stats.values())
        total_bytes = sum(stats['bytes'] for stats in language_stats.values())
        
        results = []
        for language, stats in language_stats.items():
            if total_files > 0:
                file_percentage = (stats['files'] / total_files) * 100
            else:
                file_percentage = 0
                
            if total_lines > 0:
                line_percentage = (stats['lines'] / total_lines) * 100
            else:
                line_percentage = 0
                
            if total_bytes > 0:
                byte_percentage = (stats['bytes'] / total_bytes) * 100
            else:
                byte_percentage = 0
            
            results.append({
                'language': language,
                'files': stats['files'],
                'lines': stats['lines'],
                'bytes': stats['bytes'],
                'file_percentage': round(file_percentage, 2),
                'line_percentage': round(line_percentage, 2),
                'byte_percentage': round(byte_percentage, 2)
            })
        
        # Sort by lines of code
        results.sort(key=lambda x: x['lines'], reverse=True)
        
        return {
            'summary': {
                'total_files': total_files,
                'total_lines': total_lines,
                'total_bytes': total_bytes,
                'total_languages': len(results)
            },
            'languages': results
        }
    
    def get_primary_language(self, project_path: str) -> Optional[str]:
        """
        Get the primary programming language of the project
        
        Args:
            project_path: Project path
            
        Returns:
            Primary programming language name, or None if not found
        """
        results = self.analyze_project(project_path)
        if results['languages']:
            return results['languages'][0]['language']
        return None
    
    def get_language_summary(self, project_path: str) -> str:
        """
        Get a text summary of the project's language distribution
        
        Args:
            project_path: Project path
            
        Returns:
            Language distribution summary text
        """
        results = self.analyze_project(project_path)
        
        if not results['languages']:
            return "No programming language files detected."
        
        summary_lines = []
        summary_lines.append(f"Project contains {results['summary']['total_languages']} programming languages")
        summary_lines.append(f"Total files: {results['summary']['total_files']}")
        summary_lines.append(f"Total lines of code: {results['summary']['total_lines']}")
        
        # Show top 3 main languages
        top_languages = results['languages'][:3]
        summary_lines.append("\nMain languages:")
        for lang in top_languages:
            summary_lines.append(
                f"  {lang['language']}: {lang['line_percentage']:.1f}% "
                f"({lang['lines']} lines, {lang['files']} files)"
            )
        
        return "\n".join(summary_lines)
    
    def save_analysis_result(self, project_path: str, output_path: str) -> None:
        """
        Save language analysis result to file
        
        Args:
            project_path: Project path
            output_path: Output file path
        """
        results = self.analyze_project(project_path)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)


def analyze_project_languages(project_path: str, config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Convenience function: analyze project language distribution
    
    Args:
        project_path: Project path
        config_path: Language mapping config file path
        
    Returns:
        Language analysis result
    """
    analyzer = LanguageAnalyzer(config_path)
    return analyzer.analyze_project(project_path)

if __name__ == "__main__":
    """Test when running this script directly"""
    import sys
    from pathlib import Path
    
    # Get the project root directory as the test path
    current_dir = Path(__file__).parent.parent.parent
    
    print("🔍 Language Analyzer Test")
    print("=" * 50)
    print(f"Test project path: {current_dir}")
    print()
    
    try:
        # Create analyzer instance
        analyzer = LanguageAnalyzer()
        
        # Analyze project
        print("Analyzing project...")
        results = analyzer.analyze_project(str(current_dir))
        
        # Show results
        print("\n📊 Analysis Result:")
        print(f"  Total files: {results['summary']['total_files']}")
        print(f"  Total languages: {results['summary']['total_languages']}")
        print(f"  Total lines of code: {results['summary']['total_lines']}")
        print(f"  Total file size: {results['summary']['total_bytes']} bytes")
        
        if results['languages']:
            print("\n📈 Language Distribution:")
            print("-" * 60)
            print(f"{'Language':<15} {'Files':<8} {'Lines':<10} {'File %':<10} {'Line %':<10}")
            print("-" * 60)
            
            for lang in results['languages'][:10]:  # Show top 10 languages
                print(f"{lang['language']:<15} {lang['files']:<8} {lang['lines']:<10} "
                      f"{lang['file_percentage']:<10.1f}% {lang['line_percentage']:<10.1f}%")
            
            print("-" * 60)
            
            # Get primary language
            primary_lang = analyzer.get_primary_language(str(current_dir))
            print(f"\n🏆 Primary Language: {primary_lang}")
            
            # Get language summary
            summary = analyzer.get_language_summary(str(current_dir))
            print(f"\n📋 Language Summary:\n{summary}")
            
        else:
            print("\n⚠️  No programming language files detected.")
        
        print("\n✅ Test completed!")
        
    except FileNotFoundError as e:
        print(f"❌ Error: Project path does not exist - {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
