import os
import json
from pathlib import Path
from typing import Dict, Union, Optional
from rich.console import Console
from rich.panel import Panel

# Define the global config path
CONFIG_DIR = Path.home() / ".aireadme"
CONFIG_FILE = CONFIG_DIR / "config.json"

# Initialize console for rich printing
console = Console()

# Global cache for the loaded config
_config_cache: Optional[Dict[str, str]] = None


def load_config() -> Dict[str, str]:
    """Load configuration from environment variables or a global config file."""
    config = {}
    config_file_path = os.path.expanduser("~/.aireadme/config.json")

    # First, try to load from the global config file
    if os.path.exists(config_file_path):
        with open(config_file_path, 'r') as f:
            try:
                file_config = json.load(f)
                config.update(file_config)
            except json.JSONDecodeError:
                # Handle empty or invalid JSON file
                pass

    # Then, override with any environment variables
    config["llm_api_key"] = os.getenv("LLM_API_KEY", config.get("llm_api_key"))
    config["llm_base_url"] = os.getenv("LLM_BASE_URL", config.get("llm_base_url"))
    config["llm_model_name"] = os.getenv("LLM_MODEL_NAME", config.get("llm_model_name"))
    config["t2i_api_key"] = os.getenv("T2I_API_KEY", config.get("t2i_api_key"))
    config["t2i_base_url"] = os.getenv("T2I_BASE_URL", config.get("t2i_base_url"))
    config["t2i_model_name"] = os.getenv("T2I_MODEL_NAME", config.get("t2i_model_name"))

    # Load personal info, defaulting to what's in the config file or empty strings
    config["github_username"] = os.getenv("GITHUB_USERNAME", config.get("github_username", ""))
    config["twitter_handle"] = os.getenv("TWITTER_HANDLE", config.get("twitter_handle", ""))
    config["linkedin_username"] = os.getenv("LINKEDIN_USERNAME", config.get("linkedin_username", ""))
    config["email"] = os.getenv("EMAIL", config.get("email", ""))

    return config

def validate_config():
    """Validate that required configurations are present."""
    config = load_config()
    required_vars = {
        "LLM_API_KEY": "Your Large Language Model API key",
        "T2I_API_KEY": "Your Text-to-Image Model API key",
    }
    missing_vars = []
    for var, desc in required_vars.items():
        if var not in config:
            missing_vars.append((var, desc))

    if missing_vars:
        CONFIG_DIR.mkdir(exist_ok=True) # Ensure the directory exists for the example
        message = "[bold red]Missing Required Configuration[/bold red]\n\n"
        message += "Please set the following environment variables, or create a config file at `~/.aireadme/config.json`.\n\n"
        for var, desc in missing_vars:
            message += f"- [bold cyan]{var}[/bold cyan]: {desc}\n"
        message += "\n[bold]Option 1: Set Environment Variables[/bold]\n"
        message += "[green]export LLM_API_KEY='your_llm_api_key'\nexport T2I_API_KEY='your_t2i_api_key'[/green]\n\n"
        message += "[bold]Option 2: Create JSON Config File[/bold] (~/.aireadme/config.json)\n"
        message += f"[green]{{\n  \"LLM_API_KEY\": \"your_llm_api_key\",\n  \"T2I_API_KEY\": \"your_t2i_api_key\"\n}}[/green]"

        console.print(Panel(message, title="Configuration Error", expand=False))
        exit()


def get_llm_config() -> Dict[str, Union[str, int, float]]:
    config = load_config()
    return {
        "model": config.get("LLM_MODEL_NAME", "gpt-3.5-turbo"),
        "base_url": config.get("LLM_BASE_URL", "https://api.openai.com/v1"),
        "api_key": config.get("LLM_API_KEY"),
        "max_tokens": int(config.get("LLM_MAX_TOKENS", 1024)),
        "temperature": float(config.get("LLM_TEMPERATURE", 0.7)),
    }


def get_t2i_config() -> Dict[str, Union[str, int, float]]:
    config = load_config()
    return {
        "model": config.get("T2I_MODEL_NAME", "dall-e-3"),
        "base_url": config.get("T2I_BASE_URL", "https://api.openai.com/v1"),
        "api_key": config.get("T2I_API_KEY"),
        "size": config.get("T2I_IMAGE_SIZE", "1024x1024"),
        "quality": config.get("T2I_IMAGE_QUALITY", "standard"),
    }


def validate_config():
    """
    Validate if configuration is complete
    """
    llm_config = get_llm_config()
    t2i_config = get_t2i_config()
    
    if not llm_config["api_key"]:
        raise ValueError("LLM_API_KEY environment variable not set")
    
    if not t2i_config["api_key"]:
        raise ValueError("T2I_API_KEY environment variable not set")
    
    print("Configuration validation passed")
    return True


# Keep original default configurations for use by other modules
DEFAULT_IGNORE_PATTERNS = [
    ".git",
    ".vscode",
    "__pycache__",
    "*.pyc",
    ".DS_Store",
    "build",
    "dist",
    "*.egg-info",
    ".venv",
    "venv",
    "__init__.py",      # 根目录下的 __init__.py
    "*/__init__.py",    # 一级子目录下的 __init__.py
    "*/*/__init__.py",  # 二级子目录下的 __init__.py
    ".idea"
]

# Patterns for script files to be described by the LLM
SCRIPT_PATTERNS = ["*.py", "*.sh"]
DOCUMENT_PATTERNS = ["*.md", "*.txt"]


def get_readme_template_path():
    """Gets the path to the BLANK_README.md template."""
    from importlib import resources
    try:
        with resources.path('aireadme', 'BLANK_README.md') as p:
            return str(p)
    except FileNotFoundError:
        raise FileNotFoundError("BLANK_README.md not found in package.")


if __name__ == "__main__":
    # Test configuration loading
    print("=== LLM Configuration ===")
    llm_config = get_llm_config()
    for key, value in llm_config.items():
        print(f"{key}: {value}")
    
    print("\n=== Text-to-Image Configuration ===")
    t2i_config = get_t2i_config()
    for key, value in t2i_config.items():
        print(f"{key}: {value}")
    
    print("\n=== Configuration Validation ===")
    try:
        validate_config()
    except ValueError as e:
        print(f"Configuration validation failed: {e}")