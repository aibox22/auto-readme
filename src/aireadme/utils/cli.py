import argparse
import os
from rich.console import Console
from rich.table import Table
from aireadme.core import aireadme
from aireadme.config import validate_config, get_config_sources

def main():
    """
    aireadme command line entry point
    Support both command line arguments and interactive interface
    """
    parser = argparse.ArgumentParser(
        description="aireadme - AI-driven README documentation generator",
        epilog="Examples:\n  aireadme                    # Interactive mode\n  aireadme .                  # Generate for current directory\n  aireadme ./my-project       # Generate for specific directory",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "project_path",
        nargs="?",
        help="Path of project for generating README (default: interactive input)"
    )
    parser.add_argument(
        "--version", 
        action="version", 
        version="aireadme 0.1.8"
    )
    
    args = parser.parse_args()

    try:
        validate_config()
        console = Console()
        
        # Determine project path
        if args.project_path:
            project_path = os.path.abspath(args.project_path)
            if not os.path.isdir(project_path):
                console.print(f"[bold red]Error: Project path '{project_path}' is not a valid directory.[/bold red]")
                return
        else:
            console.print("[bold cyan]aireadme - AI README Generator[/bold cyan]")
            console.print("Please provide the path of project for generating README (press Enter to use the current directory).\n")
            project_input = console.input("[cyan]Project Path[/cyan]: ").strip()
            project_path = os.path.abspath(project_input) if project_input else os.getcwd()
            
            if not os.path.isdir(project_path):
                console.print(f"[bold red]Error: Project path '{project_path}' is not a valid directory.[/bold red]")
                return

        generator = aireadme()
        generator.generate(project_path)
    except KeyboardInterrupt:
        console = Console()
        console.print("\n[yellow]Operation cancelled[/yellow]")
    except FileNotFoundError as e:
        console = Console()
        console.print(f"[red]Error: {e}[/red]")
    except Exception as e:
        console = Console()
        console.print(f"[bold red]An error occurred: {e}[/bold red]")
        
        # Show configuration information to help with debugging
        from aireadme.config import load_config
        try:
            config = load_config()
            sources = get_config_sources()
            if config and sources:
                # Show configuration source info once
                console.print("\n[yellow]Configuration loaded from:[/yellow]")
                source_files = set(sources.values())
                for source_file in source_files:
                    if "Environment Variable" not in source_file:
                        console.print(f"[yellow]  • {source_file}[/yellow]")
                
                # Show configuration table with actual values
                table = Table(title="[bold cyan]Current Configuration[/bold cyan]")
                table.add_column("Variable", style="cyan")
                table.add_column("Value", style="green")
                
                # Only show non-sensitive configuration values
                display_keys = ["llm_model_name", "t2i_model_name", "llm_base_url", "t2i_base_url", 
                               "github_username", "twitter_handle", "linkedin_username", "email"]
                
                for key in display_keys:
                    if key in config and config[key]:
                        value = config[key]
                        # Mask API keys for security
                        if "api_key" in key.lower():
                            value = "***" + value[-4:] if len(value) > 4 else "***"
                        table.add_row(key, value)
                
                console.print(table)
        except Exception:
            pass  # Don't show config info if there's an error loading it