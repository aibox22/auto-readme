import os
from rich.console import Console
import requests
from openai import OpenAI, AzureOpenAI
from typing import Optional, Dict, Union
from readmex.config import get_llm_config, get_t2i_config, validate_config
import time


class ModelClient:
    """Model client class for LLM Q&A and text-to-image functionality"""
    
    def __init__(self, max_tokens: int = 10000, temperature: float = 0.7, 
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
        
        # Check if we're using Azure OpenAI with detailed logging
        self.console.print("[cyan]🔧 ModelClient Initialization[/cyan]")
        self.console.print(f"[dim]LLM Base URL: {self.llm_config['base_url']}[/dim]")
        self.console.print(f"[dim]T2I Base URL: {self.t2i_config['base_url']}[/dim]")
        
        self.is_llm_azure = self._is_azure_openai(self.llm_config["base_url"])
        self.is_t2i_azure = self._is_azure_openai(self.t2i_config["base_url"])
        
        # Log detection results
        llm_provider = "[blue]Azure OpenAI[/blue]" if self.is_llm_azure else "[green]Standard OpenAI[/green]"
        t2i_provider = "[blue]Azure OpenAI[/blue]" if self.is_t2i_azure else "[green]Standard OpenAI[/green]"
        self.console.print(f"[cyan]📊 LLM Provider:[/cyan] {llm_provider}")
        self.console.print(f"[cyan]🎨 T2I Provider:[/cyan] {t2i_provider}")
        
        # Initialize clients
        self.console.print("[cyan]🔌 Initializing clients...[/cyan]")
        self.llm_client = self._initialize_llm_client()
        self.t2i_client = self._initialize_t2i_client()
        self.console.print("[green]✓ ModelClient initialization complete[/green]")
    
    def _is_azure_openai(self, base_url: str) -> bool:
        """
        Check if the base URL is for Azure OpenAI
        
        Args:
            base_url: The base URL to check
            
        Returns:
            True if it's Azure OpenAI, False otherwise
        """
        is_azure = ".openai.azure.com" in base_url.lower()
        self.console.print(f"[dim]🔍 Checking URL: {base_url}[/dim]")
        self.console.print(f"[dim]   Contains '.openai.azure.com': {is_azure}[/dim]")
        return is_azure

    def _extract_azure_info(self, base_url: str) -> tuple[str, str, str]:
        """
        Extract Azure OpenAI endpoint, deployment name and API version from base_url
        
        Args:
            base_url: Azure OpenAI URL like:
                https://resource.openai.azure.com/openai/deployments/model-name/...?api-version=2024-02-01
                
        Returns:
            Tuple of (azure_endpoint, deployment_name, api_version)
        """
        import re
        from urllib.parse import urlparse, parse_qs
        
        # First extract the base endpoint and deployment from path
        endpoint_pattern = r'(https://[^/]+\.openai\.azure\.com)(?:/openai/deployments/([^/\?]+))?'
        match = re.match(endpoint_pattern, base_url)
        
        if match:
            azure_endpoint = match.group(1)
            deployment_name = match.group(2) if match.group(2) else "unknown"
            
            # Extract API version from query parameters
            parsed_url = urlparse(base_url)
            query_params = parse_qs(parsed_url.query)
            api_version = query_params.get('api-version', ['2024-02-01'])[0]
            
            self.console.print(f"[dim]   Extracted endpoint: {azure_endpoint}[/dim]")
            self.console.print(f"[dim]   Extracted deployment: {deployment_name}[/dim]")
            self.console.print(f"[dim]   Extracted API version: {api_version}[/dim]")
            
            return azure_endpoint, deployment_name, api_version
        else:
            self.console.print(f"[yellow]⚠️ Could not parse Azure URL: {base_url}[/yellow]")
            # Fallback: assume the base_url is the endpoint
            return base_url, "unknown", "2024-02-01"
    
    def _initialize_llm_client(self) -> Union[OpenAI, AzureOpenAI]:
        """
        Initialize LLM client (OpenAI or Azure OpenAI)
        
        Returns:
            Configured LLM client (OpenAI or AzureOpenAI)
        """
        if self.is_llm_azure:
            self.console.print("[cyan]🔧 Initializing Azure OpenAI LLM client[/cyan]")
            # For Azure OpenAI, extract azure_endpoint, deployment and api_version from base_url
            base_url = self.llm_config["base_url"]
            azure_endpoint, deployment_name, api_version = self._extract_azure_info(base_url)
            
            # Store deployment name for use in API calls
            self.llm_deployment = deployment_name
            
            self.console.print(f"[dim]   Azure Endpoint: {azure_endpoint}[/dim]")
            self.console.print(f"[dim]   Deployment: {deployment_name}[/dim]")
            self.console.print(f"[dim]   API Version: {api_version}[/dim]")
            
            client = AzureOpenAI(
                azure_endpoint=azure_endpoint,
                api_key=self.llm_config["api_key"],
                api_version=api_version,  # Use extracted API version
            )
            self.console.print("[green]✓ Azure OpenAI LLM client initialized[/green]")
            return client
        else:
            self.console.print("[cyan]🔧 Initializing standard OpenAI LLM client[/cyan]")
            self.console.print(f"[dim]   Base URL: {self.llm_config['base_url']}[/dim]")
            
            client = OpenAI(
                base_url=self.llm_config["base_url"],
                api_key=self.llm_config["api_key"],
            )
            self.console.print("[green]✓ Standard OpenAI LLM client initialized[/green]")
            return client
    
    def _initialize_t2i_client(self) -> Union[OpenAI, AzureOpenAI]:
        """
        Initialize text-to-image client (OpenAI or Azure OpenAI)
        
        Returns:
            Configured text-to-image client (OpenAI or AzureOpenAI)
        """
        if self.is_t2i_azure:
            self.console.print("[cyan]🔧 Initializing Azure OpenAI T2I client[/cyan]")
            # For Azure OpenAI, extract azure_endpoint, deployment and api_version from base_url
            base_url = self.t2i_config["base_url"]
            azure_endpoint, deployment_name, api_version = self._extract_azure_info(base_url)
            
            # Store deployment name for use in API calls
            self.t2i_deployment = deployment_name
            
            self.console.print(f"[dim]   Azure Endpoint: {azure_endpoint}[/dim]")
            self.console.print(f"[dim]   Deployment: {deployment_name}[/dim]")
            self.console.print(f"[dim]   API Version: {api_version}[/dim]")
            
            client = AzureOpenAI(
                azure_endpoint=azure_endpoint,
                api_key=self.t2i_config["api_key"],
                api_version=api_version,  # Use extracted API version
            )
            self.console.print("[green]✓ Azure OpenAI T2I client initialized[/green]")
            return client
        else:
            self.console.print("[cyan]🔧 Initializing standard OpenAI T2I client[/cyan]")
            self.console.print(f"[dim]   Base URL: {self.t2i_config['base_url']}[/dim]")
            
            client = OpenAI(
                base_url=self.t2i_config["base_url"],
                api_key=self.t2i_config["api_key"],
            )
            self.console.print("[green]✓ Standard OpenAI T2I client initialized[/green]")
            return client
    
    def get_answer(self, question: str, model: Optional[str] = None, max_retries: int = 3) -> str:
        """
        Get answer using LLM (with retry mechanism)
        
        Args:
            question: User question
            model: Specify model to use, if not specified use default model from config
            max_retries: Maximum retry attempts
            
        Returns:
            LLM answer
        """
        # For Azure OpenAI, use deployment name; for others, use model name
        if self.is_llm_azure and hasattr(self, 'llm_deployment'):
            model_name = self.llm_deployment
            specified_model = model or self.llm_config["model_name"]
            self.console.print(f"[cyan]🤖 Making Azure OpenAI LLM request[/cyan]")
            self.console.print(f"[dim]   Using deployment: {model_name}[/dim]")
            self.console.print(f"[dim]   Requested model: {specified_model}[/dim]")
        else:
            model_name = model or self.llm_config["model_name"]
            self.console.print(f"[cyan]🤖 Making LLM request[/cyan]")
            self.console.print(f"[dim]   Model: {model_name}[/dim]")
        
        provider = 'Azure OpenAI' if self.is_llm_azure else 'OpenAI'
        self.console.print(f"[dim]   Provider: {provider}[/dim]")
        self.console.print(f"[dim]   Max retries: {max_retries}[/dim]")
        
        for attempt in range(max_retries):
            try:
                response = self.llm_client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "user", "content": question}
                    ],
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    timeout=60
                )
                
                answer = response.choices[0].message.content
                return answer
                
            except Exception as e:
                error_msg = str(e)
                self.console.print(f"[red]LLM request error (attempt {attempt + 1}/{max_retries}): {error_msg}[/red]")
                
                # Provide detailed error information
                self.console.print(f"[yellow]Model used: {model_name}[/yellow]")
                self.console.print(f"[yellow]Base URL: {self.llm_config.get('base_url', 'Unknown')}[/yellow]")
                
                # If this is the last attempt, raise exception
                if attempt == max_retries - 1:
                    self.console.print(f"[red]All retry attempts failed, giving up request[/red]")
                    raise Exception(f"LLM request failed after {max_retries} retries: {error_msg}")
                else:
                    # Exponential backoff delay
                    delay = 2 ** attempt
                    self.console.print(f"[yellow]Waiting {delay} seconds before retry...[/yellow]")
                    time.sleep(delay)
    
    def generate_text(self, prompt: str, model: Optional[str] = None) -> str:
        """
        Generate text using LLM (alias for get_answer)
        
        Args:
            prompt: Text prompt
            model: Specify model to use, if not specified use default model from config
            
        Returns:
            Generated text
        """
        return self.get_answer(prompt, model)
    
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
            # For Azure OpenAI, use deployment name; for others, use model name
            if self.is_t2i_azure and hasattr(self, 't2i_deployment'):
                model_name = self.t2i_deployment
                specified_model = model or self.t2i_config["model_name"]
                self.console.print(f"[cyan]🎨 Making Azure OpenAI T2I request[/cyan]")
                self.console.print(f"[dim]   Using deployment: {model_name}[/dim]")
                self.console.print(f"[dim]   Requested model: {specified_model}[/dim]")
            else:
                model_name = model or self.t2i_config["model_name"]
                self.console.print(f"[cyan]🎨 Making T2I request[/cyan]")
                self.console.print(f"[dim]   Model: {model_name}[/dim]")
            
            provider = 'Azure OpenAI' if self.is_t2i_azure else 'OpenAI'
            self.console.print(f"[dim]   Provider: {provider}[/dim]")
            self.console.print(f"[dim]   Image size: {self.image_size}[/dim]")
            self.console.print(f"[dim]   Quality: {self.quality}[/dim]")
            
            # Generate image request parameters - start with basic params
            generate_params = {
                "model": model_name,
                "prompt": prompt,
                "n": 1
            }
            
            # Add size and quality parameters based on provider type
            if self.is_t2i_azure:
                self.console.print("[cyan]🔧 Configuring for Azure OpenAI[/cyan]")
                # For Azure OpenAI, use basic parameters
                generate_params["size"] = self.image_size
                # Azure OpenAI may support quality parameter for DALL-E models
                deployment_model = specified_model if self.is_t2i_azure and hasattr(self, 't2i_deployment') else model_name
                if deployment_model.startswith("dall-e"):
                    generate_params["quality"] = self.quality
                    self.console.print("[dim]   Added quality parameter for DALL-E[/dim]")
                    
            else:
                self.console.print("[cyan]🔧 Configuring for standard OpenAI[/cyan]")
                # For OpenAI and other OpenAI-compatible APIs
                base_url = self.t2i_config.get("base_url", "")
                
                if "openai.com" in base_url or model_name.startswith("dall-e"):
                    generate_params["size"] = self.image_size
                    # Add quality parameter only for dall-e models
                    if model_name.startswith("dall-e"):
                        generate_params["quality"] = self.quality
                        self.console.print("[dim]   Added quality parameter for DALL-E[/dim]")
                else:
                    # For other providers (like Doubao/ByteDance), use basic parameters
                    generate_params["size"] = self.image_size
                    self.console.print("[dim]   Using basic parameters for other provider[/dim]")
                    
                    # Don't add quality parameter for non-OpenAI providers
                    # as it may cause "InvalidParameter" errors
            
            self.console.print(f"[cyan]📤 Sending request with parameters:[/cyan]")
            for key, value in generate_params.items():
                self.console.print(f"[dim]   {key}: {value}[/dim]")
            
            response = self.t2i_client.images.generate(**generate_params)
            
            self.console.print("[green]✓ Image generation request successful[/green]")
            
            image_url = response.data[0].url
            self.console.print(f"[green]✓ Image URL received: {image_url}[/green]")
            
            # Download image content with retry mechanism
            self.console.print("[cyan]⬇️ Downloading image content...[/cyan]")
            image_content = self._download_image_with_retry(image_url, max_retries=3)
            
            if image_content:
                size_mb = len(image_content) / (1024 * 1024)
                self.console.print(f"[green]✓ Download successful: {len(image_content)} bytes ({size_mb:.2f} MB)[/green]")
            else:
                self.console.print("[yellow]⚠️ Image download failed, but URL is available[/yellow]")
            
            return {
                "url": image_url,
                "content": image_content
            }
            
        except Exception as e:
            self.console.print(f"[red]❌ Image generation failed: {e}[/red]")
            # Provide helpful error information
            self.console.print(f"[yellow]🔍 Debug information:[/yellow]")
            self.console.print(f"[dim]   Model used: {model_name}[/dim]")
            self.console.print(f"[dim]   Base URL: {self.t2i_config.get('base_url', 'Unknown')}[/dim]")
            self.console.print(f"[dim]   Is Azure OpenAI: {self.is_t2i_azure}[/dim]")
            self.console.print(f"[dim]   Error type: {type(e).__name__}[/dim]")
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
                self.console.print(f"[dim]📥 Download attempt {attempt + 1}/{max_retries}[/dim]")
                
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
            "llm_is_azure": self.is_llm_azure,
            "t2i_base_url": self.t2i_config["base_url"],
            "t2i_model_name": self.t2i_config["model_name"],
            "t2i_is_azure": self.is_t2i_azure,
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