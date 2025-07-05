# tests/test_model_client.py
# 测试 ModelClient 类的 get_answer 和 get_image 方法

import pytest
from pathlib import Path
import sys
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))
from src.readmex.utils.model_client import ModelClient

# 测试 get_answer 方法
def test_get_answer():
    # 实例化 ModelClient
    client = ModelClient()
    # 构造问题
    question = "你好，介绍一下你自己"
    # 调用 get_answer 获取回复
    answer = client.get_answer(question)
    print("get_answer 返回：", answer)
    # 断言返回内容不为空
    assert answer is not None and len(answer) > 0

# 测试 get_image 方法
# @pytest.mark.skip(reason="生成图片会消耗额度，调试时可去掉本行")
def test_get_image():
    # 实例化 ModelClient
    client = ModelClient()
    # 设置图片生成的 prompt
    prompt = "一只可爱的卡通猫，蓝色背景"
    # 调用 get_image 获取图片内容
    img_result = client.get_image(prompt)
    print("get_image 返回结果：", img_result)
    # 断言返回结果包含url或content
    assert img_result is not None
    assert "url" in img_result or "content" in img_result

# 测试配置信息获取
def test_get_current_settings():
    # 实例化 ModelClient
    client = ModelClient()
    # 获取当前设置
    settings = client.get_current_settings()
    print("当前设置：", settings)
    # 断言设置不为空
    assert settings is not None
    assert "llm_model_name" in settings
    assert "t2i_model_name" in settings 