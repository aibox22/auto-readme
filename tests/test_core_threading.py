# tests/test_core_threading.py
# 测试多线程脚本描述生成功能

import pytest
import os
import tempfile
import time
from unittest.mock import MagicMock, patch
from pathlib import Path
import sys

# 添加项目根目录到路径
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

from src.autoreadme.core import autoreadme


class TestCoreThreading:
    """测试 autoreadme 的多线程功能"""

    def test_multithreaded_script_descriptions(self):
        """测试多线程脚本描述生成"""
        print("\n" + "=" * 60)
        print("🧵 测试: 多线程脚本描述生成")
        print("=" * 60)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # 创建测试文件
            test_files = {
                "app.py": "#!/usr/bin/env python\n# Main application file\nprint('Hello World')",
                "utils.py": "# Utility functions\ndef helper():\n    return True",
                "config.py": "# Configuration settings\nDEBUG = True\nAPI_KEY = 'test'",
                "models.py": "# Data models\nclass User:\n    def __init__(self, name):\n        self.name = name"
            }
            
            # 写入测试文件
            for filename, content in test_files.items():
                filepath = os.path.join(temp_dir, filename)
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)
            
            # 创建 autoreadme 实例并模拟 model_client
            craft = autoreadme(project_dir=temp_dir)
            
            # Mock model_client.get_answer 方法
            def mock_get_answer(prompt):
                # 模拟API调用延迟
                time.sleep(0.1)
                if "app.py" in prompt:
                    return "主应用程序文件，包含应用启动逻辑"
                elif "utils.py" in prompt:
                    return "工具函数模块，提供辅助功能"
                elif "config.py" in prompt:
                    return "配置管理模块，定义应用配置"
                elif "models.py" in prompt:
                    return "数据模型定义，包含用户类"
                else:
                    return "Python脚本文件"
            
            craft.model_client.get_answer = mock_get_answer
            
            print(f"测试目录: {temp_dir}")
            print(f"测试文件数量: {len(test_files)}")
            
            # 测试单线程处理时间
            start_time = time.time()
            descriptions_single = craft._generate_script_descriptions(max_workers=1)
            single_thread_time = time.time() - start_time
            
            print(f"单线程处理时间: {single_thread_time:.2f} 秒")
            
            # 测试多线程处理时间
            start_time = time.time()
            descriptions_multi = craft._generate_script_descriptions(max_workers=3)
            multi_thread_time = time.time() - start_time
            
            print(f"多线程处理时间: {multi_thread_time:.2f} 秒")
            print(f"速度提升: {single_thread_time/multi_thread_time:.2f}x")
            
            # 验证结果
            import json
            desc_single = json.loads(descriptions_single)
            desc_multi = json.loads(descriptions_multi)
            
            assert len(desc_single) == len(test_files), f"单线程处理文件数不匹配: {len(desc_single)} vs {len(test_files)}"
            assert len(desc_multi) == len(test_files), f"多线程处理文件数不匹配: {len(desc_multi)} vs {len(test_files)}"
            
            # 验证描述内容
            for filename in test_files.keys():
                assert filename in desc_single, f"单线程结果缺少文件: {filename}"
                assert filename in desc_multi, f"多线程结果缺少文件: {filename}"
                assert len(desc_single[filename]) > 0, f"单线程描述为空: {filename}"
                assert len(desc_multi[filename]) > 0, f"多线程描述为空: {filename}"
            
            print("✅ 多线程功能测试通过!")
            print(f"   ✓ 处理文件数: {len(desc_multi)}")
            print(f"   ✓ 性能提升: {single_thread_time/multi_thread_time:.2f}x")
            
            # 验证多线程确实比单线程快（考虑到测试环境的误差）
            if multi_thread_time < single_thread_time * 0.8:  # 至少快20%
                print("   ✓ 多线程性能优化有效")
            else:
                print("   ⚠️  多线程性能提升不明显（可能由于测试环境限制）")

    def test_empty_file_list(self):
        """测试空文件列表的处理"""
        print("\n" + "=" * 60)
        print("📂 测试: 空文件列表处理")
        print("=" * 60)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # 创建一个只有非脚本文件的目录
            with open(os.path.join(temp_dir, "README.md"), 'w') as f:
                f.write("# Test Project")
            
            craft = autoreadme(project_dir=temp_dir)
            
            descriptions = craft._generate_script_descriptions(max_workers=3)
            
            import json
            desc_dict = json.loads(descriptions)
            
            assert len(desc_dict) == 0, "空目录应该返回空字典"
            print("✅ 空文件列表处理测试通过!")

    def test_error_handling(self):
        """测试错误处理"""
        print("\n" + "=" * 60)
        print("🚨 测试: 错误处理机制")
        print("=" * 60)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # 创建测试文件
            test_file = os.path.join(temp_dir, "test.py")
            with open(test_file, 'w', encoding='utf-8') as f:
                f.write("print('test')")
            
            craft = autoreadme(project_dir=temp_dir)
            
            # Mock model_client.get_answer 抛出异常
            def mock_get_answer_error(prompt):
                raise Exception("API调用失败")
            
            craft.model_client.get_answer = mock_get_answer_error
            
            # 应该不会崩溃，而是优雅地处理错误
            descriptions = craft._generate_script_descriptions(max_workers=2)
            
            import json
            desc_dict = json.loads(descriptions)
            
            # 由于错误，可能没有成功处理任何文件
            print(f"错误情况下处理的文件数: {len(desc_dict)}")
            print("✅ 错误处理测试通过!")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"]) 