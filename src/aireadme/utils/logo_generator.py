import os
from rich.console import Console
from aireadme.utils.model_client import ModelClient

def generate_logo(project_dir, descriptions, model_client, console):
    """
    Generate project logo image based on project description
    
    Args:
        project_dir: Project directory path
        descriptions: Project description information
        model_client: Model client instance
        console: Console output object
        
    Returns:
        str: Generated logo image path, returns None if failed
    """
    console.print("Generating project logo...")
    try:
        # Create images directory
        images_dir = os.path.join(project_dir, "images")
        os.makedirs(images_dir, exist_ok=True)
        png_path = os.path.join(images_dir, "logo.png")

        # Step 1: Generate logo description prompt based on project description
        description_prompt = f"""Based on the following project information, generate a professional logo design description:

**Project Information**:
{descriptions}

Please generate a concise, professional logo design description with the following requirements:
1. A flat, minimalist vector icon with rectangular outline and rounded corners
2. Contains geometric shapes that reflect the project's core functionality
3. Uses smooth gradient colors giving it a modern, tech-inspired look
4. Clean, simple and modern design, suitable as a project logo
6. Describe in English, within 50 words

Return only the logo design description focusing on geometric elements and color scheme, no other explanations.
"""
        
        # Get logo description
        try:
            logo_description = model_client.get_answer(description_prompt)
        except Exception as e:
            console.print(f"[red]Failed to get logo description: {e}[/red]")
            return None

        # Step 2: Generate image using logo description
        image_prompt = f"{logo_description} Don't include any text in the image."
        console.print(f"[cyan]Image Prompt: {image_prompt}[/cyan]")
        console.print(f"[cyan]Generating image...[/cyan]")
        
        # Call text-to-image API to generate logo with high quality settings
        console.print(f"[cyan]Using high-quality image generation (quality: hd, size: 1024x1024)[/cyan]")
        try:
            image_result = model_client.get_image(image_prompt)
        except Exception as e:
            console.print(f"[red]Image generation failed: {e}[/red]")
            return None
        
        if not image_result or not image_result.get("content"):
            console.print("[red]Image content is empty, generation failed[/red]")
            return None
        
        # Save image file
        with open(png_path, 'wb') as f:
            f.write(image_result["content"])
        
        console.print(f"[green]✔ Logo image saved to {png_path}[/green]")
        console.print(f"[green]✔ Image URL: {image_result['url']}[/green]")
        
        return png_path
            
    except Exception as e:
        console.print(f"[red]Logo generation failed: {e}[/red]")
        return None