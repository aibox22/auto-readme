import os
import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from rich.console import Console
from rich.progress import Progress
from rich.table import Table
from aireadme.utils.model_client import ModelClient
from aireadme.utils.file_handler import (
    find_files,
    get_project_structure,
    load_gitignore_patterns,
)
from aireadme.utils.logo_generator import generate_logo
from aireadme.config import load_config
from .config import DEFAULT_IGNORE_PATTERNS, SCRIPT_PATTERNS, DOCUMENT_PATTERNS, get_readme_template_path

class aireadme:
    def __init__(self, project_dir=None):
        self.model_client = ModelClient(quality="hd", image_size="1024x1024")  # 确保使用高质量、高分辨率图像生成
        self.console = Console()
        self.project_dir = project_dir  # 初始化时设置项目目录
        self.output_dir = None  # 输出目录将在 _get_basic_info 中设置
        self.config = {
            "github_username": "",
            "repo_name": "",
            "twitter_handle": "",
            "linkedin_username": "",
            "email": "",
            "project_description": "",
            "entry_file": "",
            "key_features": "",
            "additional_info": "",
        }

    def generate(self, project_path=None):
        """Generate README for the project."""
        self.console.print("[bold green]🚀 Starting AI README generation...[/bold green]")
        
        # Set project directory if provided
        if project_path:
            self.project_dir = project_path
        
        # Load configuration: environment variables > config file > user input
        self._load_configuration()
        
        # Get basic project information if not already set
        if not self.project_dir or not self.output_dir:
            self._get_basic_info()
        
        # Collect information
        self._get_git_info()
        self._get_user_info()
        self._get_project_meta_info()
        
        # Analyze project
        structure = self._get_project_structure()
        dependencies = self._get_project_dependencies()
        descriptions = self._get_script_descriptions()
        
        # Auto-generate project description if empty
        if not self.config["project_description"]:
            self.config["project_description"] = self._generate_project_description(structure, dependencies, descriptions)
        
        # Auto-generate entry file if empty
        if not self.config["entry_file"]:
            self.config["entry_file"] = self._generate_entry_file(structure, dependencies, descriptions)
        
        # Auto-generate key features if empty
        if not self.config["key_features"]:
            self.config["key_features"] = self._generate_key_features(structure, dependencies, descriptions)
        
        # Auto-generate additional info if empty
        if not self.config["additional_info"]:
            self.config["additional_info"] = self._generate_additional_info(structure, dependencies, descriptions)
        
        # Generate README
        
        # Generate logo
        from aireadme.utils.logo_generator import generate_logo
        logo_path = generate_logo(self.output_dir, descriptions, self.model_client, self.console)
        
        # Generate README content
        readme_content = self._generate_readme_content(structure, dependencies, descriptions, logo_path)
        
        # Save README
        readme_path = os.path.join(self.output_dir, "README.md")
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(readme_content)
            
        self.console.print(f"[bold green]✅ README generated successfully at {readme_path}[/bold green]")

    def _load_configuration(self):
        """Load configuration from environment variables, config file, or user input."""
        from aireadme.config import load_config, validate_config, CONFIG_FILE
        
        try:
            # First, validate and load existing configuration
            validate_config()
            config = load_config()
            
            # Update self.config with loaded values
            for key, value in config.items():
                if key in self.config and value:
                    self.config[key] = value
            
            # Set output directory if project_dir is available
            if self.project_dir:
                self.output_dir = os.path.join(self.project_dir, "aireadme_output")
                os.makedirs(self.output_dir, exist_ok=True)
                self.console.print(f"[green]✔ Configuration loaded from {CONFIG_FILE}[/green]")
                self.console.print(f"[green]✔ Output directory: {self.output_dir}[/green]")
            
        except Exception as e:
            self.console.print(f"[yellow]Warning: Could not load configuration: {e}[/yellow]")
            self.console.print("[yellow]Will proceed with interactive configuration...[/yellow]")

    def _get_basic_info(self):
        """
        Interactive input for basic information: project path and output directory
        """
        self.console.print("[bold cyan]aireadme - AI README Generator[/bold cyan]")
        self.console.print("Please configure basic information (press Enter to use default values)\n")

        # Get project path
        current_dir = os.getcwd()
        project_input = self.console.input(
            f"[cyan]Project Path[/cyan] (default: {current_dir}): "
        ).strip()

        if project_input:
            # Handle relative and absolute paths
            if os.path.isabs(project_input):
                self.project_dir = project_input
            else:
                self.project_dir = os.path.join(current_dir, project_input)
        else:
            self.project_dir = current_dir

        # Check if project path exists
        if not os.path.exists(self.project_dir):
            self.console.print(f"[red]Error: Project path '{self.project_dir}' does not exist[/red]")
            exit(1)

        self.console.print(f"[green]✔ Project path: {self.project_dir}[/green]")

        # Get output directory
        output_input = self.console.input(
            f"[cyan]Output Directory[/cyan] (default: {current_dir}): "
        ).strip()

        if output_input:
            # Handle relative and absolute paths
            if os.path.isabs(output_input):
                output_base = output_input
            else:
                output_base = os.path.join(current_dir, output_input)
        else:
            output_base = current_dir

        # Create aireadme_output subdirectory under output directory
        self.output_dir = os.path.join(output_base, "aireadme_output")

        # Create output directory
        try:
            os.makedirs(self.output_dir, exist_ok=True)
            self.console.print(f"[green]✔ Output directory: {self.output_dir}[/green]")
        except Exception as e:
            self.console.print(
                f"[red]Error: Cannot create output directory '{self.output_dir}': {e}[/red]"
            )
            exit(1)

        self.console.print()  # Empty line separator

        # Get additional project information
        self.console.print("[bold cyan]Additional Project Information[/bold cyan]")
        self.console.print("Please provide additional information about your project (press Enter to skip):\n")

        # Project description
        user_description = self.console.input(
            "[cyan]Project Description[/cyan] (brief summary of what this project does, press Enter to auto-generate): "
        ).strip()
        
        if user_description:
            self.config["project_description"] = user_description
        else:
            self.console.print("[yellow]No description provided, will auto-generate based on project analysis...[/yellow]")
            self.config["project_description"] = ""  # Will be generated later

        # Entry file
        user_entry_file = self.console.input(
            "[cyan]Entry File[/cyan] (main file to run the project, press Enter to auto-detect): "
        ).strip()
        
        if user_entry_file:
            self.config["entry_file"] = user_entry_file
        else:
            self.console.print("[yellow]No entry file specified, will auto-detect based on project analysis...[/yellow]")
            self.config["entry_file"] = ""  # Will be generated later

        # Features
        user_features = self.console.input(
            "[cyan]Key Features[/cyan] (main features or capabilities, press Enter to auto-generate): "
        ).strip()
        
        if user_features:
            self.config["key_features"] = user_features
        else:
            self.console.print("[yellow]No features specified, will auto-generate based on project analysis...[/yellow]")
            self.config["key_features"] = ""  # Will be generated later

        # Additional information
        user_additional_info = self.console.input(
            "[cyan]Additional Info[/cyan] (any other important information, press Enter to auto-generate): "
        ).strip()
        
        if user_additional_info:
            self.config["additional_info"] = user_additional_info
        else:
            self.console.print("[yellow]No additional info specified, will auto-generate based on project analysis...[/yellow]")
            self.config["additional_info"] = ""  # Will be generated later

        self.console.print("\n[green]✔ Project information collected![/green]")
        self.console.print()  # Empty line separator

    def _get_project_meta_info(self):
        self.console.print(
            "Please provide additional project information (or press Enter to use defaults):"
        )
        user_description = self.console.input(
            "[cyan]Project Description (press Enter to auto-generate): [/cyan]"
        ).strip()
        
        if user_description:
            self.config["project_description"] = user_description
        else:
            self.console.print("[yellow]No description provided, will auto-generate based on project analysis...[/yellow]")
            self.config["project_description"] = ""  # Will be generated later
        user_entry_file = self.console.input(
            "[cyan]Entry File (press Enter to auto-detect): [/cyan]"
        ).strip()
        
        if user_entry_file:
            self.config["entry_file"] = user_entry_file
        else:
            self.console.print("[yellow]No entry file specified, will auto-detect based on project analysis...[/yellow]")
            self.config["entry_file"] = ""  # Will be generated later
            
        user_features = self.console.input(
            "[cyan]Key Features (press Enter to auto-generate): [/cyan]"
        ).strip()
        
        if user_features:
            self.config["key_features"] = user_features
        else:
            self.console.print("[yellow]No features specified, will auto-generate based on project analysis...[/yellow]")
            self.config["key_features"] = ""  # Will be generated later
            
        user_additional_info = self.console.input(
            "[cyan]Additional Information (press Enter to auto-generate): [/cyan]"
        ).strip()
        
        if user_additional_info:
            self.config["additional_info"] = user_additional_info
        else:
            self.console.print("[yellow]No additional info specified, will auto-generate based on project analysis...[/yellow]")
            self.config["additional_info"] = ""  # Will be generated later

    def _get_git_info(self):
        self.console.print("Gathering Git information...")
        
        # Check if GitHub username is already configured
        if self.config.get("github_username") and self.config["github_username"] != "":
            self.console.print(f"[green]✔ GitHub Username (from config): {self.config['github_username']}[/green]")
            git_username_configured = True
        else:
            git_username_configured = False
            
        # Try to get repo info from git remote first (more reliable)
        repo_name_from_git = None
        try:
            # Use git remote get-url origin command
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                remote_url = result.stdout.strip()
                self.console.print(f"[cyan]Found git remote: {remote_url}[/cyan]")
                
                # Parse GitHub URL (supports both HTTPS and SSH)
                github_match = re.search(
                    r"github\.com[:/]([^/]+)/([^/\.]+)(?:\.git)?/?$", remote_url
                )
                
                if github_match:
                    if not git_username_configured:
                        self.config["github_username"] = github_match.group(1)
                        self.console.print(f"[green]✔ GitHub Username (auto-detected): {self.config['github_username']}[/green]")
                        git_username_configured = True
                    repo_name_from_git = github_match.group(2)
                    self.config["repo_name"] = repo_name_from_git
                    self.console.print(f"[green]✔ Repository Name (auto-detected): {self.config['repo_name']}[/green]")
                    return
                else:
                    self.console.print(f"[yellow]Remote URL is not a GitHub repository: {remote_url}[/yellow]")
            else:
                self.console.print(f"[yellow]Could not get git remote: {result.stderr.strip()}[/yellow]")
                
        except subprocess.TimeoutExpired:
            self.console.print("[yellow]Git command timed out[/yellow]")
        except FileNotFoundError:
            self.console.print("[yellow]Git command not found[/yellow]")
        except Exception as e:
            self.console.print(f"[yellow]Could not get git remote: {e}[/yellow]")
        
        # Fallback: Try to get repo name from .git/config
        if not git_username_configured or not repo_name_from_git:
            try:
                git_config_path = os.path.join(self.project_dir, ".git", "config")
                if os.path.exists(git_config_path):
                    with open(git_config_path, "r") as f:
                        config_content = f.read()
                    url_match = re.search(
                        r"url =.*github.com[:/](.*?)/(.*?)\.git", config_content
                    )
                    if url_match:
                        if not git_username_configured:
                            self.config["github_username"] = url_match.group(1)
                            self.console.print(f"[green]✔ GitHub Username (from .git/config): {self.config['github_username']}[/green]")
                            git_username_configured = True
                        if not repo_name_from_git:
                            repo_name_from_git = url_match.group(2)
                            self.config["repo_name"] = repo_name_from_git
                            self.console.print(f"[green]✔ Repository Name (from .git/config): {self.config['repo_name']}[/green]")
                            return
            except Exception as e:
                self.console.print(f"[yellow]Could not read .git/config: {e}[/yellow]")

        # Only ask for missing information
        if not git_username_configured:
            self.console.print("[yellow]GitHub username not found, please enter manually:[/yellow]")
            self.config["github_username"] = self.console.input("[cyan]GitHub Username (default: your-username): [/cyan]") or "your-username"
        
        if not repo_name_from_git:
            self.console.print("[yellow]Repository name not found, please enter manually:[/yellow]")
            self.config["repo_name"] = self.console.input("[cyan]Repository Name (default: your-repo): [/cyan]") or "your-repo"

    def _get_user_info(self):
        # Check which contact information is already configured
        configured_info = []
        missing_info = []
        
        contact_fields = [
            ("twitter_handle", "Twitter Handle", "@your_handle"),
            ("linkedin_username", "LinkedIn Username", "your-username"),
            ("email", "Email", "your.email@example.com")
        ]
        
        for field_key, field_name, default_value in contact_fields:
            if self.config.get(field_key) and self.config[field_key] != "" and self.config[field_key] != default_value:
                configured_info.append((field_key, field_name, self.config[field_key]))
            else:
                missing_info.append((field_key, field_name, default_value))
        
        # Show already configured information
        if configured_info:
            self.console.print("[green]✔ Contact information (from config):[/green]")
            for field_key, field_name, value in configured_info:
                self.console.print(f"[green]  {field_name}: {value}[/green]")
        
        # Only ask for missing information
        if missing_info:
            self.console.print("Please enter missing contact information (or press Enter to use defaults):")
            for field_key, field_name, default_value in missing_info:
                self.config[field_key] = self.console.input(f"[cyan]{field_name} (default: {default_value}): [/cyan]") or default_value

    def _get_project_structure(self):
        self.console.print("Generating project structure...")
        ignore_patterns = load_gitignore_patterns(self.project_dir)
        structure = get_project_structure(self.project_dir, ignore_patterns)
        structure_path = os.path.join(self.output_dir, "project_structure.txt")
        with open(structure_path, "w", encoding="utf-8") as f:
            f.write(structure)
        self.console.print(f"[green]✔ Project structure saved to: {structure_path}[/green]")
        return structure

    def _get_project_dependencies(self):
        self.console.print("Generating project dependencies...")
        
        # First check if requirements.txt already exists
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
                    self.console.print(f"[yellow]Warning: Could not read {py_file}: {e}[/yellow]")
            
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
                generated_requirements = self._clean_requirements_content(generated_requirements)
                
            else:
                generated_requirements = "# No external imports found\n"
                if existing_dependencies:
                    generated_requirements = existing_dependencies
        else:
            generated_requirements = "# No Python files found\n"
            if existing_dependencies:
                generated_requirements = existing_dependencies
        
        # Save generated requirements.txt to output folder
        if self.output_dir:
            output_requirements_path = os.path.join(self.output_dir, "requirements.txt")
            with open(output_requirements_path, "w", encoding="utf-8") as f:
                f.write(generated_requirements)
            self.console.print(f"[green]✔ Generated requirements.txt saved to: {output_requirements_path}[/green]")
            
            # Also save dependency analysis information
            dependencies_info = f"""# Dependencies Analysis Report

## Existing requirements.txt:
{existing_dependencies if existing_dependencies else "None found"}

## Discovered imports ({len(all_imports)} unique):
{chr(10).join(sorted(all_imports)) if all_imports else "No imports found"}

## Generated requirements.txt:
{generated_requirements}
"""
            dependencies_analysis_path = os.path.join(self.output_dir, "dependencies_analysis.txt")
            with open(dependencies_analysis_path, "w", encoding="utf-8") as f:
                f.write(dependencies_info)
            self.console.print(f"[green]✔ Dependencies analysis saved to: {dependencies_analysis_path}[/green]")
        
        self.console.print("[green]✔ Project dependencies generated.[/green]")
        return generated_requirements
    
    def _extract_imports(self, content):
        """Extract import statements from Python code"""
        import re
        
        imports = set()
        lines = content.split('\n')
        
        for line in lines:
            line = line.strip()
            
            # Skip comment lines
            if line.startswith('#') or not line:
                continue
            
            # Match import xxx format
            import_match = re.match(r'^import\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)', line)
            if import_match:
                imports.add(f"import {import_match.group(1)}")
                continue
            
            # Match from xxx import yyy format
            from_import_match = re.match(r'^from\s+([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)\s+import\s+(.+)', line)
            if from_import_match:
                module = from_import_match.group(1)
                imports.add(f"from {module} import {from_import_match.group(2)}")
                continue
        
        return imports
    
    def _clean_requirements_content(self, content):
        """Clean generated requirements.txt content"""
        lines = content.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            
            # Skip empty lines and obvious non-requirements format lines
            if not line or line.startswith('```') or line.startswith('Based on'):
                continue
                
            # If line contains package name and version info, keep it
            if '==' in line or '>=' in line or '<=' in line or '~=' in line or line.startswith('#'):
                cleaned_lines.append(line)
            elif re.match(r'^[a-zA-Z0-9_-]+$', line):
                # If only package name, add default version
                cleaned_lines.append(f"{line}>=1.0.0")
        
        return '\n'.join(cleaned_lines)

    def _get_script_descriptions(self, max_workers=5):
        """ 
        Generate script descriptions using multithreading
        
        Args:
            max_workers (int): Maximum number of threads, default is 3
        """
        self.console.print("Generating script and document descriptions...")
        from aireadme.config import SCRIPT_PATTERNS, DOCUMENT_PATTERNS, DEFAULT_IGNORE_PATTERNS
        gitignore_patterns = load_gitignore_patterns(self.project_dir)
        ignore_patterns = DEFAULT_IGNORE_PATTERNS + gitignore_patterns
        # 将脚本模式和文档模式合并，以便生成更全面的文件描述
        all_patterns = SCRIPT_PATTERNS + DOCUMENT_PATTERNS
        filepaths = list(find_files(self.project_dir, all_patterns, ignore_patterns))

        if not filepaths:
            self.console.print("[yellow]No script or document files found to process.[/yellow]")
            return json.dumps({}, indent=2)

        table = Table(title="Files to be processed")
        table.add_column("File Path", style="cyan")
        for filepath in filepaths:
            table.add_row(os.path.relpath(filepath, self.project_dir))
        self.console.print(table)

        descriptions = {}
        descriptions_lock = Lock()  # Thread lock to protect shared dictionary
        
        def process_file(filepath):
            """Function to process a single file"""
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                
                prompt = f"Analyze the following script and provide a concise summary. Focus on:\n1. Main purpose and functionality\n2. Key functions/methods and their roles\n3. Important features or capabilities\n\nScript content:\n{content}"
                description = self.model_client.get_answer(prompt)
                
                # Use lock to protect shared resource
                with descriptions_lock:
                    descriptions[os.path.relpath(filepath, self.project_dir)] = description
                
                return True
            except Exception as e:
                self.console.print(f"[red]Error processing {filepath}: {e}[/red]")
                return False

        # Use thread pool for concurrent processing
        with Progress() as progress:
            task = progress.add_task("[cyan]Generating...[/cyan]", total=len(filepaths))
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all tasks
                future_to_filepath = {
                    executor.submit(process_file, filepath): filepath
                    for filepath in filepaths
                }
                
                # Process completed tasks
                for future in as_completed(future_to_filepath):
                    filepath = future_to_filepath[future]
                    try:
                        success = future.result()
                        if success:
                            self.console.print(f"[dim]✓ {os.path.relpath(filepath, self.project_dir)}[/dim]")
                        progress.update(task, advance=1)
                    except Exception as e:
                        self.console.print(f"[red]Exception for {filepath}: {e}[/red]")
                        progress.update(task, advance=1)

        # Save script descriptions to output folder
        descriptions_json = json.dumps(descriptions, indent=2, ensure_ascii=False)
        if self.output_dir:
            descriptions_path = os.path.join(self.output_dir, "script_descriptions.json")
            with open(descriptions_path, "w", encoding="utf-8") as f:
                f.write(descriptions_json)
            self.console.print(f"[green]✔ Script and document descriptions saved to: {descriptions_path}[/green]")
        
        self.console.print(f"[green]✔ Script and document descriptions generated using {max_workers} threads.[/green]")
        self.console.print(f"[green]✔ Processed {len(descriptions)} files successfully.[/green]")
        return descriptions_json

    def _generate_project_description(self, structure, dependencies, descriptions):
        """
        Auto-generate project description based on project analysis
        
        Args:
            structure: Project structure string
            dependencies: Dependencies analysis string
            descriptions: File descriptions JSON string
            
        Returns:
            str: Generated project description
        """
        self.console.print("[cyan]Auto-generating project description based on project analysis...[/cyan]")
        
        try:
            prompt = f"""Based on the following project analysis, generate a concise and accurate project description (2-3 sentences maximum).

Project Structure:
```
{structure}
```

Dependencies:
```
{dependencies}
```

File Descriptions:
{descriptions}

Please analyze the project and provide:
1. What this project does (main purpose)
2. Key technologies/frameworks used
3. Primary functionality or features

Generate a brief, professional description that captures the essence of this project. Keep it under 100 words and focus on the core functionality.

Return only the description text, no additional explanations."""
            
            generated_description = self.model_client.get_answer(prompt)
            
            # Clean the generated description
            generated_description = generated_description.strip()
            if generated_description.startswith('"') and generated_description.endswith('"'):
                generated_description = generated_description[1:-1]
            
            self.console.print(f"[green]✔ Auto-generated description: {generated_description}[/green]")
            return generated_description
            
        except Exception as e:
            self.console.print(f"[red]Failed to auto-generate project description: {e}[/red]")
            return "A software project with various components and functionality."

    def _generate_entry_file(self, structure, dependencies, descriptions):
        """
        Auto-detect entry file based on project analysis
        
        Args:
            structure: Project structure string
            dependencies: Dependencies analysis string
            descriptions: File descriptions JSON string
            
        Returns:
            str: Detected entry file
        """
        self.console.print("[cyan]Auto-detecting entry file based on project analysis...[/cyan]")
        
        try:
            prompt = f"""Based on the following project analysis, identify the main entry file for this project.

Project Structure:
```
{structure}
```

Dependencies:
```
{dependencies}
```

File Descriptions:
{descriptions}

Please analyze the project and identify the main entry file that users would typically run to start the application. Look for:
1. Files with names like main.py, app.py, run.py, server.py, index.py
2. Files described as entry points or main applications
3. Files that contain main execution logic
4. Consider the dependencies to understand the project type

Return only the filename (e.g., "main.py", "app.py"), no path or additional explanations."""
            
            detected_entry = self.model_client.get_answer(prompt)
            
            # Clean the detected entry file
            detected_entry = detected_entry.strip()
            if detected_entry.startswith('"') and detected_entry.endswith('"'):
                detected_entry = detected_entry[1:-1]
            
            # Fallback to common names if detection fails
            if not detected_entry or len(detected_entry) > 50:
                detected_entry = "main.py"
            
            self.console.print(f"[green]✔ Auto-detected entry file: {detected_entry}[/green]")
            return detected_entry
            
        except Exception as e:
            self.console.print(f"[red]Failed to auto-detect entry file: {e}[/red]")
            return "main.py"

    def _generate_key_features(self, structure, dependencies, descriptions):
        """
        Auto-generate key features based on project analysis
        
        Args:
            structure: Project structure string
            dependencies: Dependencies analysis string
            descriptions: File descriptions JSON string
            
        Returns:
            str: Generated key features
        """
        self.console.print("[cyan]Auto-generating key features based on project analysis...[/cyan]")
        
        try:
            prompt = f"""Based on the following project analysis, identify 3-5 key features or capabilities of this project.

Project Structure:
```
{structure}
```

Dependencies:
```
{dependencies}
```

File Descriptions:
{descriptions}

Please analyze the project and identify the main features or capabilities. Focus on:
1. Core functionality provided by the application
2. Key technologies or frameworks used
3. Important capabilities or services offered
4. Notable features that make this project useful

Return the features as a comma-separated list (e.g., "Feature 1, Feature 2, Feature 3"). Keep each feature concise (2-4 words)."""
            
            generated_features = self.model_client.get_answer(prompt)
            
            # Clean the generated features
            generated_features = generated_features.strip()
            if generated_features.startswith('"') and generated_features.endswith('"'):
                generated_features = generated_features[1:-1]
            
            self.console.print(f"[green]✔ Auto-generated features: {generated_features}[/green]")
            return generated_features
            
        except Exception as e:
            self.console.print(f"[red]Failed to auto-generate key features: {e}[/red]")
            return "Core functionality, Easy to use, Well documented"

    def _generate_additional_info(self, structure, dependencies, descriptions):
        """
        Auto-generate additional information based on project analysis
        
        Args:
            structure: Project structure string
            dependencies: Dependencies analysis string
            descriptions: File descriptions JSON string
            
        Returns:
            str: Generated additional information
        """
        self.console.print("[cyan]Auto-generating additional information based on project analysis...[/cyan]")
        
        try:
            prompt = f"""Based on the following project analysis, generate additional important information about this project.

Project Structure:
```
{structure}
```

Dependencies:
```
{dependencies}
```

File Descriptions:
{descriptions}

Please analyze the project and provide additional useful information such as:
1. Notable technical details or architecture
2. Special requirements or prerequisites
3. Important usage notes or considerations
4. Unique aspects of the implementation

Generate 1-2 sentences of additional information that would be valuable for users. Keep it concise and informative.

Return only the additional information text, no explanations."""
            
            generated_info = self.model_client.get_answer(prompt)
            
            # Clean the generated info
            generated_info = generated_info.strip()
            if generated_info.startswith('"') and generated_info.endswith('"'):
                generated_info = generated_info[1:-1]
            
            self.console.print(f"[green]✔ Auto-generated additional info: {generated_info}[/green]")
            return generated_info
            
        except Exception as e:
            self.console.print(f"[red]Failed to auto-generate additional info: {e}[/red]")
            return ""

    def _generate_readme_content(self, structure, dependencies, descriptions, logo_path):
        self.console.print("Generating README content...")
        try:
            template_path = get_readme_template_path()
            with open(template_path, "r", encoding="utf-8") as f:
                template = f.read()
        except FileNotFoundError as e:
            self.console.print(f"[red]Error: {e}[/red]")
            return ""

        # Replace placeholders
        for key, value in self.config.items():
            if value:
                template = template.replace(f"{{{{{key}}}}}", value)
            else:
                # If value is empty, remove the line containing the placeholder
                template = re.sub(f".*{{{{{key}}}}}.*\n?", "", template)

        if self.config["github_username"] and self.config["repo_name"]:
            template = template.replace(
                "github_username/repo_name",
                f"{self.config['github_username']}/{self.config['repo_name']}",
            )
        else:
            # Remove all github-related badges and links if info is missing
            template = re.sub(
                r"\[\[(Contributors|Forks|Stargazers|Issues|project_license)-shield\]\]\[(Contributors|Forks|Stargazers|Issues|project_license)-url\]\n?",
                "",
                template,
            )

        if logo_path:
            # Logo 和 README 都在同一个输出目录中，使用相对路径
            relative_logo_path = os.path.relpath(logo_path, self.output_dir)
            template = template.replace("images/logo.png", relative_logo_path)
        else:
            template = re.sub(r'<img src="images/logo.png".*>', "", template)

        # Remove screenshot section
        template = re.sub(
            r"\[\[Product Name Screen Shot\]\[product-screenshot\]\]\(https://example.com\)",
            "",
            template,
        )
        template = re.sub(
            r"\[product-screenshot\]: images/screenshot.png", "", template
        )

        # Prepare additional project information for the prompt
        additional_info = ""
        if self.config.get("project_description"):
            additional_info += f"**Project Description:** {self.config['project_description']}\n"
        if self.config.get("entry_file"):
            additional_info += f"**Entry File:** {self.config['entry_file']}\n"
        if self.config.get("key_features"):
            additional_info += f"**Key Features:** {self.config['key_features']}\n"
        if self.config.get("additional_info"):
            additional_info += f"**Additional Information:** {self.config['additional_info']}\n"

        prompt = f"""You are a readme.md generator. You need to return the readme text directly without any other speech.
        Based on the following template, please generate a complete README.md file. 
        Fill in any missing information based on the project context provided.

        Use the additional project information provided by the user to enhance the content, especially for:
        - Project description and overview
        - Entry file information
        - Features section
        - Any additional information provided by the user

        **Template:**
        {template}

        **Project Structure:**
        ```
        {structure}
        ```

        **Dependencies:**
        ```
        {dependencies}
        ```

        **Script Descriptions:**
        {descriptions}

        **Additional Project Information:**
        {additional_info}

        Please ensure the final README is well-structured, professional, and incorporates all the user-provided information appropriately.
        """
        readme = self.model_client.get_answer(prompt)
        self.console.print("[green]✔ README content generated.[/green]")
        
        # Clean the generated content more carefully
        readme = readme.strip()
        
        # Remove markdown code block markers if present
        if readme.startswith("```"):
            lines = readme.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]  # Remove first line
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]  # Remove last line
            readme = "\n".join(lines)
        
        # Ensure the README includes reference links at the bottom
        # Check if reference links are missing and add them if needed
        if "[contributors-shield]:" not in readme and self.config.get("github_username") and self.config.get("repo_name"):
            self.console.print("[yellow]Adding missing reference links...[/yellow]")
            
            # Get the reference links from template
            try:
                template_path = get_readme_template_path()
                with open(template_path, "r", encoding="utf-8") as f:
                    template_content = f.read()
                
                # Extract reference links section from template
                ref_links_match = re.search(
                    r"<!-- MARKDOWN LINKS & IMAGES -->.*$", 
                    template_content, 
                    re.DOTALL
                )
                
                if ref_links_match:
                    ref_links = ref_links_match.group(0)
                    
                    # Replace placeholders in reference links
                    ref_links = ref_links.replace("{{github_username}}", self.config["github_username"])
                    ref_links = ref_links.replace("{{repo_name}}", self.config["repo_name"])
                    if self.config.get("linkedin_username"):
                        ref_links = ref_links.replace("{{linkedin_username}}", self.config["linkedin_username"])
                    
                    # Append reference links to README
                    if not readme.endswith("\n"):
                        readme += "\n"
                    readme += "\n" + ref_links
                    
                    self.console.print("[green]✔ Reference links added.[/green]")
                    
            except Exception as e:
                self.console.print(f"[yellow]Could not add reference links: {e}[/yellow]")
        
        return readme
