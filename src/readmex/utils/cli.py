import argparse
import os
import sys
from pathlib import Path
from rich.console import Console
from rich.table import Table

# Add the src directory to the Python path when running directly
if __name__ == '__main__':
    # Get the project root directory (3 levels up from this file)
    project_root = Path(__file__).parent.parent.parent.parent
    src_path = project_root / "src"
    if src_path not in sys.path:
        sys.path.insert(0, str(src_path))

from readmex.core import readmex
from readmex.website_core import WebsiteGenerator
from readmex.config import validate_config, get_config_sources

def main():
    """
    readmex command line entry point
    Support both command line arguments and interactive interface
    """
    parser = argparse.ArgumentParser(
        description="readmex - AI-driven README documentation generator",
        epilog="Examples:\n  readmex                    # Interactive mode\n  readmex .                  # Generate for current directory\n  readmex ./my-project       # Generate for specific directory\n  readmex --website          # Generate MkDocs website\n  readmex --website --serve  # Generate and serve website",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "project_path",
        nargs="?",
        help="Path of project for generating README (default: interactive input)"
    )
    parser.add_argument(
        "--website",
        action="store_true",
        help="Generate MkDocs website instead of README"
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Start local server after generating website (requires --website)"
    )
    parser.add_argument(
        "--deploy",
        action="store_true",
        help="Deploy website to GitHub Pages (requires --website)"
    )
    parser.add_argument(
        "--version", 
        action="version", 
        version="readmex 0.1.8"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose mode to print prompts and detailed information"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode to skip LLM calls for faster testing"
    )
    parser.add_argument(
        "--silent",
        action="store_true",
        help="Enable silent mode to skip interactive prompts (auto-generate all content)"
    )
    
    args = parser.parse_args()

    try:
        validate_config()
        console = Console()
        
        # Determine project path
        if args.project_path:
            project_path = os.path.abspath(args.project_path)
            if not os.path.isdir(project_path):
                console.print(f"[bold red]Error: Project path '{project_path}' is not a valid directory.[/bold red]")
                return
        elif args.serve:
            # 对于 --serve 参数，直接使用当前目录
            project_path = os.getcwd()
        else:
            console.print("[bold cyan]readmex - AI README Generator[/bold cyan]")
            console.print("Please provide the path of project for generating README (press Enter to use the current directory).\n")
            project_input = console.input("[cyan]Project Path[/cyan]: ").strip()
            project_path = os.path.abspath(project_input) if project_input else os.getcwd()
            
            if not os.path.isdir(project_path):
                console.print(f"[bold red]Error: Project path '{project_path}' is not a valid directory.[/bold red]")
                return

        if args.website:
            # 网站生成模式
            _handle_website_generation(args, project_path, console)
        elif args.serve:
            # 仅启动服务模式
            _handle_serve_only(project_path, console)
        else:
            # README生成模式
            generator = readmex(
                project_dir=project_path,
                debug=getattr(args, 'debug', False),
                silent=getattr(args, 'silent', False)
            )
            generator.generate()
    except KeyboardInterrupt:
        console = Console()
        console.print("\n[yellow]Operation cancelled[/yellow]")
    except FileNotFoundError as e:
        console = Console()
        console.print(f"[red]Error: {e}[/red]")
    except Exception as e:
        console = Console()
        console.print(f"[bold red]An error occurred: {e}[/bold red]")
        
        # Show configuration information to help with debugging
        from readmex.config import load_config
        try:
            config = load_config()
            sources = get_config_sources()
            if config and sources:
                # Show configuration source info once
                console.print("\n[yellow]Configuration loaded from:[/yellow]")
                source_files = set(sources.values())
                for source_file in source_files:
                    if "Environment Variable" not in source_file:
                        console.print(f"[yellow]  • {source_file}[/yellow]")
                
                # Show configuration table with actual values
                table = Table(title="[bold cyan]Current Configuration[/bold cyan]")
                table.add_column("Variable", style="cyan")
                table.add_column("Value", style="green")
                
                # Only show non-sensitive configuration values
                display_keys = ["llm_model_name", "t2i_model_name", "llm_base_url", "t2i_base_url",
                               "embedding_model_name", "embedding_base_url", "local_embedding",
                               "github_username", "twitter_handle", "linkedin_username", "email"]
                
                for key in display_keys:
                    if key in config and config[key]:
                        value = config[key]
                        # Mask API keys for security
                        if "api_key" in key.lower():
                            value = "***" + value[-4:] if len(value) > 4 else "***"
                        table.add_row(key, value)
                
                console.print(table)
        except Exception:
            pass  # Don't show config info if there's an error loading it


def _handle_serve_only(project_path: str, console: Console) -> None:
    """处理仅启动服务功能"""
    try:
        # 创建网站生成器以获取输出目录
        website_generator = WebsiteGenerator(project_path)
        
        # 检查网站是否存在
        website_exists = os.path.exists(website_generator.output_dir) and \
                        os.path.exists(os.path.join(website_generator.output_dir, "mkdocs.yml")) and \
                        os.path.exists(os.path.join(website_generator.output_dir, "docs"))
        
        if not website_exists:
            console.print("[red]未找到已生成的网站。请先运行 'readmex --website' 生成网站。[/red]")
            return
            
        console.print("[green]启动网站服务...[/green]")
        _serve_website(website_generator.output_dir, console)
        
    except Exception as e:
        console.print(f"[red]启动服务失败: {e}[/red]")
        raise


