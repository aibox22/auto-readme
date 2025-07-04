import os
from rich.console import Console
import requests
from openai import OpenAI
from typing import Optional, Dict, Union
from aireadme.config import get_llm_config, get_t2i_config, validate_config


class ModelClient:
    """Model client class for LLM Q&A and text-to-image functionality"""
    
    def __init__(self, max_tokens: int = 1000, temperature: float = 0.7, 
                 image_size: str = "1024x1024", quality: str = "hd"):
        """
        Initialize model client
        
        Args:
            max_tokens: Maximum number of tokens
            temperature: Temperature parameter
            image_size: Image size
            quality: Image quality
        """
        # Validate configuration
        validate_config()
        
        # Get configurations
        self.llm_config = get_llm_config()
        self.t2i_config = get_t2i_config()
        
        # Set parameters
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.image_size = image_size
        self.quality = quality
        
        # Initialize console
        self.console = Console()
        
        # Initialize clients
        self.llm_client = self._initialize_llm_client()
        self.t2i_client = self._initialize_t2i_client()
    
    def _initialize_llm_client(self) -> OpenAI:
        """
        Initialize LLM client
        
        Returns:
            Configured LLM OpenAI client
        """
        return OpenAI(
            base_url=self.llm_config["base_url"],
            api_key=self.llm_config["api_key"],
        )
    
    def _initialize_t2i_client(self) -> OpenAI:
        """
        Initialize text-to-image client
        
        Returns:
            Configured text-to-image OpenAI client
        """
        return OpenAI(
            base_url=self.t2i_config["base_url"],
            api_key=self.t2i_config["api_key"],
        )
    
    def get_answer(self, question: str, model: Optional[str] = None) -> str:
        """
        Get answer to question using LLM
        
        Args:
            question: User question
            model: Specify model to use, if not specified use default model from config
            
        Returns:
            LLM answer
        """
        try:
            # Use specified model or default LLM model from config
            model_name = model or self.llm_config["model_name"]
            
            response = self.llm_client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "user", "content": question}
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            self.console.print(f"[red]Error occurred while getting answer: {e}[/red]")
            raise
    
    def get_image(self, prompt: str, model: Optional[str] = None) -> Dict[str, Union[str, bytes, None]]:
        """
        Generate image using text-to-image model
        
        Args:
            prompt: Image description prompt
            model: Specify model to use, if not specified use default model from config
            
        Returns:
            Dictionary containing url and content: {"url": str, "content": bytes}
        """
        try:
            # Use specified model or default text-to-image model from config
            model_name = model or self.t2i_config["model_name"]
            
            # Generate image request parameters - start with basic params
            generate_params = {
                "model": model_name,
                "prompt": prompt,
                "n": 1
            }
            
            # Add size parameter - different providers may have different parameter names
            base_url = self.t2i_config.get("base_url", "")
            
            # For OpenAI and OpenAI-compatible APIs
            if "openai.com" in base_url or model_name.startswith("dall-e"):
                generate_params["size"] = self.image_size
                # Add quality parameter only for dall-e models
                if model_name.startswith("dall-e"):
                    generate_params["quality"] = self.quality
            else:
                # For other providers (like Doubao/ByteDance), use basic parameters
                generate_params["size"] = self.image_size
                
                # Don't add quality parameter for non-OpenAI providers
                # as it may cause "InvalidParameter" errors
            
            self.console.print(f"[cyan]Generating image with model: {model_name}[/cyan]")
            self.console.print(f"[cyan]Parameters: {generate_params}[/cyan]")
            
            response = self.t2i_client.images.generate(**generate_params)
            
            image_url = response.data[0].url
            
            # Download image content with retry mechanism
            image_content = self._download_image_with_retry(image_url, max_retries=3)
            
            self.console.print(f"[green]✓ Image URL: {image_url}[/green]")
            if image_content:
                self.console.print(f"[green]✓ Image content size: {len(image_content)} bytes[/green]")
            
            return {
                "url": image_url,
                "content": image_content
            }
            
        except Exception as e:
            self.console.print(f"[red]Error occurred while generating image: {e}[/red]")
            # Provide helpful error information
            self.console.print(f"[yellow]Model used: {model_name}[/yellow]")
            self.console.print(f"[yellow]Base URL: {self.t2i_config.get('base_url', 'Unknown')}[/yellow]")
            raise
    
    def _download_image_with_retry(self, image_url: str, max_retries: int = 3) -> Optional[bytes]:
        """
        Download image with retry mechanism
        
        Args:
            image_url: Image URL
            max_retries: Maximum retry attempts
            
        Returns:
            Image content bytes, returns None if failed
        """
        import time
        import ssl
        
        for attempt in range(max_retries):
            try:
                self.console.print(f"Downloading image (attempt {attempt + 1}/{max_retries})...")
                
                # Set request parameters with SSL tolerance
                session = requests.Session()
                session.verify = True  # Verify SSL certificate
                
                # Add User-Agent and other headers
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': 'image/*,*/*;q=0.8',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive'
                }
                
                response = session.get(
                    image_url, 
                    timeout=60,  # Increase timeout
                    headers=headers,
                    stream=True  # Stream download
                )
                response.raise_for_status()
                
                # Get image content
                image_content = response.content
                self.console.print(f"Image downloaded successfully, size: {len(image_content)} bytes")
                return image_content
                
            except (requests.exceptions.SSLError, ssl.SSLError) as ssl_error:
                self.console.print(f"SSL error (attempt {attempt + 1}/{max_retries}): {str(ssl_error)}")
                if attempt == max_retries - 1:
                    self.console.print("SSL connection failed consistently, possibly server certificate issue")
                else:
                    time.sleep(2 ** attempt)  # Exponential backoff
                    
            except requests.exceptions.ConnectionError as conn_error:
                self.console.print(f"Connection error (attempt {attempt + 1}/{max_retries}): {str(conn_error)}")
                if attempt == max_retries - 1:
                    self.console.print("Network connection failed consistently")
                else:
                    time.sleep(2 ** attempt)
                    
            except requests.exceptions.Timeout as timeout_error:
                self.console.print(f"Timeout error (attempt {attempt + 1}/{max_retries}): {str(timeout_error)}")
                if attempt == max_retries - 1:
                    self.console.print("Request timeout")
                else:
                    time.sleep(1)
                    
            except Exception as e:
                self.console.print(f"Failed to download image (attempt {attempt + 1}/{max_retries}): {str(e)}")
                if attempt == max_retries - 1:
                    self.console.print("All retry attempts failed")
                else:
                    time.sleep(1)
        
        return None

    def get_current_settings(self) -> dict:
        """
        Get current settings information
        
        Returns:
            Current settings dictionary
        """
        return {
            "llm_base_url": self.llm_config["base_url"],
            "llm_model_name": self.llm_config["model_name"],
            "t2i_base_url": self.t2i_config["base_url"],
            "t2i_model_name": self.t2i_config["model_name"],
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "image_size": self.image_size,
            "quality": self.quality
        }


