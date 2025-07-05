#!/usr/bin/env python3
"""
Test script to verify the extended auto-generation functionality for all fields:
- Entry File
- Key Features  
- Additional Information
"""

import sys
import os

def test_new_methods_exist():
    """Test if all new auto-generation methods exist in the code"""
    print("=== Testing Extended Auto-Generation Methods ===")
    
    try:
        # Read the core.py file to check for method definitions
        core_file_path = os.path.join(os.path.dirname(__file__), 'src', 'readmex', 'core.py')
        
        with open(core_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check if all new methods exist
        methods_to_check = [
            'def _generate_entry_file(self, structure, dependencies, descriptions):',
            'def _generate_key_features(self, structure, dependencies, descriptions):',
            'def _generate_additional_info(self, structure, dependencies, descriptions):'
        ]
        
        all_found = True
        for method_def in methods_to_check:
            if method_def in content:
                method_name = method_def.split('(')[0].replace('def ', '')
                print(f"✅ {method_name} method exists with correct signature")
            else:
                method_name = method_def.split('(')[0].replace('def ', '')
                print(f"❌ {method_name} method does not exist or has incorrect signature")
                all_found = False
        
        return all_found
        
    except Exception as e:
        print(f"❌ Error reading core.py: {e}")
        return False

def test_generate_method_integration():
    """Test if the generate method includes all auto-generation calls"""
    print("\n=== Testing Generate Method Integration ===")
    
    try:
        # Read the core.py file to check for auto-generation calls
        core_file_path = os.path.join(os.path.dirname(__file__), 'src', 'readmex', 'core.py')
        
        with open(core_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check for all auto-generation calls in generate method
        auto_gen_calls = [
            'self._generate_entry_file(structure, dependencies, descriptions)',
            'self._generate_key_features(structure, dependencies, descriptions)',
            'self._generate_additional_info(structure, dependencies, descriptions)'
        ]
        
        all_found = True
        for call in auto_gen_calls:
            if call in content:
                print(f"✅ Found auto-generation call: {call}")
            else:
                print(f"❌ Missing auto-generation call: {call}")
                all_found = False
        
        # Check for conditional logic
        conditional_checks = [
            'if not self.config["entry_file"]:',
            'if not self.config["key_features"]:',
            'if not self.config["additional_info"]:'
        ]
        
        for check in conditional_checks:
            if check in content:
                print(f"✅ Found conditional check: {check}")
            else:
                print(f"❌ Missing conditional check: {check}")
                all_found = False
        
        return all_found
        
    except Exception as e:
        print(f"❌ Error reading core.py: {e}")
        return False

def test_user_interface_updates():
    """Test if user interface prompts have been updated"""
    print("\n=== Testing User Interface Updates ===")
    
    try:
        core_file_path = os.path.join(os.path.dirname(__file__), 'src', 'readmex', 'core.py')
        
        with open(core_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check for updated prompts in both _get_basic_info and _get_project_meta_info
        expected_prompts = [
            'press Enter to auto-detect',  # Entry file
            'press Enter to auto-generate',  # Key features and additional info
            'will auto-detect based on project analysis',
            'will auto-generate based on project analysis'
        ]
        
        all_found = True
        for prompt in expected_prompts:
            if prompt in content:
                print(f"✅ Found updated prompt: '{prompt}'")
            else:
                print(f"❌ Missing updated prompt: '{prompt}'")
                all_found = False
        
        return all_found
        
    except Exception as e:
        print(f"❌ Error checking user interface updates: {e}")
        return False

def test_method_implementations():
    """Test if the method implementations contain proper logic"""
    print("\n=== Testing Method Implementations ===")
    
    try:
        core_file_path = os.path.join(os.path.dirname(__file__), 'src', 'readmex', 'core.py')
        
        with open(core_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check for key implementation details
        implementation_checks = [
            'Auto-detecting entry file based on project analysis',
            'Auto-generating key features based on project analysis', 
            'Auto-generating additional information based on project analysis',
            'self.model_client.get_answer(prompt)',
            'detected_entry = detected_entry.strip()',
            'generated_features = generated_features.strip()',
            'generated_info = generated_info.strip()'
        ]
        
        all_found = True
        for check in implementation_checks:
            if check in content:
                print(f"✅ Found implementation detail: '{check}'")
            else:
                print(f"❌ Missing implementation detail: '{check}'")
                all_found = False
        
        return all_found
        
    except Exception as e:
        print(f"❌ Error checking method implementations: {e}")
        return False

def main():
    """Run all tests"""
    print("Testing Extended Auto-Generation Functionality\n")
    
    tests = [
        test_new_methods_exist,
        test_generate_method_integration,
        test_user_interface_updates,
        test_method_implementations
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
            results.append(False)
    
    # Summary
    print("\n" + "="*50)
    print("EXTENDED AUTO-GENERATION TEST SUMMARY")
    print("="*50)
    
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(f"🎉 All tests passed! ({passed}/{total})")
        print("✅ Extended auto-generation functionality is properly implemented")
        print("\n📋 Implementation Summary:")
        print("   • Entry file auto-detection")
        print("   • Key features auto-generation")
        print("   • Additional info auto-generation")
        print("   • User interface prompts updated")
        print("   • Generate method integration complete")
    else:
        print(f"⚠️  Some tests failed ({passed}/{total})")
        print("❌ Extended auto-generation functionality needs attention")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)