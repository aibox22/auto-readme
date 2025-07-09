import os
import json
from pathlib import Path
from typing import Dict, Union, Optional
from rich.console import Console
from rich.panel import Panel

# Define the global config path
CONFIG_DIR = Path.home() / ".readmex"
CONFIG_FILE = CONFIG_DIR / "config.json"

# Initialize console for rich printing
console = Console()

# Global cache for the loaded config
_config_cache: Optional[Dict[str, str]] = None
_config_sources: Optional[Dict[str, str]] = None



def load_config() -> Dict[str, str]:
    """
    Load configuration from a global config file and override with environment variables.
    Keys from the config file are normalized to lowercase for internal consistency.
    """
    global _config_cache, _config_sources
    if _config_cache is not None:
        return _config_cache

    config = {}
    sources = {}
    # First, try to load from the global config file
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, 'r') as f:
            try:
                file_config = json.load(f)
                # Normalize keys to lowercase
                config = {k.lower(): v for k, v in file_config.items()}
                for key in config:
                    sources[key] = str(CONFIG_FILE)
            except json.JSONDecodeError as e:
                console.print(Panel(f"[bold red]Error parsing config file:[/] {CONFIG_FILE}\n[bold]Reason:[/] {e}", 
                                    title="[bold yellow]Configuration Error[/bold yellow]", expand=False, border_style="red"))
                exit()
            except AttributeError:
                # Handle cases where the file content is not a dictionary
                pass

    # Define mapping from ENV var name (uppercase) to internal config key (lowercase)
    env_map = {
        "LLM_API_KEY": "llm_api_key",
        "LLM_BASE_URL": "llm_base_url",
        "LLM_MODEL_NAME": "llm_model_name",
        "T2I_API_KEY": "t2i_api_key",
        "T2I_BASE_URL": "t2i_base_url",
        "T2I_MODEL_NAME": "t2i_model_name",
        "EMBEDDING_API_KEY": "embedding_api_key",
        "EMBEDDING_BASE_URL": "embedding_base_url",
        "EMBEDDING_MODEL_NAME": "embedding_model_name",
        "LOCAL_EMBEDDING": "local_embedding",
        "GITHUB_USERNAME": "github_username",
        "TWITTER_HANDLE": "twitter_handle",
        "LINKEDIN_USERNAME": "linkedin_username",
        "EMAIL": "email",
    }

    # Load from environment, overriding file config if an env var is set
    for env_var, config_key in env_map.items():
        env_value = os.getenv(env_var)
        if env_value is not None:
            config[config_key] = env_value
            sources[config_key] = f"Environment Variable ({env_var})"
    
    # Set defaults for personal info if not provided
    personal_info_keys = ["github_username", "twitter_handle", "linkedin_username", "email"]
    for key in personal_info_keys:
        if key not in config:
            config[key] = ""
    
    # Set defaults for embedding config if not provided
    embedding_defaults = {
        "embedding_model_name": "text-embedding-3-small",
        "embedding_base_url": "https://api.openai.com/v1",
        "embedding_api_key": "",
        "local_embedding": "true"
    }
    for key, default_value in embedding_defaults.items():
        if key not in config:
            config[key] = default_value

    _config_cache = config
    _config_sources = sources
    return _config_cache

def validate_config():
    """Validate that required configurations are present and provide detailed guidance if not."""
    config = load_config()
    required_keys = ["llm_api_key", "t2i_api_key"]
    missing_keys = [key for key in required_keys if not config.get(key)]

    if missing_keys:
        console.print(Panel("[bold yellow]Missing required API keys. Let's set them up.[/bold yellow]", title="Configuration Required", expand=False))
        
        # Interactive input for missing keys
        for key in missing_keys:
            config[key] = console.input(f"Please enter your [bold cyan]{key}[/bold cyan]: ").strip()

        # Save to config file
        CONFIG_DIR.mkdir(exist_ok=True)
        
        # Load existing config to update it, not overwrite
        try:
            with open(CONFIG_FILE, 'r') as f_read:
                existing_config = json.load(f_read)
        except (FileNotFoundError, json.JSONDecodeError):
            # Create a complete config template with all possible keys
            existing_config = {
                "LLM_API_KEY": "",
                "LLM_BASE_URL": "https://api.openai.com/v1",
                "LLM_MODEL_NAME": "gpt-3.5-turbo",
                "T2I_API_KEY": "",
                "T2I_BASE_URL": "https://api.openai.com/v1",
                "T2I_MODEL_NAME": "dall-e-3",
                "EMBEDDING_API_KEY": "",
                "EMBEDDING_BASE_URL": "https://api.openai.com/v1",
                "EMBEDDING_MODEL_NAME": "text-embedding-3-small",
                "LOCAL_EMBEDDING": "true",
                "GITHUB_USERNAME": "",
                "TWITTER_HANDLE": "",
                "LINKEDIN_USERNAME": "",
                "EMAIL": ""
            }
        
        # Update with user input
        existing_config.update({k.upper(): v for k, v in config.items() if v}) # Save keys in uppercase
        
        with open(CONFIG_FILE, 'w') as f:
            json.dump(existing_config, f, indent=2)
        
        console.print(f"[green]✔ Configuration saved to [bold cyan]{CONFIG_FILE}[/bold cyan][/green]")
        
        # Reload config to ensure it's up-to-date
        global _config_cache
        _config_cache = None
        load_config()