def main():
    """Main function demonstrating model client usage"""
    console = Console()
    try:
        # Create model client instance
        client = ModelClient()
        
        # Display current configuration information
        console.print("=== Current Configuration ===")
        settings = client.get_current_settings()
        for key, value in settings.items():
            console.print(f"{key}: {value}")
        console.print()
        
        # Test LLM Q&A functionality
        console.print("=== LLM Q&A Test ===")
        question = "What is artificial intelligence? Please answer briefly in 50 words or less."
        answer = client.get_answer(question)
        console.print(f"Question: {question}")
        console.print(f"Answer: {answer}")
        console.print()
        
        # Test text-to-image functionality
        console.print("=== Text-to-Image Test ===")
        image_prompt = "A cute cat playing in a garden, cartoon style"
        image_result = client.get_image(image_prompt)
        console.print(f"Image description: {image_prompt}")
        
        if "error" in image_result:
            console.print(f"Generation failed: {image_result['error']}")
        else:
            console.print(f"Generated image URL: {image_result['url']}")
            if image_result['content']:
                content_size = len(image_result['content'])
                console.print(f"Image content size: {content_size} bytes")
                # Option to save image locally
                # with open("generated_image.png", "wb") as f:
                #     f.write(image_result['content'])
                # console.print("Image saved as generated_image.png")
            else:
                console.print("Image content download failed")
        console.print()
        
        console.print("=== Program completed ===")
        
    except Exception as e:
        console.print(f"Program error: {str(e)}")


if __name__ == "__main__":
    main()