<a id="readme-top"></a>

<!-- 项目徽章 -->
[![贡献者][contributors-shield]][contributors-url]
[![分支][forks-shield]][forks-url]
[![星标][stars-shield]][stars-url]
[![问题][issues-shield]][issues-url]
[![许可证][license-shield]][license-url]

<!-- 语言切换 -->
<div align="center">
  
[English](README.md) | 简体中文

</div>

<!-- 项目LOGO -->
<br />
<div align="center">
  <a href="https://github.com/thu-ailab/ai-readme">
    <img src="images/logo.png" alt="Logo" height="100">
  </a>

<h3 align="center">AI-README</h3>

  <p align="center">
    🚀 AI智能README生成器：自动创建Markdown文档、Logo、徽章等。再也不用为文档编写而烦恼！
    <br />
    <a href="https://github.com/thu-ailab/ai-readme"><strong>探索文档 »</strong></a>
    <br />
    <br />
    <a href="https://github.com/thu-ailab/ai-readme">查看演示</a>
    &middot;
    <a href="https://github.com/thu-ailab/ai-readme/issues/new?labels=bug&template=bug-report---.md">报告Bug</a>
    &middot;
    <a href="https://github.com/thu-ailab/ai-readme/issues/new?labels=enhancement&template=feature-request---.md">请求功能</a>
  </p>
</div>

<!-- 目录 -->
<details>
  <summary>目录</summary>
  <ol>
    <li>
      <a href="#关于项目">关于项目</a>
      <ul>
        <li><a href="#技术栈">技术栈</a></li>
      </ul>
    </li>
    <li>
      <a href="#快速开始">快速开始</a>
      <ul>
        <li><a href="#前置要求">前置要求</a></li>
        <li><a href="#安装">安装</a></li>
      </ul>
    </li>
    <li><a href="#使用方法">使用方法</a></li>
    <li><a href="#路线图">路线图</a></li>
    <li><a href="#贡献">贡献</a></li>
    <li><a href="#许可证">许可证</a></li>
    <li><a href="#联系方式">联系方式</a></li>
    <li><a href="#致谢">致谢</a></li>
  </ol>
</details>

<!-- 关于项目 -->
## 关于项目

