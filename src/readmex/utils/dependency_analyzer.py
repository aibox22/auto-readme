import os
import re
import json
from typing import Set, List, Dict, Any
from pathlib import Path
from rich.console import Console
from readmex.utils.file_handler import find_files, load_gitignore_patterns
from readmex.config import DEFAULT_IGNORE_PATTERNS
from readmex.utils.model_client import ModelClient


class DependencyAnalyzer:
    """Multi-language project dependency analyzer class"""
    
    def __init__(self, project_dir: str, primary_language: str = "python", model_client=None, console=None):
        """
        Initialize dependency analyzer
        
        Args:
            project_dir: Project root directory path
            primary_language: Primary programming language of the project
            model_client: Model client for generating dependency files
            console: Rich console object for output
        """
        self.project_dir = project_dir
        self.primary_language = primary_language.lower()
        self.model_client = model_client
        self.console = console or Console()
        
        # Load dependency configuration
        self.config = self._load_dependency_config()
        
        # Validate primary language
        if self.primary_language not in self.config["languages"]:
            self.console.print(f"[yellow]Warning: Language '{self.primary_language}' not supported, falling back to default[/yellow]")
            self.primary_language = self.config["default_language"]
    
    def _load_dependency_config(self) -> Dict[str, Any]:
        """Load dependency configuration from JSON file"""
        try:
            config_path = Path(__file__).parent.parent / "config" / "dependency_config.json"
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            self.console.print("[red]Warning: dependency_config.json not found, using default Python configuration[/red]")
            return self._get_default_config()
        except json.JSONDecodeError as e:
            self.console.print(f"[red]Warning: Invalid JSON in dependency_config.json: {e}[/red]")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration for Python"""
        return {
            "languages": {
                "python": {
                    "dependency_files": ["requirements.txt"],
                    "file_extensions": ["*.py"],
                    "import_patterns": [
                        {
                            "pattern": "^import\\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\\.[a-zA-Z_][a-zA-Z0-9_]*)*)",
                            "format": "import {module}",
                            "group": 1
                        },
                        {
                            "pattern": "^from\\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\\.[a-zA-Z_][a-zA-Z0-9_]*)*)\\s+import\\s+(.+)",
                            "format": "from {module} import {items}",
                            "group": 1,
                            "items_group": 2
                        }
                    ],
                    "prompt_template": "Based on the following import statements from a Python project, generate a requirements.txt file with appropriate package versions.\n\nImport statements found:\n{imports}\n\nExisting requirements.txt (if any):\n{existing}\n\nPlease generate a complete requirements.txt file that includes:\n1. Only external packages (not built-in Python modules)\n2. Reasonable version specifications (use >= for flexibility)\n3. Common packages with their typical versions\n4. Merge with existing requirements if provided\n\nReturn only the requirements.txt content, one package per line in format: package>=version"
                }
            },
            "default_language": "python",
            "builtin_modules": {
                "python": ["os", "sys", "re", "json", "urllib", "http", "datetime", "time", "math", "random", "collections", "itertools", "functools", "operator", "pathlib", "typing", "abc", "contextlib", "copy", "pickle", "sqlite3", "csv", "configparser", "logging", "unittest", "threading", "multiprocessing", "asyncio", "socket", "email", "html", "xml", "base64", "hashlib", "hmac", "secrets", "uuid", "decimal", "fractions", "statistics", "io", "tempfile", "shutil", "glob", "fnmatch", "linecache", "fileinput"]
            }
        }

    def analyze_project_dependencies(self, output_dir: str = None) -> str:
        """
        Analyze project dependencies and generate dependency files
        
        Args:
            output_dir: Output directory, saves files if provided
            
        Returns:
            Generated dependency file content
        """
        lang_config = self.config["languages"][self.primary_language]
        self.console.print(f"Generating {self.primary_language} project dependencies...")

        # Check if existing dependency files exist
        existing_dependencies = self._get_existing_dependencies()
        if existing_dependencies:
            self.console.print(f"[yellow]Found existing dependency files[/yellow]")

        # Scan all source files to extract import statements
        gitignore_patterns = load_gitignore_patterns(self.project_dir)
        ignore_patterns = DEFAULT_IGNORE_PATTERNS + gitignore_patterns
        source_files = list(find_files(self.project_dir, lang_config["file_extensions"], ignore_patterns))

        all_imports = set()

        if source_files:
            self.console.print(f"Scanning {len(source_files)} {self.primary_language} files for imports...")

            for source_file in source_files:
                try:
                    with open(source_file, "r", encoding="utf-8") as f:
                        content = f.read()

                    # Extract import statements using language-specific patterns
                    import_lines = self._extract_imports_by_language(content)
                    all_imports.update(import_lines)

                except Exception as e:
                    self.console.print(
                        f"[yellow]Warning: Could not read {source_file}: {e}[/yellow]"
                    )

            if all_imports:
                self.console.print(f"Found {len(all_imports)} unique import statements")

                # Filter out built-in modules
                external_imports = self._filter_external_imports(all_imports)
                
                if external_imports:
                    # Use LLM to generate dependency file
                    imports_text = "\n".join(sorted(external_imports))
                    prompt = lang_config["prompt_template"].format(
                        imports=imports_text,
                        existing=existing_dependencies
                    )
                    
                    self.console.print(f"Generating {self.primary_language} dependency file...")
                    generated_dependencies = self.model_client.get_answer(prompt)

                    # Clean the generated content
                    generated_dependencies = self._clean_dependency_content(
                        generated_dependencies
                    )
                else:
                    generated_dependencies = f"# No external {self.primary_language} dependencies found\n"
                    if existing_dependencies:
                        generated_dependencies = existing_dependencies
            else:
                generated_dependencies = f"# No {self.primary_language} import statements found\n"
                if existing_dependencies:
                    generated_dependencies = existing_dependencies
        else:
            generated_dependencies = f"# No {self.primary_language} files found\n"
            if existing_dependencies:
                generated_dependencies = existing_dependencies

        # Save generated dependency files to output folder
        if output_dir:
            self._save_dependency_files(
                output_dir, generated_dependencies, existing_dependencies, all_imports
            )

        self.console.print(f"[green]✔ {self.primary_language} project dependencies generated.[/green]")
        return generated_dependencies

    def _get_existing_dependencies(self) -> str:
        """Get existing dependency file content for the current language"""
        lang_config = self.config["languages"][self.primary_language]
        existing_content = ""
        
        for dep_file in lang_config["dependency_files"]:
            dep_path = os.path.join(self.project_dir, dep_file)
            if os.path.exists(dep_path):
                try:
                    with open(dep_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        if content.strip():
                            existing_content += f"\n=== {dep_file} ===\n{content}\n"
                except Exception as e:
                    self.console.print(f"[yellow]Warning: Could not read {dep_file}: {e}[/yellow]")
        
        return existing_content.strip()

    def _extract_imports_by_language(self, content: str) -> Set[str]:
        """Extract import statements using language-specific patterns"""
        lang_config = self.config["languages"][self.primary_language]
        imports = set()
        lines = content.split("\n")

        for line in lines:
            line = line.strip()

            # Skip comment lines and empty lines
            if not line or line.startswith("#") or line.startswith("//") or line.startswith("/*"):
                continue

            # Apply language-specific patterns
            for pattern_config in lang_config["import_patterns"]:
                pattern = pattern_config["pattern"]
                match = re.match(pattern, line)
                
                if match:
                    module = match.group(pattern_config["group"])
                    
                    # Format the import statement
                    if "items_group" in pattern_config:
                        items = match.group(pattern_config["items_group"])
                        formatted = pattern_config["format"].format(module=module, items=items)
                    else:
                        formatted = pattern_config["format"].format(module=module)
                    
                    imports.add(formatted)
                    break

        return imports

    def _filter_external_imports(self, imports: Set[str]) -> Set[str]:
        """Filter out built-in modules to keep only external dependencies"""
        builtin_modules = self.config.get("builtin_modules", {}).get(self.primary_language, [])
        external_imports = set()
        
        for import_stmt in imports:
            # Extract module name from import statement
            module_name = self._extract_module_name(import_stmt)
            
            # Check if it's a built-in module
            is_builtin = False
            for builtin in builtin_modules:
                if module_name.startswith(builtin):
                    is_builtin = True
                    break
            
            # Skip relative imports and local files
            if not is_builtin and not module_name.startswith('.') and '/' not in module_name:
                external_imports.add(import_stmt)
        
        return external_imports

    def _extract_module_name(self, import_stmt: str) -> str:
        """Extract the base module name from an import statement"""
        # Handle different import formats
        if import_stmt.startswith("import "):
            module = import_stmt[7:].split()[0]
        elif import_stmt.startswith("from "):
            module = import_stmt.split(" import ")[0][5:]
        elif "require(" in import_stmt:
            # JavaScript/Node.js require
            match = re.search(r"require\(['\"]([^'\"]+)['\"]", import_stmt)
            module = match.group(1) if match else ""
        elif import_stmt.startswith("use "):
            # Rust use statement
            module = import_stmt[4:].split("::")[0]
        elif import_stmt.startswith("using "):
            # C# using statement
            module = import_stmt[6:].rstrip(";")
        else:
            module = import_stmt
        
        # Get the top-level module name
        return module.split('.')[0].split('::')[0].split('/')[0]

    def _clean_dependency_content(self, content: str) -> str:
        """Clean generated dependency file content (language-agnostic)"""
        lines = content.split("\n")
        cleaned_lines = []

        for line in lines:
            line = line.strip()

            # Skip empty lines and obvious non-dependency format lines
            if not line or line.startswith("```") or line.startswith("Based on"):
                continue

            # Keep lines that look like dependency specifications
            if any(char in line for char in ["=", ">", "<", "~", "^"]) or line.startswith("#"):
                cleaned_lines.append(line)
            elif re.match(r"^[a-zA-Z0-9_-]+$", line):
                # If only package name, keep as is (version will be handled by LLM)
                cleaned_lines.append(line)

        return "\n".join(cleaned_lines)

    def _save_dependency_files(
        self, 
        output_dir: str, 
        generated_dependencies: str, 
        existing_dependencies: str, 
        all_imports: Set[str]
    ) -> None:
        """Save dependency files and analysis information"""
        lang_config = self.config["languages"][self.primary_language]
        
        # Determine output filename based on language
        primary_dep_file = lang_config["dependency_files"][0]
        output_dep_path = os.path.join(output_dir, primary_dep_file)
        
        # Save generated dependency file
        with open(output_dep_path, "w", encoding="utf-8") as f:
            f.write(generated_dependencies)
        self.console.print(
            f"[green]✔ Generated {primary_dep_file} saved to: {output_dep_path}[/green]"
        )

        # Save dependency analysis information
        dependencies_info = f"""# {self.primary_language.title()} Dependencies Analysis Report

