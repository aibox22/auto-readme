#!/usr/bin/env python3
"""
Test script to verify fixed image generation functionality
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from rich.console import Console
from aireadme.utils.model_client import ModelClient

def test_image_generation():
    """Test the fixed image generation functionality"""
    console = Console()
    
    console.print("[bold cyan]=== Testing Fixed Image Generation ===[/bold cyan]")
    
    try:
        # Create model client
        client = ModelClient()
        
        # Display current settings
        console.print("\n[yellow]Current Settings:[/yellow]")
        settings = client.get_current_settings()
        for key, value in settings.items():
            console.print(f"  {key}: {value}")
        
        # Test image generation with a simple prompt
        console.print("\n[yellow]Testing image generation...[/yellow]")
        prompt = "A simple geometric logo with blue and white colors"
        
        console.print(f"[cyan]Prompt: {prompt}[/cyan]")
        
        # Generate image
        result = client.get_image(prompt)
        
        if result and "url" in result:
            console.print("[bold green]✓ Image generation successful![/bold green]")
            console.print(f"[green]Image URL: {result['url']}[/green]")
            if result.get('content'):
                console.print(f"[green]Content size: {len(result['content'])} bytes[/green]")
            else:
                console.print("[yellow]⚠️  Image URL generated but content download failed[/yellow]")
        else:
            console.print("[red]✗ Image generation failed[/red]")
            
    except Exception as e:
        console.print(f"[red]✗ Test failed with error: {e}[/red]")
        
        # Check if it's the specific model parameter error
        if "InvalidParameter" in str(e) and "model" in str(e):
            console.print("\n[yellow]This appears to be a model parameter issue.[/yellow]")
            console.print("[yellow]The fix should have resolved this. Please check:[/yellow]")
            console.print("1. Model name compatibility with your API provider")
            console.print("2. API endpoint configuration")
            console.print("3. API key validity")
        
        return False
    
    return True

if __name__ == "__main__":
    success = test_image_generation()
    if success:
        print("\n🎉 Image generation test completed successfully!")
    else:
        print("\n❌ Image generation test failed.")