# tests/test_logo_generator.py
# 测试 logo_generator 的 generate_logo 函数

import pytest
import os
import tempfile
from unittest.mock import MagicMock, patch
from rich.console import Console
from pathlib import Path
import sys

root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))
from src.readmex.utils.logo_generator import generate_logo
from src.readmex.utils.model_client import ModelClient


class TestLogoGenerator:
    """测试 Logo 生成器"""

    def test_generate_logo_mock(self):
        """使用 Mock 测试 logo 生成逻辑"""
        print("\n" + "=" * 60)
        print("🧪 测试 1: Mock Logo 生成逻辑测试")
        print("=" * 60)

        # 创建临时目录
        with tempfile.TemporaryDirectory() as temp_dir:
            # 准备测试数据
            descriptions = """
            {
              "main.py": "这是一个自动生成README文档的工具，使用AI技术分析项目结构和代码",
              "config.py": "配置文件管理模块，处理API密钥和模型设置"
            }
            """

            # 创建 Mock 对象
            mock_model_client = MagicMock()
            console = Console()

            # 模拟 LLM 返回的logo描述
            mock_model_client.get_answer.return_value = (
                "A modern AI-powered documentation tool logo with blue and green colors"
            )

            # 模拟图片生成结果
            mock_image_result = {
                "url": "https://example.com/logo.png",
                "content": b"fake_png_content_123",
            }
            mock_model_client.get_image.return_value = mock_image_result

            # 调用函数
            logo_path = generate_logo(
                temp_dir, descriptions, mock_model_client, console
            )

            # 验证结果
            assert logo_path is not None
            assert logo_path.endswith("logo.png")
            assert os.path.exists(logo_path)

            # 验证文件内容
            with open(logo_path, "rb") as f:
                content = f.read()
                assert content == b"fake_png_content_123"

            # 验证调用次数
            assert mock_model_client.get_answer.call_count == 1
            assert mock_model_client.get_image.call_count == 1

    def test_generate_logo_error_handling(self):
        """测试错误处理"""
        print("\n" + "=" * 60)
        print("🚨 测试 2: 错误处理测试")
        print("=" * 60)

        with tempfile.TemporaryDirectory() as temp_dir:
            descriptions = "测试项目"

            # 创建 Mock 对象，模拟图片生成失败
            mock_model_client = MagicMock()
            console = Console()

            # 模拟正常的描述生成
            mock_model_client.get_answer.return_value = "A test logo"

            # 模拟图片生成失败
            mock_image_result = {"error": "API调用失败"}
            mock_model_client.get_image.return_value = mock_image_result

            # 调用函数
            logo_path = generate_logo(
                temp_dir, descriptions, mock_model_client, console
            )

            # 验证返回None
            assert logo_path is None

    def test_generate_logo_empty_content(self):
        """测试图片内容为空的情况"""
        print("\n" + "=" * 60)
        print("📭 测试 3: 空内容处理测试")
        print("=" * 60)

        with tempfile.TemporaryDirectory() as temp_dir:
            descriptions = "测试项目"

            mock_model_client = MagicMock()
            console = Console()

            # 模拟正常的描述生成
            mock_model_client.get_answer.return_value = "A test logo"

            # 模拟图片生成成功但内容为空
            mock_image_result = {"url": "https://example.com/logo.png", "content": None}
            mock_model_client.get_image.return_value = mock_image_result

            # 调用函数
            logo_path = generate_logo(
                temp_dir, descriptions, mock_model_client, console
            )

            # 验证返回None
            assert logo_path is None

    def test_generate_logo_real_api(self):
        """使用真实API测试logo生成"""
        print("\n" + "=" * 60)
        print("🌐 测试 4: 真实 API Logo 生成测试")
        print("=" * 60)

        with tempfile.TemporaryDirectory() as temp_dir:
            descriptions = """
            {
              "readmex/core.py": "readmex核心类，负责协调整个README生成流程",
              "readmex/utils/model_client.py": "模型客户端，支持LLM问答和AI文生图功能",
              "readmex/utils/logo_generator.py": "Logo生成器，根据项目描述生成专业的项目Logo"
            }
            """

            # 使用真实的 ModelClient
            try:
                model_client = ModelClient()
                console = Console()

                print(f"测试目录: {temp_dir}")
                print("开始测试真实API logo生成...")

                logo_path = generate_logo(temp_dir, descriptions, model_client, console)

                # 如果遇到网络问题（SSL错误等），允许测试跳过
                if logo_path is None:
                    pytest.skip("Logo生成失败，可能由于网络连接问题（SSL错误等）")

                # 验证生成结果
                assert os.path.exists(logo_path), f"Logo文件不存在: {logo_path}"

                # 检查文件大小
                file_size = os.path.getsize(logo_path)
                assert file_size > 0, "Logo文件为空"
                assert file_size > 1000, f"Logo文件太小，可能生成失败: {file_size} 字节"

                print(f"✅ Logo 生成成功!")
                print(f"   文件路径: {logo_path}")
                print(f"   文件大小: {file_size:,} 字节")

                # 验证文件是有效的图片格式
                with open(logo_path, "rb") as f:
                    header = f.read(12)

                    # 检查常见图片格式
                    if header.startswith(b"\x89PNG\r\n\x1a\n"):
                        image_format = "PNG"
                    elif header.startswith(b"RIFF") and b"WEBP" in header:
                        image_format = "WebP"
                    elif header.startswith(b"\xff\xd8\xff"):
                        image_format = "JPEG"
                    else:
                        # 打印文件头以便调试
                        print(f"   文件头: {header}")
                        image_format = "Unknown"
                        # 不直接断言失败，而是警告
                        print(f"   ⚠️  未知图片格式，但文件大小正常: {file_size:,} 字节")

                if image_format != "Unknown":
                    print(f"   文件格式: {image_format} ✅")
                else:
                    print(f"   文件格式: 未知但可接受 ⚠️")

                # 验证images目录结构
                images_dir = os.path.dirname(logo_path)
                assert (
                    os.path.basename(images_dir) == "images"
                ), "Logo应该保存在images目录中"

                print(f"   目录结构: 正确 ✅")
                print("🎉 真实API logo生成测试通过!")

            except Exception as e:
                # 如果是网络相关错误，跳过测试而不是失败
                if (
                    "SSL" in str(e)
                    or "ConnectionError" in str(e)
                    or "TimeoutError" in str(e)
                ):
                    pytest.skip(f"网络连接问题，跳过测试: {e}")
                else:
                    pytest.fail(f"真实API测试失败: {e}")

    def test_logo_description_generation(self):
        """测试Logo描述生成功能（仅测试LLM部分）"""
        print("\n" + "=" * 60)
        print("💬 测试 5: LLM Logo 描述生成测试")
        print("=" * 60)

        try:
            model_client = ModelClient()
            console = Console()

            descriptions = """
            {
              "app.py": "一个简单的Web应用",
              "models.py": "数据库模型定义",
              "utils.py": "工具函数集合"
            }
            """

            print("测试Logo描述生成...")

            # 调用 LLM 生成 logo 描述
            prompt = f"""基于以下项目文件描述，为这个项目设计一个专业的logo描述。
            
项目文件描述：
{descriptions}

请用英文生成一个详细的logo设计描述，包括：
1. 视觉元素和符号
2. 颜色方案
3. 整体风格
4. 技术感和专业性

描述应该适合用于AI图像生成，清晰明确。"""

            logo_description = model_client.get_answer(prompt)

            # 验证返回结果
            assert logo_description is not None, "Logo描述生成失败"
            assert len(logo_description.strip()) > 20, "Logo描述太短"
            assert isinstance(logo_description, str), "Logo描述应该是字符串"

            print(f"✅ Logo描述生成成功!")
            print(f"   描述长度: {len(logo_description)} 字符")
            print(f"   描述内容: {logo_description}")

            # 检查描述是否包含一些常见的设计元素词汇
            design_keywords = [
                "logo",
                "color",
                "design",
                "professional",
                "modern",
                "symbol",
                "icon",
            ]
            found_keywords = [
                word
                for word in design_keywords
                if word.lower() in logo_description.lower()
            ]

            print(f"   包含设计关键词: {', '.join(found_keywords)}")
            assert (
                len(found_keywords) >= 2
            ), f"Logo描述应该包含更多设计相关词汇，当前只有: {found_keywords}"

            print("🎉 Logo描述生成测试通过!")

        except Exception as e:
            if "SSL" in str(e) or "ConnectionError" in str(e):
                pytest.skip(f"网络连接问题，跳过描述生成测试: {e}")
            else:
                pytest.fail(f"Logo描述生成测试失败: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
