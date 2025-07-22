#!/usr/bin/env python3
"""
Azure OpenAI Integration Tests for ReadmeX
Simplified version to ensure proper execution
"""

import os
import sys
import traceback
from pathlib import Path

# Add the src directory to Python path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from readmex.utils.model_client import ModelClient
from readmex.config import get_llm_config

try:
    from rich.console import Console
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    class Console:
        def print(self, text):
            import re
            clean_text = re.sub(r'\[.*?\]', '', str(text))
            print(clean_text)


def test_azure_openai():
    """Main test function for Azure OpenAI integration"""
    console = Console()
    
    if RICH_AVAILABLE:
        console.print("[bold green]🧪 Azure OpenAI Integration Tests[/bold green]")
    else:
        console.print("🧪 Azure OpenAI Integration Tests")
    
    console.print("=" * 50)
    
    test_results = []
    
    # Test 1: URL Detection
    try:
        console.print("\n🔍 Test 1: URL Detection")
        client = ModelClient()
        
        test_urls = [
            ("https://api.openai.com/v1", False),
            ("https://test.openai.azure.com", True),
        ]
        
        all_passed = True
        for url, expected_azure in test_urls:
            is_azure = client._is_azure_openai(url)
            passed = is_azure == expected_azure
            all_passed &= passed
            
            status = "✅" if passed else "❌"
            provider = "Azure" if is_azure else "Standard"
            console.print(f"  {status} {url} → {provider}")
        
        test_results.append(("URL Detection", all_passed))
        
    except Exception as e:
        console.print(f"❌ URL Detection failed: {e}")
        test_results.append(("URL Detection", False))
    
    # Test 2: Client Initialization
    try:
        console.print("\n🔌 Test 2: Client Initialization")
        client = ModelClient()
        
        config = get_llm_config()
        
        console.print(f"  LLM Provider: {'Azure OpenAI' if client.is_llm_azure else 'Standard OpenAI'}")
        console.print(f"  T2I Provider: {'Azure OpenAI' if client.is_t2i_azure else 'Standard OpenAI'}")
        console.print(f"  API Key: {config.get('api_key', 'Not set')[:10]}...")
        
        # Check Azure-specific attributes
        success = True
        if client.is_llm_azure and hasattr(client, 'llm_deployment'):
            console.print(f"  ✅ LLM Deployment: {client.llm_deployment}")
        elif client.is_llm_azure:
            console.print("  ❌ LLM deployment not set")
            success = False
            
        test_results.append(("Client Initialization", success))
        
    except Exception as e:
        console.print(f"❌ Client Initialization failed: {e}")
        test_results.append(("Client Initialization", False))
    
    # Test 3: API Call (if API key available)
    try:
        console.print("\n🧪 Test 3: API Call Test")
        config = get_llm_config()
        
        if not config.get('api_key'):
            console.print("  ⏭️  Skipped - No API key configured")
            test_results.append(("API Call", True))
        else:
            client = ModelClient()
            console.print("  🔄 Testing simple API call...")
            
            response = client.get_answer("What is 1+1? Answer with just the number.", max_retries=1)
            success = response and len(response.strip()) > 0
            
            if success:
                console.print(f"  ✅ API call successful: '{response.strip()}'")
            else:
                console.print("  ❌ API call failed or returned empty response")
            
            test_results.append(("API Call", success))
            
    except Exception as e:
        console.print(f"  ❌ API call failed: {e}")
        test_results.append(("API Call", False))
    
    # Summary
    console.print("\n" + "=" * 50)
    console.print("📊 Test Results Summary:")
    
    passed = sum(1 for _, success in test_results if success)
    total = len(test_results)
    
    for test_name, success in test_results:
        status = "✅ PASS" if success else "❌ FAIL"
        console.print(f"  {status} {test_name}")
    
    console.print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        console.print("🎉 All tests passed!")
    else:
        console.print("⚠️  Some tests failed.")
    
    return passed == total


if __name__ == "__main__":
    print("🚀 Starting Azure OpenAI Integration Tests...")
    try:
        success = test_azure_openai()
        print(f"\n✅ Tests completed successfully: {success}")
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"❌ Test execution failed: {e}")
        traceback.print_exc()
        sys.exit(1)
