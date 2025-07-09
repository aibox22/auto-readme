
<a id="readme-top"></a>

<!-- LANGUAGE SWITCH -->
<div align="center">
  
English | [简体中文](README_CN.md)

</div>

<!-- PROJECT POSTER -->
<div align="center">
  <img src="images/poster.png" alt="Poster" width="50%">
</div>

---

<!-- PROJECT LOGO -->
<br />
<div align="center">
  <!-- <a href="https://github.com/aibox22/readmex">
    <img src="images/logo.png" alt="Logo" height="100">
  </a> -->

<h3 align="center">readmex</h3>

  <p align="center">
    🚀 AI-Powered README Generator: Automatically creates beautiful READMEs and interactive wikis for any repository! Can run all in local with your own models.
    <br />
    <a href="https://github.com/aibox22/readmex"><strong>Explore the docs »</strong></a>
    <br />
  </p>

  <!-- PROJECT SHIELDS -->
[![Contributors][contributors-shield]][contributors-url]
[![Forks][forks-shield]][forks-url]
[![Stargazers][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]
<!-- [![Latest Release][release-shield]][release-url]
![Release Date][release-date-shield] -->
[![License][license-shield]][license-url]

  <p align="center">
    <a href="https://github.com/aibox22/readmex">View Demo</a>
    &middot;
    <a href="https://github.com/aibox22/readmex/issues/new?labels=bug&template=bug-report---.md">Report Bug</a>
    &middot;
    <a href="https://github.com/aibox22/readmex/issues/new?labels=enhancement&template=feature-request---.md">Request Feature</a>
  </p>
</div>



<!-- TABLE OF CONTENTS -->
<details>
  <summary>Table of Contents</summary>
  <ol>
    <li>
      <a href="#about-the-project">About The Project</a>
      <ul>
        <li><a href="#built-with">Built With</a></li>
      </ul>
    </li>
    <li>
      <a href="#getting-started">Getting Started</a>
      <ul>
        <li><a href="#prerequisites">Prerequisites</a></li>
        <li><a href="#installation">Installation</a></li>
      </ul>
    </li>
    <li><a href="#usage">Usage</a></li>
    <li><a href="#roadmap">Roadmap</a></li>
    <li><a href="#contributing">Contributing</a></li>
    <li><a href="#license">License</a></li>
    <li><a href="#contact">Contact</a></li>
    <li><a href="#acknowledgments">Acknowledgments</a></li>
  </ol>
</details>



<!-- ABOUT THE PROJECT -->
## 📖 About The Project

[![Flow Chart](images/flow.png)](https://example.com)

AI-Powered README Generator is an AI-powered tool that automatically generates comprehensive Markdown README files for your projects. It crafts well-structured documentation that includes project details, technology stack, setup instructions, usage examples, badges, logos, and more.

### Key Features

- 🤖 **AI-Powered READMEs**: Generate comprehensive Markdown READMEs instantly.
- 🔗 **Auto Badges**: Creates and embeds relevant status badges (contributors, forks, stars, etc.).
- 🖼️ **Smart Logo Design**: Crafts a unique project logo automatically.
- 🧠 **Tech Stack Identification**: Automatically detects and includes the project's technology stack.
- 🌐 **Context-Aware Intelligence**: Tailors content to your project's specific context and needs.

<p align="right">(<a href="#readme-top">back to top</a>)</p>



### Built With

- [![Python][Python]][Python-url]
- [![OpenAI][OpenAI]][OpenAI-url]
- [![Rich][Rich]][Rich-url]

### Supported Programming Languages

<details>
<summary>Click to expand supported languages</summary>

#### Web Development
- **JavaScript**
- **TypeScript**
- **HTML**
- **CSS**
- **SCSS**
- **Sass**
- **Less**
- **Stylus**
- **Pug**
- **Handlebars**
- **Mustache**
- **Twig**
- **Smarty**
- **Jinja**
- **Vue**

#### Programming Languages
- **Python**
- **Java**
- **C**
- **C++**
- **C#**
- **Go**
- **Rust**
- **PHP**
- **Ruby**
- **Swift**
- **Kotlin**
- **Scala**
- **R**
- **MATLAB**
- **Perl**
- **Lua**
- **Dart**
- **F#**
- **Visual Basic**
- **Assembly**
- **Objective-C**
- **Haskell**
- **Erlang**
- **Elixir**
- **Clojure**
- **CoffeeScript**
- **PowerShell**
- **Shell**
- **Batch**
- **Solidity**

#### Build & Configuration
- **Dockerfile**
- **Makefile**
- **CMake**
- **Gradle**
- **Maven**
- **Nix**
- **Terraform**

#### Data & Documentation
- **Jupyter**
- **Protobuf**
- **GraphQL**
- **WebAssembly**

#### Editor & IDE
- **Vim**
- **Emacs**

</details>

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- GETTING STARTED -->
## 🚀 Getting Started

This is an example of how you may give instructions on setting up your project locally. To get a local copy up and running follow these simple steps.

### Prerequisites

- Python 3.7+

### Installation

1. Install the package using pip:
   ```bash
   pip install readmex
   ```
### Configuration

`readmex` requires API keys for both the Language Model (for generating text) and the Text-to-Image model (for generating logos). You can configure these in one of two ways. Environment variables take precedence.

#### 1. Environment Variables (Recommended for CI/CD)

Set the following environment variables in your shell:

```bash
export LLM_API_KEY="your_llm_api_key"       # Required
export T2I_API_KEY="your_t2i_api_key"       # Required

# Optional: Specify custom API endpoints and models
export LLM_BASE_URL="https://api.example.com/v1"
export T2I_BASE_URL="https://api.example.com/v1"
export LLM_MODEL_NAME="your-llm-model"
export T2I_MODEL_NAME="your-t2i-model"

# Optional: Embedding model configuration for RAG (Retrieval-Augmented Generation)
export EMBEDDING_API_KEY="your_embedding_api_key"     # Optional, for web embedding models
export EMBEDDING_BASE_URL="https://api.example.com/v1" # Optional, for web embedding models
export EMBEDDING_MODEL_NAME="text-embedding-3-small"   # Optional, embedding model name
export LOCAL_EMBEDDING="true"                         # Optional, use local embedding model (default: true)
```

#### 2. Global Config File (Recommended for Local Use)

For convenience, you can create a global configuration file. The tool will automatically look for it.

1.  Create the directory: `mkdir -p ~/.readmex`
2.  Create the config file: `~/.readmex/config.json`
3.  Add your credentials and any optional settings. You can also include personal information, which will be used as defaults during interactive prompts:

```json
{
  "LLM_API_KEY": "your_llm_api_key",
  "T2I_API_KEY": "your_t2i_api_key",
  "LLM_BASE_URL": "https://api.example.com/v1",
  "T2I_BASE_URL": "https://api.example.com/v1",
  "LLM_MODEL_NAME": "gpt-4",
  "T2I_MODEL_NAME": "dall-e-3",
  "EMBEDDING_API_KEY": "your_embedding_api_key",
  "EMBEDDING_BASE_URL": "https://api.example.com/v1",
  "EMBEDDING_MODEL_NAME": "text-embedding-3-small",
  "LOCAL_EMBEDDING": "true",
  "github_username": "your_github_username",
  "twitter_handle": "your_twitter_handle",
  "linkedin_username": "your_linkedin_username",
  "email": "your_email@example.com"
}
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- USAGE EXAMPLES -->
## 💻 Usage

Once installed, you can use the `readmex` package in the command line. To generate your README, run the following:

### Method 1: Using the installed command (Recommended)
```bash
readmex
```

### Method 2: Running as a Python module
```bash
# Run the package directly
python -m readmex

# Or run the CLI module specifically
python -m readmex.utils.cli
```

### Method 3: Development mode (for contributors)
```bash
# From the project root directory
python src/readmex/utils/cli.py
```

### Command Line Options

All methods support the same command line arguments:

```bash
# Interactive mode (default)
readmex

# Generate for current directory
readmex .

# Generate for specific directory
readmex /path/to/your/project

# Generate MkDocs website
readmex --website

# Generate website and serve locally
readmex --website --serve

# Deploy to GitHub Pages
readmex --deploy

# Enable debug mode (skip LLM calls for testing)
readmex --debug

# Enable silent mode (auto-generate without prompts)
readmex --silent

# Enable verbose mode (show detailed information)
readmex --verbose
```

This will:
1. generate a `project_structure.txt` file, which contains the project structure.
2. generate a `script_description.json` file, which contains the description of the scripts in the project.
3. generate a `requirements.txt` file, which contains the requirements of the project.
4. generate a `logo.png` file, which contains the logo of the project.
5. generate a `README.md` file, which contains the README of the project.

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- ROADMAP -->
## 🗺️ Roadmap

- [ ] Prompt Engineering for Logo Generation
- [ ] Multi-language Support
- [ ] Enhanced AI Descriptions for Project Features

See the [open issues](https://github.com/aibox22/readmex/issues) for a full list of proposed features (and known issues).

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- CONTRIBUTING -->
## 🤝 Contributing

Contributions are what make the open-source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

If you have a suggestion that would make this better, please fork the repo and create a pull request. You can also simply open an issue with the tag "enhancement".
Don't forget to give the project a star! Thanks again!

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

<p align="right">(<a href="#readme-top">back to top</a>)</p>

### Top contributors:

<a href="https://github.com/aibox22/readmex/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=aibox22/readmex" alt="contrib.rocks image" />
</a>



<!-- LICENSE -->
## 🎗 License

Copyright © 2024-2025 [readmex][readmex]. <br />
Released under the [MIT][license-url] license.

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- CONTACT -->
## 📧 Contact

Email: lintaothu@foxmail.com

Project Link: [https://github.com/aibox22/readmex](https://github.com/aibox22/readmex)

QQ Group: 2161023585 (Welcome to join our QQ Group to discuss and get help!)

<div align="center">
  <img src="images/group_qr.png" alt="QQ Group QR Code" width="200">
  <p><em>Scan QR code to join our QQ Group</em></p>
</div>

<p align="right">(<a href="#readme-top">back to top</a>)</p>


<!-- REFERENCE LINKS -->
[readmex]: https://github.com/aibox22/readmex

<!-- MARKDOWN LINKS & IMAGES -->
[contributors-shield]: https://img.shields.io/github/contributors/aibox22/readmex.svg?style=flat-round
[contributors-url]: https://github.com/aibox22/readmex/graphs/contributors
[forks-shield]: https://img.shields.io/github/forks/aibox22/readmex.svg?style=flat-round
[forks-url]: https://github.com/aibox22/readmex/network/members
[stars-shield]: https://img.shields.io/github/stars/aibox22/readmex.svg?style=flat-round
[stars-url]: https://github.com/aibox22/readmex/stargazers
[issues-shield]: https://img.shields.io/github/issues/aibox22/readmex.svg?style=flat-round
[issues-url]: https://github.com/aibox22/readmex/issues
[release-shield]: https://img.shields.io/github/v/release/aibox22/readmex?style=flat-round
[release-url]: https://github.com/aibox22/readmex/releases
[release-date-shield]: https://img.shields.io/github/release-date/aibox22/readmex?color=9cf&style=flat-round
[license-shield]: https://img.shields.io/github/license/aibox22/readmex.svg?style=flat-round
[license-url]: https://github.com/aibox22/readmex/blob/master/LICENSE.txt
[Python]: https://img.shields.io/badge/Python-3776AB?style=flat-round&logo=python&logoColor=white
[Python-url]: https://www.python.org/
[OpenAI]: https://img.shields.io/badge/OpenAI-000000?style=flat-round&logo=openai&logoColor=white
[OpenAI-url]: https://openai.com/
[Flask]: https://img.shields.io/badge/Flask-000000?style=flat-round&logo=flask&logoColor=white
[Flask-url]: https://flask.palletsprojects.com/
[Rich]: https://img.shields.io/badge/Rich-000000?style=flat-round&logo=rich&logoColor=white
[Rich-url]: https://rich.readthedocs.io/

<!-- STAR HISTORY -->
## ⭐ Star History

<div align="center">
  <a href="https://star-history.com/#aibox22/readmex&Date">
    <img src="https://api.star-history.com/svg?repos=aibox22/readmex&type=Date" alt="Star History Chart" width="800">
  </a>
</div>
