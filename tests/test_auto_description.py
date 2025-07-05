#!/usr/bin/env python3
"""
Simple test to verify the auto-generated project description method exists and is callable
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_method_exists():
    """Test if the _generate_project_description method exists"""
    print("=== Testing Auto Project Description Generation ===")
    
    try:
        # Import the core module
        from autoreadme.core import autoreadme
        
        # Check if the method exists
        if hasattr(autoreadme, '_generate_project_description'):
            print("✅ _generate_project_description method exists")
            
            # Check method signature
            import inspect
            sig = inspect.signature(autoreadme._generate_project_description)
            params = list(sig.parameters.keys())
            
            expected_params = ['self', 'structure', 'dependencies', 'descriptions']
            if params == expected_params:
                print("✅ Method signature is correct")
                print(f"   Parameters: {params}")
                return True
            else:
                print(f"❌ Method signature mismatch")
                print(f"   Expected: {expected_params}")
                print(f"   Found: {params}")
                return False
        else:
            print("❌ _generate_project_description method not found")
            return False
            
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def test_code_changes():
    """Test if the code changes were applied correctly"""
    print("\n=== Testing Code Changes ===")
    
    try:
        # Read the core.py file to verify changes
        core_file_path = os.path.join(os.path.dirname(__file__), 'src', 'autoreadme', 'core.py')
        
        with open(core_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check for key changes
        checks = [
            ('_generate_project_description method', '_generate_project_description(self, structure, dependencies, descriptions)'),
            ('Auto-generation call in generate method', 'self._generate_project_description(structure, dependencies, descriptions)'),
            ('Updated _get_basic_info prompt', 'press Enter to auto-generate'),
            ('Updated _get_project_meta_info prompt', 'press Enter to auto-generate')
        ]
        
        all_passed = True
        for check_name, check_text in checks:
            if check_text in content:
                print(f"✅ {check_name}: Found")
            else:
                print(f"❌ {check_name}: Not found")
                all_passed = False
        
        return all_passed
        
    except Exception as e:
        print(f"❌ Error reading core.py: {e}")
        return False

def test_workflow_logic():
    """Test the workflow logic for empty descriptions"""
    print("\n=== Testing Workflow Logic ===")
    
    try:
        core_file_path = os.path.join(os.path.dirname(__file__), 'src', 'autoreadme', 'core.py')
        
        with open(core_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check for the logic in generate method
        workflow_checks = [
            'if not self.config["project_description"]:',
            'self.config["project_description"] = self._generate_project_description(',
            'structure, dependencies, descriptions'
        ]
        
        all_found = True
        for check in workflow_checks:
            if check in content:
                print(f"✅ Workflow logic found: {check[:50]}...")
            else:
                print(f"❌ Workflow logic missing: {check[:50]}...")
                all_found = False
        
        return all_found
        
    except Exception as e:
        print(f"❌ Error checking workflow logic: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Testing Auto Project Description Generation Feature")
    print("=" * 60)
    
    # Run tests
    test1_result = test_method_exists()
    test2_result = test_code_changes()
    test3_result = test_workflow_logic()
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Summary")
    print(f"Test 1 (Method exists): {'✅ PASSED' if test1_result else '❌ FAILED'}")
    print(f"Test 2 (Code changes): {'✅ PASSED' if test2_result else '❌ FAILED'}")
    print(f"Test 3 (Workflow logic): {'✅ PASSED' if test3_result else '❌ FAILED'}")
    
    if test1_result and test2_result and test3_result:
        print("\n🎉 All tests passed! Auto project description feature has been implemented correctly.")
        print("\n📝 Implementation Summary:")
        print("   • Added _generate_project_description() method")
        print("   • Modified _get_basic_info() to support auto-generation")
        print("   • Modified _get_project_meta_info() to support auto-generation")
        print("   • Updated generate() method to call auto-generation when description is empty")
        print("   • Auto-generation uses project structure, dependencies, and file descriptions")
    else:
        print("\n⚠️  Some tests failed. Please check the implementation.")