def _handle_website_generation(args, project_path: str, console: Console) -> None:
    """处理网站生成相关功能"""
    try:
        # 验证参数组合
        if args.deploy and not args.website:
            console.print("[red]Error: --deploy requires --website[/red]")
            return
            
        # 创建网站生成器
        website_generator = WebsiteGenerator(project_path, verbose=getattr(args, 'verbose', False), debug=getattr(args, 'debug', False))
        
        # 检查是否只需要启动服务且网站已存在
        website_exists = os.path.exists(website_generator.output_dir) and \
                        os.path.exists(os.path.join(website_generator.output_dir, "mkdocs.yml")) and \
                        os.path.exists(os.path.join(website_generator.output_dir, "docs"))
        
        if args.serve and website_exists and not args.deploy:
            # 如果只是要启动服务且网站已存在，直接启动服务
            console.print("[green]检测到已存在的网站，直接启动服务...[/green]")
            _serve_website(website_generator.output_dir, console)
            return
            
        # 生成网站
        website_generator.generate_website()
        
        # 处理后续操作
        if args.serve:
            _serve_website(website_generator.output_dir, console)
        elif args.deploy:
            _deploy_website(website_generator.output_dir, console)
            
    except Exception as e:
        console.print(f"[red]网站生成失败: {e}[/red]")
        raise


def _serve_website(website_dir: str, console: Console) -> None:
    """启动本地服务器"""
    try:
        import subprocess
        import webbrowser
        import time
        import socket
        
        console.print("[cyan]启动本地服务器...[/cyan]")
        
        # 检查是否安装了mkdocs
        try:
            subprocess.run(["mkdocs", "--version"], 
                         capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            console.print("[yellow]未找到mkdocs，正在安装...[/yellow]")
            subprocess.run(["pip3.9", "install", "mkdocs", "mkdocs-material", "mkdocs-drawio"], 
                         check=True)
            
        # 检查端口是否被占用
        def is_port_in_use(port):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                return s.connect_ex(('localhost', port)) == 0
                
        port = 8000
        if is_port_in_use(port):
            console.print(f"[yellow]端口 {port} 已被占用，尝试使用其他端口...[/yellow]")
            for p in range(8001, 8010):
                if not is_port_in_use(p):
                    port = p
                    break
            else:
                console.print("[red]无法找到可用端口[/red]")
                return
        
        # 启动服务器
        console.print("[green]服务器启动中，请稍候...[/green]")
        process = subprocess.Popen(
            ["mkdocs", "serve", "-a", f"127.0.0.1:{port}"],
            cwd=website_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        
        # 等待服务器启动并检查是否成功
        max_wait_time = 10
        start_time = time.time()
        server_started = False
        
        while time.time() - start_time < max_wait_time:
            if process.poll() is not None:
                # 进程已退出，说明启动失败
                output = process.stdout.read() if process.stdout else ""
                console.print(f"[red]服务器启动失败: {output}[/red]")
                return
                
            if is_port_in_use(port):
                server_started = True
                break
                
            time.sleep(0.5)
        
        if not server_started:
            console.print("[red]服务器启动超时[/red]")
            process.terminate()
            return
        
        # 打开浏览器
        url = f"http://127.0.0.1:{port}"
        console.print(f"[green]✅ 服务器已启动: {url}[/green]")
        
        open_browser = console.input(
            "[cyan]是否在浏览器中打开网站？ (Y/n): [/cyan]"
        ).strip().lower()
        
        if open_browser in ['', 'y', 'yes', '是']:
            webbrowser.open(url)
            
        console.print("[yellow]按 Ctrl+C 停止服务器[/yellow]")
        
        try:
            # 持续监控服务器状态
            while process.poll() is None:
                time.sleep(1)
        except KeyboardInterrupt:
            console.print("\n[yellow]正在停止服务器...[/yellow]")
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            console.print("[green]服务器已停止[/green]")
            
    except Exception as e:
        console.print(f"[red]启动服务器失败: {e}[/red]")


def _deploy_website(website_dir: str, console: Console) -> None:
    """部署网站到GitHub Pages"""
    try:
        import subprocess
        
        console.print("[cyan]准备部署到GitHub Pages...[/cyan]")
        
        # 检查是否在git仓库中
        try:
            subprocess.run(["git", "status"], 
                         cwd=website_dir, 
                         capture_output=True, 
                         check=True)
        except subprocess.CalledProcessError:
            console.print("[red]Error: 当前目录不是git仓库[/red]")
            return
            
        # 检查是否安装了mkdocs
        try:
            subprocess.run(["mkdocs", "--version"], 
                         capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            console.print("[yellow]未找到mkdocs，正在安装...[/yellow]")
            subprocess.run(["pip", "install", "mkdocs", "mkdocs-material", "mkdocs-drawio"], 
                         check=True)
            
        # 部署到gh-pages分支
        console.print("[cyan]正在部署...[/cyan]")
        result = subprocess.run(
            ["mkdocs", "gh-deploy", "--clean"],
            cwd=website_dir,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            console.print("[green]✅ 网站已成功部署到GitHub Pages[/green]")
            console.print("[cyan]通常需要几分钟时间生效[/cyan]")
        else:
            console.print(f"[red]部署失败: {result.stderr}[/red]")
            
    except Exception as e:
        console.print(f"[red]部署失败: {e}[/red]")


if __name__ == '__main__':
    main()