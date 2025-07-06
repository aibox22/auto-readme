import os
import re
from typing import Set, List
from rich.console import Console
from readmex.utils.file_handler import find_files, load_gitignore_patterns
from readmex.config import DEFAULT_IGNORE_PATTERNS
from readmex.utils.model_client import ModelClient


class DependencyAnalyzer:
    """Project dependency analyzer class"""
    
    def __init__(self, project_dir: str, model_client=None, console=None):
        """
        Initialize dependency analyzer
        
        Args:
            project_dir: Project root directory path
            model_client: Model client for generating requirements.txt
            console: Rich console object for output
        """
        self.project_dir = project_dir
        self.model_client = model_client
        self.console = console or Console()
    
    def analyze_project_dependencies(self, output_dir: str = None) -> str:
        """
        Analyze project dependencies and generate requirements.txt
        
        Args:
            output_dir: Output directory, saves files if provided
            
        Returns:
            Generated requirements.txt content
        """
        self.console.print("Generating project dependencies...")

        # Check if existing requirements.txt exists
        existing_requirements_path = os.path.join(self.project_dir, "requirements.txt")
        existing_dependencies = ""
        if os.path.exists(existing_requirements_path):
            with open(existing_requirements_path, "r", encoding="utf-8") as f:
                existing_dependencies = f.read()
            self.console.print("[yellow]Found existing requirements.txt[/yellow]")

        # Scan all Python files to extract import statements
        gitignore_patterns = load_gitignore_patterns(self.project_dir)
        ignore_patterns = DEFAULT_IGNORE_PATTERNS + gitignore_patterns
        py_files = list(find_files(self.project_dir, ["*.py"], ignore_patterns))

        all_imports = set()

        if py_files:
            self.console.print(f"Scanning {len(py_files)} Python files for imports...")

            for py_file in py_files:
                try:
                    with open(py_file, "r", encoding="utf-8") as f:
                        content = f.read()

                    # Extract import statements
                    import_lines = self._extract_imports(content)
                    all_imports.update(import_lines)

                except Exception as e:
                    self.console.print(
                        f"[yellow]Warning: Could not read {py_file}: {e}[/yellow]"
                    )

            if all_imports:
                self.console.print(f"Found {len(all_imports)} unique import statements")

                # Use LLM to generate requirements.txt
                imports_text = "\n".join(sorted(all_imports))
                prompt = f"""Based on the following import statements from a Python project, generate a requirements.txt file with appropriate package versions.

Import statements found:
{imports_text}

Existing requirements.txt (if any):
{existing_dependencies}

Please generate a complete requirements.txt file that includes:
1. Only external packages (not built-in Python modules)
2. Reasonable version specifications (use >= for flexibility)
3. Common packages with their typical versions
4. Merge with existing requirements if provided

Return only the requirements.txt content, one package per line in format: package>=version
"""
                self.console.print("Generating requirements.txt...")
                generated_requirements = self.model_client.get_answer(prompt)

                # Clean the generated content
                generated_requirements = self._clean_requirements_content(
                    generated_requirements
                )

            else:
                generated_requirements = "# No external imports found\n"
                if existing_dependencies:
                    generated_requirements = existing_dependencies
        else:
            generated_requirements = "# No Python files found\n"
            if existing_dependencies:
                generated_requirements = existing_dependencies

        # Save generated requirements.txt to output folder
        if output_dir:
            self._save_requirements_files(
                output_dir, generated_requirements, existing_dependencies, all_imports
            )

        self.console.print("[green]✔ Project dependencies generated.[/green]")
        return generated_requirements

    def _extract_imports(self, content: str) -> Set[str]:
        """
        Extract import statements from Python code
        
        Args:
            content: Python file content
            
        Returns:
            Set of extracted import statements
        """
        imports = set()
        lines = content.split("\n")

        for line in lines:
            line = line.strip()

            # Skip comment lines
            if line.startswith("#") or not line:
                continue

            # Match import xxx format
            import_match = re.match(
                r"^import\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)", line
            )
            if import_match:
                imports.add(f"import {import_match.group(1)}")
                continue

            # Match from xxx import yyy format
            from_import_match = re.match(
                r"^from\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)\s+import\s+(.+)",
                line,
            )
            if from_import_match:
                module = from_import_match.group(1)
                imports.add(f"from {module} import {from_import_match.group(2)}")
                continue

        return imports

    def _clean_requirements_content(self, content: str) -> str:
        """
        Clean generated requirements.txt content
        
        Args:
            content: Raw generated content
            
        Returns:
            Cleaned requirements.txt content
        """
        lines = content.split("\n")
        cleaned_lines = []

        for line in lines:
            line = line.strip()

            # Skip empty lines and obvious non-requirements format lines
            if not line or line.startswith("```") or line.startswith("Based on"):
                continue

            # If line contains package name and version info, keep it
            if (
                "==" in line
                or ">=" in line
                or "<=" in line
                or "~=" in line
                or line.startswith("#")
            ):
                cleaned_lines.append(line)
            elif re.match(r"^[a-zA-Z0-9_-]+$", line):
                # If only package name, add default version
                cleaned_lines.append(f"{line}>=1.0.0")

        return "\n".join(cleaned_lines)

    def _save_requirements_files(
        self, 
        output_dir: str, 
        generated_requirements: str, 
        existing_dependencies: str, 
        all_imports: Set[str]
    ) -> None:
        """
        Save requirements.txt and dependency analysis files
        
        Args:
            output_dir: Output directory
            generated_requirements: Generated requirements.txt content
            existing_dependencies: Existing dependency content
            all_imports: All discovered import statements
        """
        # Save requirements.txt
        output_requirements_path = os.path.join(output_dir, "requirements.txt")
        with open(output_requirements_path, "w", encoding="utf-8") as f:
            f.write(generated_requirements)
        self.console.print(
            f"[green]✔ Generated requirements.txt saved to: {output_requirements_path}[/green]"
        )

        # Save dependency analysis information
        dependencies_info = f"""# Dependencies Analysis Report

## Existing requirements.txt:
{existing_dependencies if existing_dependencies else "None found"}

## Discovered imports ({len(all_imports)} unique):
{chr(10).join(sorted(all_imports)) if all_imports else "No imports found"}

## Generated requirements.txt:
{generated_requirements}
"""
        dependencies_analysis_path = os.path.join(
            output_dir, "dependencies_analysis.txt"
        )
        with open(dependencies_analysis_path, "w", encoding="utf-8") as f:
            f.write(dependencies_info)
        self.console.print(
            f"[green]✔ Dependencies analysis saved to: {dependencies_analysis_path}[/green]"
        )

    def get_project_imports(self) -> Set[str]:
        """
        Get all import statements in the project
        
        Returns:
            Set of all import statements
        """
        gitignore_patterns = load_gitignore_patterns(self.project_dir)
        ignore_patterns = DEFAULT_IGNORE_PATTERNS + gitignore_patterns
        py_files = list(find_files(self.project_dir, ["*.py"], ignore_patterns))

        all_imports = set()

        for py_file in py_files:
            try:
                with open(py_file, "r", encoding="utf-8") as f:
                    content = f.read()
                import_lines = self._extract_imports(content)
                all_imports.update(import_lines)
            except Exception:
                continue

        return all_imports

    def get_existing_requirements(self) -> str:
        """
        Get existing requirements.txt content
        
        Returns:
            Existing requirements.txt content, or empty string if not found
        """
        existing_requirements_path = os.path.join(self.project_dir, "requirements.txt")
        if os.path.exists(existing_requirements_path):
            with open(existing_requirements_path, "r", encoding="utf-8") as f:
                return f.read()
        return "" 
    
if __name__ == "__main__":
    from pathlib import Path
    output_dir = Path(__file__).parent.parent.parent.parent / "readmex_output"
    model_client = ModelClient()
    analyzer = DependencyAnalyzer(project_dir=".", model_client=model_client, console=None)
    analyzer.analyze_project_dependencies(output_dir=output_dir)