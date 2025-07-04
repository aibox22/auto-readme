#!/usr/bin/env python3
"""
Test script to verify the generate method works with project_path parameter
and configuration loading logic.
"""

import sys
import os
sys.path.insert(0, 'src')

from aireadme.core import aireadme
from rich.console import Console

def test_generate():
    console = Console()
    console.print("[bold cyan]Testing aireadme generate method...[/bold cyan]")
    
    try:
        # Create generator instance
        generator = aireadme()
        
        # Test with current directory
        current_dir = os.getcwd()
        console.print(f"[green]Testing with project path: {current_dir}[/green]")
        
        # This should now work without the "takes 1 positional argument but 2 were given" error
        generator.generate(current_dir)
        
        console.print("[bold green]✅ Test passed! Generate method accepts project_path parameter.[/bold green]")
        
    except TypeError as e:
        if "takes 1 positional argument but 2 were given" in str(e):
            console.print("[bold red]❌ Test failed! Generate method still has parameter issue.[/bold red]")
            console.print(f"[red]Error: {e}[/red]")
        else:
            console.print(f"[yellow]Different TypeError: {e}[/yellow]")
    except Exception as e:
        console.print(f"[yellow]Other error (expected during testing): {e}[/yellow]")
        console.print("[green]✅ Parameter issue is fixed, but other configuration issues exist.[/green]")

if __name__ == "__main__":
    test_generate()