[![产品截图](images/screenshot.png)](https://example.com)

AI智能README生成器是一个基于AI的工具，可以自动为您的项目生成全面的Markdown README文件。它能够生成结构良好的文档，包括项目详情、技术栈、设置说明、使用示例、徽章、Logo等。

### 核心功能

- 🤖 **AI驱动的README生成**：即时生成全面的Markdown README文档
- 🔗 **自动徽章生成**：创建并嵌入相关的状态徽章（贡献者、分支、星标等）
- 🖼️ **智能Logo设计**：自动生成独特的项目Logo
- 🧠 **技术栈识别**：自动检测并包含项目的技术栈
- 🌐 **上下文感知智能**：根据项目的特定上下文和需求定制内容

<p align="right">(<a href="#readme-top">返回顶部</a>)</p>

### 技术栈

- [![Python][Python]][Python-url]
- [![OpenAI][OpenAI]][OpenAI-url]
- [![Rich][Rich]][Rich-url]

<p align="right">(<a href="#readme-top">返回顶部</a>)</p>

<!-- 快速开始 -->
## 快速开始

以下是在本地设置项目的示例说明。要获取本地副本并运行，请按照以下简单步骤操作。

### 前置要求

- Python 3.7+

### 安装

1. 克隆仓库
   ```bash
   git clone https://github.com/thu-ailab/ai-readme.git
   ```
2. 进入项目目录
   ```bash
   cd ai-readme
   ```
3. 安装aireadme包（这将使您能够在终端中使用`aireadme`命令）：
    ```bash
    pip install -e .
    ```
4. 通过编辑`source.env`文件并添加您的LLM API密钥来设置环境变量。

<p align="right">(<a href="#readme-top">返回顶部</a>)</p>

<!-- 使用示例 -->
## 使用方法

安装完成后，您可以在命令行中使用`aireadme`包。要生成README，请运行以下命令：
```bash
aireadme
```

或者您可以直接运行Python脚本：
```bash
python src/aireadme/cli.py --project-path /path/to/your/project --output-dir /path/to/output
```

这将会：
1. 生成`project_structure.txt`文件，包含项目结构
2. 生成`script_description.json`文件，包含项目中脚本的描述
3. 生成`requirements.txt`文件，包含项目的依赖要求
4. 生成`logo.png`文件，包含项目的Logo
5. 生成`README.md`文件，包含项目的README文档

<p align="right">(<a href="#readme-top">返回顶部</a>)</p>

<!-- 路线图 -->
## 路线图

- [ ] Logo生成的提示工程优化
- [ ] 多语言支持
- [ ] 增强AI对项目功能的描述能力

查看[开放问题](https://github.com/thu-ailab/ai-readme/issues)以获取提议功能（和已知问题）的完整列表。

<p align="right">(<a href="#readme-top">返回顶部</a>)</p>

<!-- 贡献 -->
## 贡献

贡献让开源社区成为了一个学习、启发和创造的绝佳场所。您所做的任何贡献都是**非常感谢**的。

如果您有建议可以改善此项目，请fork该仓库并创建一个pull request。您也可以简单地创建一个带有"enhancement"标签的issue。
不要忘记给项目点个星！再次感谢！

1. Fork此项目
2. 创建您的功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交您的更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启一个Pull Request

<p align="right">(<a href="#readme-top">返回顶部</a>)</p>

### 主要贡献者：

<a href="https://github.com/thu-ailab/ai-readme/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=thu-ailab/ai-readme" alt="contrib.rocks image" />
</a>

<!-- 许可证 -->
## 🎗 许可证

版权所有 © 2024-2025 [ai-readme][ai-readme]。<br />
基于[MIT][license-url]许可证发布。

<p align="right">(<a href="#readme-top">返回顶部</a>)</p>

<!-- 联系方式 -->
## 联系方式

邮箱：lintaothu@foxmail.com

项目链接：[https://github.com/thu-ailab/ai-readme](https://github.com/thu-ailab/ai-readme)

QQ群：2161023585（欢迎加入我们的QQ群进行讨论和获取帮助！）

<p align="right">(<a href="#readme-top">返回顶部</a>)</p>

<!-- 参考链接 -->
[ai-readme]: https://github.com/thu-ailab/ai-readme

<!-- MARKDOWN链接和图片 -->
[contributors-shield]: https://img.shields.io/github/contributors/thu-ailab/ai-readme.svg?style=for-the-badge
[contributors-url]: https://github.com/thu-ailab/ai-readme/graphs/contributors
[forks-shield]: https://img.shields.io/github/forks/thu-ailab/ai-readme.svg?style=for-the-badge
[forks-url]: https://github.com/thu-ailab/ai-readme/network/members
[stars-shield]: https://img.shields.io/github/stars/thu-ailab/ai-readme.svg?style=for-the-badge
[stars-url]: https://github.com/thu-ailab/ai-readme/stargazers
[issues-shield]: https://img.shields.io/github/issues/thu-ailab/ai-readme.svg?style=for-the-badge
[issues-url]: https://github.com/thu-ailab/ai-readme/issues
[license-shield]: https://img.shields.io/github/license/thu-ailab/ai-readme.svg?style=for-the-badge
[license-url]: https://github.com/thu-ailab/ai-readme/blob/master/LICENSE.txt
[Python]: https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white
[Python-url]: https://www.python.org/
[OpenAI]: https://img.shields.io/badge/OpenAI-000000?style=for-the-badge&logo=openai&logoColor=white
[OpenAI-url]: https://openai.com/
[Flask]: https://img.shields.io/badge/Flask-000000?style=for-the-badge&logo=flask&logoColor=white
[Flask-url]: https://flask.palletsprojects.com/
[Rich]: https://img.shields.io/badge/Rich-000000?style=for-the-badge&logo=rich&logoColor=white
[Rich-url]: https://rich.readthedocs.io/ 