#!/usr/bin/env python3
"""
Test script to check T2I configuration and model compatibility
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from rich.console import Console
from autoreadme.config import load_config, get_t2i_config
from autoreadme.utils.model_client import ModelClient

def test_t2i_config():
    """Test T2I configuration and model compatibility"""
    console = Console()
    
    console.print("[bold cyan]=== T2I Configuration Check ===[/bold cyan]")
    
    # Load and display configuration
    config = load_config()
    t2i_config = get_t2i_config()
    
    console.print("\n[yellow]Current T2I Configuration:[/yellow]")
    for key, value in t2i_config.items():
        if "api_key" in key:
            masked_value = "***" + value[-4:] if value and len(value) > 4 else "***"
            console.print(f"  {key}: {masked_value}")
        else:
            console.print(f"  {key}: {value}")
    
    # Check model compatibility
    model_name = t2i_config.get("model_name", "dall-e-3")
    base_url = t2i_config.get("base_url", "https://api.openai.com/v1")
    
    console.print(f"\n[yellow]Model Analysis:[/yellow]")
    console.print(f"  Model Name: {model_name}")
    console.print(f"  Base URL: {base_url}")
    
    # Check if using custom API endpoint
    if "openai.com" not in base_url:
        console.print(f"\n[yellow]⚠️  Using custom API endpoint: {base_url}[/yellow]")
        console.print("[yellow]Common model compatibility issues:[/yellow]")
        console.print("  • Some providers may not support 'dall-e-3' model name")
        console.print("  • Try alternative model names like:")
        console.print("    - 'dall-e'")
        console.print("    - 'text-to-image'")
        console.print("    - 'stable-diffusion'")
        console.print("    - Check your provider's documentation for supported models")
    
    # Test model client initialization
    console.print("\n[yellow]Testing ModelClient initialization:[/yellow]")
    try:
        client = ModelClient()
        console.print("[green]✓ ModelClient initialized successfully[/green]")
        
        # Display current settings
        settings = client.get_current_settings()
        console.print("\n[yellow]ModelClient Settings:[/yellow]")
        for key, value in settings.items():
            console.print(f"  {key}: {value}")
            
    except Exception as e:
        console.print(f"[red]✗ ModelClient initialization failed: {e}[/red]")
    
    # Suggest fixes
    console.print("\n[bold yellow]=== Suggested Fixes ===[/bold yellow]")
    console.print("1. Check if your API provider supports the model name 'dall-e-3'")
    console.print("2. Try updating T2I_MODEL_NAME in your configuration:")
    console.print("   - For OpenAI-compatible APIs: try 'dall-e' or 'dall-e-2'")
    console.print("   - For other providers: check their documentation")
    console.print("3. Verify your API endpoint URL is correct")
    console.print("4. Test with a simple model name like 'text-to-image'")

if __name__ == "__main__":
    test_t2i_config()