#!/usr/bin/env python3
"""
Test script to verify improved error handling and configuration display
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from rich.console import Console
from autoreadme.config import load_config, get_config_sources
from autoreadme.utils.cli import main

def test_error_handling():
    """Test the improved error handling with configuration display"""
    console = Console()
    
    try:
        # Simulate a connection error
        raise ConnectionError("Connection error")
        
    except Exception as e:
        console.print(f"[bold red]An error occurred: {e}[/bold red]")
        
        # Show configuration information to help with debugging
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
                from rich.table import Table
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
        except Exception as config_error:
            console.print(f"[red]Could not load configuration: {config_error}[/red]")

if __name__ == "__main__":
    test_error_handling()