def get_config_sources() -> Dict[str, str]:
    """Returns the sources of the configuration values."""
    global _config_sources
    if _config_sources is None:
        load_config()
    return _config_sources


def get_llm_config() -> Dict[str, Union[str, int, float]]:
    config = load_config()
    return {
        "model_name": config.get("llm_model_name", "gpt-3.5-turbo"),
        "base_url": config.get("llm_base_url", "https://api.openai.com/v1"),
        "api_key": config.get("llm_api_key"),
        "max_tokens": int(config.get("llm_max_tokens", 1024)),
        "temperature": float(config.get("llm_temperature", 0.7)),
    }


def get_t2i_config() -> Dict[str, Union[str, int, float]]:
    config = load_config()
    return {
        "model_name": config.get("t2i_model_name", "dall-e-3"),
        "base_url": config.get("t2i_base_url", "https://api.openai.com/v1"),
        "api_key": config.get("t2i_api_key"),
        "size": config.get("t2i_image_size", "1024x1024"),
        "quality": config.get("t2i_image_quality", "standard"),
    }


def get_embedding_config() -> Dict[str, Union[str, bool]]:
    """获取embedding模型配置"""
    config = load_config()
    return {
        "model_name": config.get("embedding_model_name", "text-embedding-3-small"),
        "base_url": config.get("embedding_base_url", "https://api.openai.com/v1"),
        "api_key": config.get("embedding_api_key"),
        "local_embedding": config.get("local_embedding", "true").lower() == "true",
    }


# Keep original default configurations for use by other modules
DEFAULT_IGNORE_PATTERNS = [
    ".git",
    ".github",
    ".cursor",
    ".cursorrules",
    ".vscode",
    "__pycache__",
    "*.pyc",
    "*.md",
    "website/*",
    ".DS_Store",
    "build",
    "dist",
    "*.egg-info",
    ".venv",
    "venv",
    "__init__.py",      # 根目录下的 __init__.py
    "*/__init__.py",    # 一级子目录下的 __init__.py
    "*/*/__init__.py",  # 二级子目录下的 __init__.py
    ".idea",
    "*output*"
]

# Patterns for script files to be described by the LLM
SCRIPT_PATTERNS = ["*.py", "*.sh"]
DOCUMENT_PATTERNS = ["*.md", "*.txt"]


def get_readme_template_path():
    """Gets the path to the BLANK_README.md template."""
    from importlib import resources
    import os
    
    try:
        # 尝试使用 importlib.resources (Python 3.9+)
        template_files = resources.files('readmex.templates')
        if template_files is not None:
            template_path = template_files.joinpath('BLANK_README.md')
            if template_path.is_file():
                return str(template_path)
    except (AttributeError, FileNotFoundError, TypeError):
        pass
    
    # 备用方案：使用相对路径
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        template_path = os.path.join(current_dir, 'templates', 'BLANK_README.md')
        if os.path.exists(template_path):
            return template_path
    except Exception:
        pass
    
    # 最后的备用方案：使用 pkg_resources (如果可用)
    try:
        import pkg_resources
        return pkg_resources.resource_filename('readmex.templates', 'BLANK_README.md')
    except (ImportError, FileNotFoundError):
        pass
    
    raise FileNotFoundError("BLANK_README.md not found in package templates.")


if __name__ == "__main__":
    # Test configuration loading
    validate_config()
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
        print("Configuration validation passed")
    except SystemExit:
        # The validate_config function calls exit(), so we catch it to allow the script to continue
        # In a real run, the program would terminate here.
        pass
    except ValueError as e:
        print(f"Configuration validation failed: {e}")