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
from aireadme.config import validate_config


def main():
    """Main function to run the README generation process via interactive CLI."""
    validate_config()
    console = Console()
    console.print("[bold cyan]aireadme - AI README Generator[/bold cyan]")
    console.print("Please provide the project path (press Enter to use the current directory).\n")
    project_path = console.input("[cyan]Project Path[/cyan]: ").strip() or os.getcwd()

    if not os.path.isdir(project_path):
        console.print(f"[bold red]Error: Project path '{project_path}' is not a valid directory.[/bold red]")
        return

    generator = aireadme()
    generator.generate(project_path)


class aireadme:
    def __init__(self):
        self.model_client = ModelClient(quality="hd", image_size="1024x1024")
        self.console = Console()
        self.config = {}

    def generate(self, project_path: str, output_path: str = None):
        """Generate a README for the given project path."""
        self.project_dir = project_path
        if output_path is None:
            self.output_dir = os.path.join(self.project_dir, "aireadme_output")
        else:
            self.output_dir = output_path
        
        os.makedirs(self.output_dir, exist_ok=True)
        self.console.print(f"[green]✔ Project path set to: {self.project_dir}[/green]")
        self.console.print(f"[green]✔ Output will be saved to: {self.output_dir}[/green]")

        self._get_user_info()
        self._get_git_info()
        self._get_project_meta_info()

        self.console.print("[bold green]Generating README...[/bold green]")

        structure = self._generate_project_structure()
        dependencies = self._generate_project_dependencies()
        descriptions = self._generate_script_descriptions()
        logo_path = generate_logo(
            self.output_dir, descriptions, self.model_client, self.console
        )

        readme_content = self._generate_readme_content(
            structure, dependencies, descriptions, logo_path
        )

        # Save README.md to output directory
        readme_path = os.path.join(self.output_dir, "README.md")
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(readme_content)

        self.console.print(
            f"[bold green]✔ README.md generated at: {readme_path}[/bold green]"
        )
        if logo_path:
            self.console.print(f"[bold green]✔ Logo generated at: {logo_path}[/bold green]")
        
        # Display all generated files
        self.console.print(f"\n[bold cyan]📁 Generated Files List:[/bold cyan]")
        self.console.print(f"   📄 README.md")
        self.console.print(f"   📋 project_structure.txt")
        self.console.print(f"   📦 requirements.txt") 
        self.console.print(f"   📊 dependencies_analysis.txt")
        self.console.print(f"   📝 script_descriptions.json")
        if logo_path:
            self.console.print(f"   🎨 images/logo.png")
        
        self.console.print(
            f"\n[bold green]✔ All files saved to output directory: {self.output_dir}[/bold green]"
        )

    def _get_project_meta_info(self):
        """Interactive input for project metadata."""
        self.console.print()
        self.console.print("[bold cyan]Project Information[/bold cyan]")
        self.console.print("Please provide some details about your project (press Enter to skip):\n")
        self.config["project_description"] = self.console.input(
            "[cyan]Project Description[/cyan] (A brief summary of what this project does): "
        ).strip()
        self.config["entry_file"] = self.console.input(
            "[cyan]Entry File[/cyan] (The main file to run the project, e.g., main.py, app.js): "
        ).strip()
        self.config["key_features"] = self.console.input(
            "[cyan]Key Features[/cyan] (Main features or capabilities, separated by commas): "
        ).strip()
        self.config["additional_info"] = self.console.input(
            "[cyan]Additional Info[/cyan] (Any other important notes about the project): "
        ).strip()
        self.console.print("\n[green]✔ Project information collected![/green]")

    def _get_git_info(self):
        self.console.print("Gathering Git information...")
        try:
            git_config_path = os.path.join(self.project_dir, ".git", "config")
            if os.path.exists(git_config_path):
                with open(git_config_path, "r") as f:
                    config_content = f.read()
                url_match = re.search(
                    r"url =.*github.com[:/](.*?)/(.*?).git", config_content
                )
                if url_match:
                    self.config["github_username"] = url_match.group(1)
                    self.config["repo_name"] = url_match.group(2)
                    self.console.print("[green]✔ Git information gathered.[/green]")
                    self.console.print(f"[green]✔ GitHub Username: {self.config['github_username']}[/green]")
                    self.console.print(f"[green]✔ Repository Name: {self.config['repo_name']}[/green]")
                    return
        except Exception as e:
            self.console.print(f"[yellow]Could not read .git/config: {e}[/yellow]")

        self.console.print(
            "[yellow]Git info not found, please enter manually (or press Enter to use defaults):[/yellow]"
        )
        if not self.config.get("github_username"):
            self.config["github_username"] = self.console.input("[cyan]GitHub Username (default: your-username): [/cyan]") or "your-username"
        if not self.config.get("repo_name"):
            self.config["repo_name"] = self.console.input("[cyan]Repository Name (default: your-repo): [/cyan]") or "your-repo"

    def _get_user_info(self):
        """Interactive input for user's personal information."""
        # Load existing global config as defaults
        global_config = load_config()

        self.console.print()
        self.console.print("[bold cyan]Personal Information[/bold cyan]")
        self.console.print("Please provide your personal details (press Enter to use defaults from config or skip):\n")

        self.config["github_username"] = self.console.input(
            f"[cyan]GitHub Username[/cyan] (default: {global_config.get('github_username', '')}): "
        ).strip() or global_config.get('github_username', '')

        self.config["twitter_handle"] = self.console.input(
            f"[cyan]Twitter Handle[/cyan] (default: {global_config.get('twitter_handle', '')}): "
        ).strip() or global_config.get('twitter_handle', '')

        self.config["linkedin_username"] = self.console.input(
            f"[cyan]LinkedIn Username[/cyan] (default: {global_config.get('linkedin_username', '')}): "
        ).strip() or global_config.get('linkedin_username', '')

        self.config["email"] = self.console.input(
            f"[cyan]Email[/cyan] (default: {global_config.get('email', '')}): "
        ).strip() or global_config.get('email', '')

        self.console.print("\n[green]✔ Personal information collected![/green]")

    def _create_readme_content(self, file_tree, file_contents):
        self.console.print("Generating README content...")
        try:
            template_path = get_readme_template_path()
            with open(template_path, "r") as f:
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
        # Simple cleaning, remove ```readme``` and ```markdown```
        readme = readme.replace("```readme", "").replace("```markdown", "").strip("```")
        return readme