## Language: {self.primary_language}
## Primary dependency file: {primary_dep_file}

## Existing dependency files:
{existing_dependencies if existing_dependencies else "None found"}

## Discovered imports ({len(all_imports)} unique):
{chr(10).join(sorted(all_imports)) if all_imports else "No imports found"}

## Generated dependency file:
{generated_dependencies}
"""
        dependencies_analysis_path = os.path.join(
            output_dir, f"{self.primary_language}_dependencies_analysis.txt"
        )
        with open(dependencies_analysis_path, "w", encoding="utf-8") as f:
            f.write(dependencies_info)
        self.console.print(
            f"[green]✔ Dependencies analysis saved to: {dependencies_analysis_path}[/green]"
        )

    # Backward compatibility methods (deprecated)
    def _extract_imports(self, content: str) -> Set[str]:
        """
        Legacy method for Python import extraction (deprecated)
        Use _extract_imports_by_language instead
        """
        return self._extract_imports_by_language(content)

    def _clean_requirements_content(self, content: str) -> str:
        """
        Legacy method for cleaning requirements (deprecated)
        Use _clean_dependency_content instead
        """
        return self._clean_dependency_content(content)

    def _save_requirements_files(self, output_dir: str, generated_requirements: str, 
                                existing_dependencies: str, all_imports: Set[str]) -> None:
        """
        Legacy method for saving requirements (deprecated)
        Use _save_dependency_files instead
        """
        self._save_dependency_files(output_dir, generated_requirements, existing_dependencies, all_imports)

    def get_project_imports(self) -> Set[str]:
        """
        Get all import statements in the project for the current language
        
        Returns:
            Set of all import statements
        """
        lang_config = self.config["languages"][self.primary_language]
        gitignore_patterns = load_gitignore_patterns(self.project_dir)
        ignore_patterns = DEFAULT_IGNORE_PATTERNS + gitignore_patterns
        source_files = list(find_files(self.project_dir, lang_config["file_extensions"], ignore_patterns))

        all_imports = set()

        for source_file in source_files:
            try:
                with open(source_file, "r", encoding="utf-8") as f:
                    content = f.read()
                import_lines = self._extract_imports_by_language(content)
                all_imports.update(import_lines)
            except Exception:
                continue

        return all_imports

    def get_existing_requirements(self) -> str:
        """
        Get existing dependency file content for the current language
        
        Returns:
            Existing dependency file content, or empty string if not found
        """
        return self._get_existing_dependencies()

    def get_supported_languages(self) -> List[str]:
        """
        Get list of supported programming languages
        
        Returns:
            List of supported language names
        """
        return list(self.config["languages"].keys())

    def set_language(self, language: str) -> bool:
        """
        Change the primary language for dependency analysis
        
        Args:
            language: New primary language
            
        Returns:
            True if language was set successfully, False if not supported
        """
        language = language.lower()
        if language in self.config["languages"]:
            self.primary_language = language
            self.console.print(f"[green]Language changed to: {language}[/green]")
            return True
        else:
            self.console.print(f"[red]Language '{language}' not supported[/red]")
            return False 
    
if __name__ == "__main__":
    from pathlib import Path
    
    # Test the multi-language dependency analyzer
    output_dir = Path(__file__).parent.parent.parent.parent / "readmex_output"
    output_dir.mkdir(exist_ok=True)
    
    # Test with Python (default)
    print("Testing Python dependency analysis...")
    model_client = ModelClient()
    analyzer = DependencyAnalyzer(
        project_dir=".", 
        primary_language="python", 
        model_client=model_client, 
        console=None
    )
    
    print(f"Supported languages: {analyzer.get_supported_languages()}")
    print(f"Current language: {analyzer.primary_language}")
    
    # Test import extraction
    imports = analyzer.get_project_imports()
    print(f"Found {len(imports)} import statements")
    
    # Test dependency analysis (commented out to avoid API calls)
    # analyzer.analyze_project_dependencies(output_dir=output_dir)
    
    # Test language switching
    print("\nTesting language switching...")
    analyzer.set_language("javascript")
    analyzer.set_language("unsupported_language")
    analyzer.set_language("python")