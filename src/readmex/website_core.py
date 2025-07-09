import os
import ast
import json
import re
import time
import shutil
from typing import Dict, List, Tuple, Optional, Any
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from rich.console import Console
from rich.progress import Progress, TaskID, TimeElapsedColumn, TimeRemainingColumn, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn
from rich.live import Live
from rich.table import Table
from rich.panel import Panel

try:
    import yaml
except ImportError:
    yaml = None

from readmex.utils.model_client import ModelClient
from readmex.utils.file_handler import (
    find_files,
    get_project_structure,
    load_gitignore_patterns,
)
from readmex.config import load_config
from readmex.code_rag import CodeRAG


class ProgressTracker:
    """进度跟踪器，用于显示详细的生成进度信息"""
    
    def __init__(self, console: Console):
        self.console = console
        self.start_time = None
        self.current_stage = ""
        self.stages = [
            ("项目分析", "正在分析项目结构和代码..."),
            ("首页生成", "正在生成项目首页文档..."),
            ("安装指南", "正在生成安装说明文档..."),
            ("使用说明", "正在生成使用指南文档..."),
            ("API文档", "正在生成API参考文档..."),
            ("示例文档", "正在生成代码示例文档..."),
            ("架构文档", "正在生成项目架构文档..."),
            ("贡献指南", "正在生成贡献者指南..."),
            ("更新日志", "正在生成变更日志模板..."),
            ("配置文件", "正在生成MkDocs配置文件...")
        ]
        self.current_stage_index = 0
        self.total_stages = len(self.stages)
        
    def start(self):
        """开始进度跟踪"""
        self.start_time = time.time()
        
    def update_stage(self, stage_index: int):
        """更新当前阶段"""
        if stage_index < len(self.stages):
            self.current_stage_index = stage_index
            self.current_stage = self.stages[stage_index][1]
            
    def get_elapsed_time(self) -> str:
        """获取已用时间"""
        if self.start_time is None:
            return "00:00"
        elapsed = time.time() - self.start_time
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)
        return f"{minutes:02d}:{seconds:02d}"
        
    def get_estimated_time(self) -> str:
        """获取预计总时间"""
        if self.start_time is None or self.current_stage_index == 0:
            return "预估中..."
        
        elapsed = time.time() - self.start_time
        progress_ratio = self.current_stage_index / self.total_stages
        
        if progress_ratio > 0:
            estimated_total = elapsed / progress_ratio
            remaining = estimated_total - elapsed
            
            if remaining < 0:
                return "即将完成"
                
            minutes = int(remaining // 60)
            seconds = int(remaining % 60)
            return f"{minutes:02d}:{seconds:02d}"
        
        return "预估中..."
        
    def create_progress_display(self) -> Table:
        """创建进度显示表格"""
        table = Table.grid(padding=1)
        table.add_column(style="cyan", no_wrap=True)
        table.add_column(style="white")
        
        # 进度信息
        progress_percent = (self.current_stage_index / self.total_stages) * 100
        progress_bar = "█" * int(progress_percent // 5) + "░" * (20 - int(progress_percent // 5))
        
        table.add_row("📊 总体进度:", f"[{progress_bar}] {progress_percent:.1f}% ({self.current_stage_index}/{self.total_stages})")
        table.add_row("⏱️  已用时间:", self.get_elapsed_time())
        table.add_row("⏳ 预计剩余:", self.get_estimated_time())
        table.add_row("🔄 当前阶段:", self.current_stage)
        
        return table


class WebsiteGenerator:
    """MkDocs网站生成器 - 独立于README生成逻辑"""
    
    def __init__(self, project_dir: str, output_dir: str = None, model_client=None, verbose: bool = False, debug: bool = False, enable_rag: bool = True):
        self.project_dir = Path(project_dir)
        self.output_dir = Path(output_dir) if output_dir else self.project_dir / "website"
        self.console = Console()
        self.model_client = model_client or self._create_model_client()
        self.config = load_config()
        self.verbose = verbose
        self.debug = debug
        self.enable_rag = enable_rag
        
        # 网站结构配置
        self.docs_dir = self.output_dir / "docs"
        self.api_dir = self.docs_dir / "api"
        self.assets_dir = self.output_dir / "assets"
        
        # API文档生成策略
        self.api_filter = APIDocumentationFilter()
        self.api_generator = APIDocumentationGenerator(self.model_client, debug)
        
        # 创建进度跟踪器
        self.progress_tracker = ProgressTracker(self.console)
        
        # 初始化RAG系统
        self.code_rag = None
        if self.enable_rag:
            try:
                from readmex.config import get_embedding_config
                
                cache_dir = self.output_dir / ".rag_cache"
                # 确保缓存目录存在
                cache_dir.mkdir(parents=True, exist_ok=True)
                
                # 获取embedding配置
                embedding_config = get_embedding_config()
                
                self.code_rag = CodeRAG(
                    project_dir=str(self.project_dir),
                    cache_dir=str(cache_dir),
                    use_local_embedding=embedding_config.get('local_embedding', True)
                )
                self.console.print("[green]✅ RAG系统初始化成功[/green]")
            except Exception as e:
                self.console.print(f"[yellow]⚠️  RAG系统初始化失败: {e}[/yellow]")
                self.console.print("[yellow]将使用传统模式生成文档[/yellow]")
                self.enable_rag = False
        
    def _create_model_client(self):
        """创建模型客户端，处理可能的错误"""
        try:
            return ModelClient()
        except Exception as e:
            self.console.print(f"[yellow]Warning: Could not create ModelClient: {e}[/yellow]")
            return None
        
    def generate_website(self) -> None:
        """生成完整的MkDocs网站"""
        self.console.print("[bold green]🌐 开始生成项目网站...[/bold green]")
        
        # 启动进度跟踪
        self.progress_tracker.start()
        
        # 创建目录结构
        self._create_directory_structure()
        
        # 阶段0: 分析项目（不显示进度条）
        self.progress_tracker.update_stage(0)
        project_analysis = self._analyze_project()
        
        # 阶段1: 生成首页（README生成阶段，不显示网站进度条）
        self.progress_tracker.update_stage(1)
        self._generate_home_page(project_analysis)
        
        # README生成完成后，开始显示网站生成进度条
        self.console.print("\n[bold green]🌐 开始并行生成网站其他页面...[/bold green]")
        
        # 使用Live显示实时进度（从阶段2开始）
        with Live(self.progress_tracker.create_progress_display(), refresh_per_second=1, console=self.console) as live:
            # 并行生成所有页面
            self._generate_pages_in_parallel(project_analysis, live)
            
            # 阶段9: 生成配置文件
            self.progress_tracker.update_stage(9)
            live.update(self.progress_tracker.create_progress_display())
            config = self._create_mkdocs_config(project_analysis)
            self._write_mkdocs_config(config)
            
            # 完成
            self.progress_tracker.current_stage_index = self.progress_tracker.total_stages
            self.progress_tracker.current_stage = "✅ 网站生成完成！"
            live.update(self.progress_tracker.create_progress_display())
            time.sleep(1)  # 让用户看到完成状态
        
        self.console.print(f"\n[bold green]✅ 网站生成完成: {self.output_dir}[/bold green]")
        
    def _generate_pages_in_parallel(self, project_analysis: Dict, live) -> None:
        """并行生成所有页面以提升性能"""
        # 定义需要并行生成的页面任务
        page_tasks = [
            ('installation', 2, self._generate_installation_page),
            ('usage', 3, self._generate_usage_page), 
            ('examples', 5, self._generate_examples_page),
            ('architecture', 6, self._generate_architecture_page),
            ('contributing', 7, self._generate_contributing_page),
            ('changelog', 8, self._generate_changelog_page)
        ]
        
        # API文档单独处理，因为它有自己的并行逻辑
        self.progress_tracker.update_stage(4)
        live.update(self.progress_tracker.create_progress_display())
        self._generate_api_documentation(project_analysis)
        
        # 使用线程池并行生成其他页面
        with ThreadPoolExecutor(max_workers=20) as executor:
            # 提交所有任务
            future_to_task = {}
            for page_type, stage_index, generator_func in page_tasks:
                future = executor.submit(self._generate_page_wrapper, page_type, project_analysis, generator_func)
                future_to_task[future] = (page_type, stage_index)
            
            # 等待任务完成并更新进度
            completed_stages = set()
            for future in as_completed(future_to_task):
                page_type, stage_index = future_to_task[future]
                try:
                    future.result()
                    completed_stages.add(stage_index)
                    
                    # 更新进度到最新完成的阶段
                    max_completed_stage = max(completed_stages) if completed_stages else 2
                    self.progress_tracker.update_stage(max_completed_stage)
                    live.update(self.progress_tracker.create_progress_display())
                    
                    if self.verbose:
                        self.console.print(f"[green]✅ {page_type} 页面生成完成[/green]")
                        
                except Exception as e:
                    self.console.print(f"[red]❌ {page_type} 页面生成失败: {e}[/red]")
                    if self.debug:
                        import traceback
                        self.console.print(f"[red]{traceback.format_exc()}[/red]")
    
    def _generate_page_wrapper(self, page_type: str, project_analysis: Dict, generator_func) -> None:
        """页面生成包装器，用于并行执行"""
        try:
            generator_func(project_analysis)
        except Exception as e:
            # 保留原始异常信息，便于调试
            import traceback
            error_details = traceback.format_exc()
            raise Exception(f"生成{page_type}页面时发生错误: {str(e)}\n详细错误信息:\n{error_details}") from e
        
    def _create_directory_structure(self) -> None:
        """创建网站目录结构"""
        directories = [
            self.output_dir,
            self.docs_dir,
            self.api_dir,
            self.assets_dir,
            self.assets_dir / "images",
            self.assets_dir / "css",
            self.docs_dir / "assets",
            self.docs_dir / "assets" / "images"
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            
        # 复制项目资源文件到docs/assets目录
        self._copy_project_assets()
            
    def _analyze_project(self) -> Dict[str, Any]:
        """分析项目结构和内容"""
        # 加载gitignore模式
        ignore_patterns = load_gitignore_patterns(str(self.project_dir))
        
        analysis = {
            'structure': get_project_structure(str(self.project_dir), ignore_patterns),
            'dependencies': self._get_dependencies(),
            'functions': self._extract_functions(),
            'classes': self._extract_classes(),
            'modules': self._get_modules(),
            'entry_points': self._find_entry_points(),
            'git_info': self._get_git_info()
        }
        
        # 如果启用了RAG，进行深度代码分析
        if self.enable_rag and self.code_rag is not None:
            try:
                self.console.print("[blue]🔍 开始RAG代码分析...[/blue]")
                
                # 提取代码块
                code_blocks = self.code_rag.extract_code_blocks()
                
                # 构建向量嵌入
                if self.code_rag.build_embeddings():
                    # 获取代码统计信息
                    rag_stats = self.code_rag.get_code_statistics()
                    analysis['rag_stats'] = rag_stats
                    analysis['rag_enabled'] = True
                    
                    self.console.print(f"[green]✅ RAG分析完成: {len(code_blocks)} 个代码块[/green]")
                else:
                    analysis['rag_enabled'] = False
                    self.console.print("[yellow]⚠️  RAG向量化失败，使用传统分析[/yellow]")
                    
            except Exception as e:
                self.console.print(f"[red]❌ RAG分析失败: {e}[/red]")
                analysis['rag_enabled'] = False
        else:
            analysis['rag_enabled'] = False
        
        return analysis
        
    def _generate_home_page(self, analysis: Dict) -> None:
        """生成首页 - 使用README生成逻辑"""
        content = self._generate_readme_as_homepage(analysis)

        # 后处理：添加logo支持
        content = self._post_process_homepage_content(content)
        self._write_page('index.md', content)
        
    def _generate_installation_page(self, analysis: Dict) -> None:
        """生成安装页面"""
        content = self._generate_page_content('installation', analysis)
        self._write_page('installation.md', content)
        
    def _generate_usage_page(self, analysis: Dict) -> None:
        """生成使用说明页面"""
        content = self._generate_page_content('usage', analysis)
        self._write_page('usage.md', content)
        
    def _generate_api_documentation(self, analysis: Dict) -> None:
        """生成API文档 - 智能筛选有价值的函数"""
        # 筛选有价值的API
        valuable_apis = self.api_filter.filter_valuable_apis(
            analysis['functions'], 
            analysis['classes']
        )
        
        # 生成API索引页面
        api_index_content = self._generate_api_index(valuable_apis)
        self._write_page('api/index.md', api_index_content)
        
        # 为每个API生成独立页面
        self._generate_individual_api_pages(valuable_apis)
        
    def _generate_individual_api_pages(self, apis: List[Dict]) -> None:
        """为每个API生成独立的markdown页面"""
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = []
            
            for api in apis:
                future = executor.submit(self._generate_single_api_page, api)
                futures.append(future)
                
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    self.console.print(f"[red]API页面生成失败: {e}[/red]")
                    
    def _generate_single_api_page(self, api: Dict) -> None:
        """生成单个API的详细文档页面"""
        content = self.api_generator.generate_api_documentation(
            api['definition'],
            api['context'],
            api['metadata']
        )
        
        filename = f"api/{api['module']}/{api['name']}.md"
        self._write_page(filename, content)
        
    def _generate_examples_page(self, analysis: Dict) -> None:
        """生成示例页面"""
        content = self._generate_page_content('examples', analysis)
        self._write_page('examples.md', content)
        
    def _generate_architecture_page(self, analysis: Dict) -> None:
        """生成架构页面 - 并行生成图表和文档内容"""
        # 使用线程池并行生成架构图和文档内容
        with ThreadPoolExecutor(max_workers=20) as executor:
            # 提交两个并行任务
            drawio_future = executor.submit(self._generate_drawio_diagram, analysis)
            content_future = executor.submit(self._generate_page_content, 'architecture', analysis)
            
            # 等待两个任务完成
            drawio_content = drawio_future.result()
            content = content_future.result()
        
        # 保存架构图文件
        drawio_file_path = self.docs_dir / 'architecture_diagram.drawio'
        try:
            with open(drawio_file_path, 'w', encoding='utf-8') as f:
                f.write(drawio_content)
            if self.verbose:
                self.console.print(f"[green]架构图已保存到: {drawio_file_path}[/green]")
        except Exception as e:
            if self.verbose:
                self.console.print(f"[red]保存架构图失败: {e}[/red]")
        
        # 后处理：替换占位符为 markdown 图片引用语法
        content = self._post_process_architecture_content(content, drawio_content)
        
        self._write_page('architecture.md', content)
        
    def _generate_contributing_page(self, analysis: Dict) -> None:
        """生成贡献指南页面"""
        content = self._generate_page_content('contributing', analysis)
        self._write_page('contributing.md', content)
        
    def _generate_changelog_page(self, analysis: Dict) -> None:
        """生成更新日志页面"""
        content = self._generate_page_content('changelog', analysis)
        self._write_page('changelog.md', content)
        
    def _post_process_architecture_content(self, content: str, drawio_content: str) -> str:
        """
        后处理架构文档内容，将占位符替换为 markdown 图片引用语法
        
        Args:
            content: 原始的架构文档内容
            drawio_content: drawio XML 内容（此参数保留兼容性，但不再使用）
            
        Returns:
            str: 处理后的架构文档内容
        """
        # 直接替换为 markdown 图片引用语法
        markdown_reference = "![项目架构图](architecture_diagram.drawio)"
        
        # 替换占位符
        processed_content = content.replace('{{ARCHITECTURE_DIAGRAM_PLACEHOLDER}}', markdown_reference)
        
        return processed_content
    
    def _post_process_homepage_content(self, content: str) -> str:
        """
        后处理首页内容，处理logo图片路径
        
        Args:
            content: 原始的首页内容
            
        Returns:
            str: 处理后的首页内容
        """
        # 复制logo到assets目录
        logo_relative_path = self._copy_logo_to_assets()
        
        if logo_relative_path:
            # 替换logo路径为相对于website的正确路径
            # 将 images/logo.png 或 images/logo.svg 替换为正确的相对路径
            import re
            
            # 匹配各种logo引用格式（包括相对路径）
            logo_patterns = [
                r'<img src="(\.\./)?images/logo\.png"([^>]*)>',
                r'<img src="(\.\./)?images/logo\.svg"([^>]*)>',
                r'!\[([^\]]*)\]\((\.\./)?images/logo\.png\)',
                r'!\[([^\]]*)\]\((\.\./)?images/logo\.svg\)',
            ]
            
            for pattern in logo_patterns:
                if 'img src' in pattern:
                    # HTML格式 - 第二个捕获组是img标签的其他属性
                    content = re.sub(pattern, f'<img src="{logo_relative_path}"\\2>', content)
                else:
                    # Markdown格式 - 第一个捕获组是alt文本
                    content = re.sub(pattern, f'![\\1]({logo_relative_path})', content)
        
        return content
    
    def _copy_logo_to_assets(self) -> str:
        """
        复制项目根目录的logo到website/docs/assets目录，并调整大小
        
        Returns:
            str: logo的相对路径（相对于docs目录），如果没有找到logo则返回None
        """
        # 确保docs/assets/images目录存在
        docs_assets_images_dir = self.docs_dir / "assets" / "images"
        docs_assets_images_dir.mkdir(parents=True, exist_ok=True)
        
        # 查找项目根目录的logo文件
        logo_files = ['logo.svg', 'logo.png']
        project_images_dir = self.project_dir / "images"
        
        for logo_file in logo_files:
            logo_source = project_images_dir / logo_file
            if logo_source.exists():
                # 复制logo到docs/assets目录
                logo_dest = docs_assets_images_dir / logo_file
                try:
                    # 如果是PNG文件，尝试调整大小
                    if logo_file.endswith('.png'):
                        self._resize_and_copy_image(logo_source, logo_dest, max_height=100)
                    else:
                        shutil.copy2(logo_source, logo_dest)
                    
                    # 返回相对于docs目录的路径
                    relative_path = f"assets/images/{logo_file}"
                    if self.verbose:
                        self.console.print(f"[green]✅ Logo已复制到: {logo_dest}[/green]")
                        self.console.print(f"[green]📍 相对路径: {relative_path}[/green]")
                    return relative_path
                except Exception as e:
                    if self.verbose:
                        self.console.print(f"[yellow]⚠️  复制logo失败: {e}[/yellow]")
        
        if self.verbose:
            self.console.print(f"[yellow]⚠️  未找到logo文件 (查找路径: {project_images_dir})[/yellow]")
        return None

    def _resize_and_copy_image(self, source_path: Path, dest_path: Path, max_height: int = 100) -> None:
        """
        调整图片大小并复制
        
        Args:
            source_path: 源图片路径
            dest_path: 目标图片路径
            max_height: 最大高度（像素）
        """
        try:
            from PIL import Image
            
            # 打开图片
            with Image.open(source_path) as img:
                # 获取原始尺寸
                original_width, original_height = img.size
                
                # 如果高度超过最大值，按比例缩放
                if original_height > max_height:
                    ratio = max_height / original_height
                    new_width = int(original_width * ratio)
                    new_height = max_height
                    
                    # 调整大小
                    resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    resized_img.save(dest_path, optimize=True, quality=95)
                    
                    if self.verbose:
                        self.console.print(f"[green]🔧 图片已调整大小: {original_width}x{original_height} -> {new_width}x{new_height}[/green]")
                else:
                    # 直接复制
                    img.save(dest_path, optimize=True, quality=95)
                    
        except ImportError:
            # 如果没有安装PIL，直接复制
            shutil.copy2(source_path, dest_path)
            if self.verbose:
                self.console.print(f"[yellow]⚠️  PIL未安装，无法调整图片大小，直接复制[/yellow]")
        except Exception as e:
            # 如果调整大小失败，直接复制
            shutil.copy2(source_path, dest_path)
            if self.verbose:
                self.console.print(f"[yellow]⚠️  图片调整失败，直接复制: {e}[/yellow]")

    def _copy_project_assets(self) -> None:
        """
        复制项目中的所有资源文件到docs/assets目录
        包括logo、screenshot等图片资源
        """
        # 确保docs/assets/images目录存在
        docs_assets_images_dir = self.docs_dir / "assets" / "images"
        docs_assets_images_dir.mkdir(parents=True, exist_ok=True)
        
        # 查找项目根目录的images文件夹
        project_images_dir = self.project_dir / "images"
        
        if project_images_dir.exists():
            # 复制所有图片文件
            image_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp']
            
            for image_file in project_images_dir.iterdir():
                if image_file.is_file() and image_file.suffix.lower() in image_extensions:
                    dest_file = docs_assets_images_dir / image_file.name
                    
                    try:
                        # 对PNG和JPG文件进行大小调整
                        if image_file.suffix.lower() in ['.png', '.jpg', '.jpeg']:
                            # 根据文件名判断是否需要特殊处理
                            if 'logo' in image_file.name.lower():
                                self._resize_and_copy_image(image_file, dest_file, max_height=100)
                            elif 'screenshot' in image_file.name.lower():
                                self._resize_and_copy_image(image_file, dest_file, max_height=400)
                            else:
                                self._resize_and_copy_image(image_file, dest_file, max_height=300)
                        else:
                            # SVG等矢量图直接复制
                            shutil.copy2(image_file, dest_file)
                        
                        if self.verbose:
                            self.console.print(f"[green]📁 已复制资源: {image_file.name}[/green]")
                            
                    except Exception as e:
                        if self.verbose:
                            self.console.print(f"[yellow]⚠️  复制资源失败 {image_file.name}: {e}[/yellow]")
        
        # 查找项目根目录的其他常见图片文件
        common_image_files = ['logo.png', 'logo.svg', 'screenshot.png', 'banner.png', 'icon.png']
        
        for image_name in common_image_files:
            image_file = self.project_dir / image_name
            if image_file.exists():
                dest_file = docs_assets_images_dir / image_name
                
                try:
                    if image_name.endswith('.png') or image_name.endswith('.jpg'):
                        if 'logo' in image_name:
                            self._resize_and_copy_image(image_file, dest_file, max_height=100)
                        elif 'screenshot' in image_name:
                            self._resize_and_copy_image(image_file, dest_file, max_height=400)
                        else:
                            self._resize_and_copy_image(image_file, dest_file, max_height=300)
                    else:
                        shutil.copy2(image_file, dest_file)
                    
                    if self.verbose:
                        self.console.print(f"[green]📁 已复制根目录资源: {image_name}[/green]")
                        
                except Exception as e:
                    if self.verbose:
                        self.console.print(f"[yellow]⚠️  复制根目录资源失败 {image_name}: {e}[/yellow]")

    def _write_mkdocs_config(self, config: Dict) -> None:
        """写入MkDocs配置文件"""
        config_path = self.output_dir / "mkdocs.yml"
        
        if yaml is None:
            # 如果没有安装PyYAML，使用简单的字符串格式
            yaml_content = self._dict_to_yaml_string(config)
            with open(config_path, 'w', encoding='utf-8') as f:
                f.write(yaml_content)
            return
            
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
        
    def _generate_page_content(self, page_type: str, analysis: Dict) -> str:
        """使用LLM生成页面内容"""
        if self.debug:
            # Debug模式下跳过大模型调用，返回简单的占位符内容
            self.console.print(f"[yellow]生成 {page_type} 页面 (debug模式 - 跳过大模型调用)...[/yellow]")
            return self._generate_debug_page_content(page_type, analysis)
        
        # 检查model_client是否可用
        if self.model_client is None:
            self.console.print(f"[yellow]⚠️  模型客户端不可用，使用debug模式生成 {page_type} 页面[/yellow]")
            return self._generate_debug_page_content(page_type, analysis)
        
        # 生成基础prompt
        base_prompt = self._create_page_prompt(page_type, analysis)
        
        # 如果启用RAG，使用RAG增强prompt
        if self.enable_rag and self.code_rag is not None and analysis.get('rag_enabled', False):
            # 根据页面类型生成查询
            query = self._generate_rag_query(page_type, analysis)
            
            # 使用RAG增强prompt
            enhanced_prompt = self.code_rag.generate_enhanced_prompt(
                base_prompt=base_prompt,
                query=query,
                max_context_blocks=8
            )
            
            if self.verbose:
                self.console.print(f"[green]🔍 使用RAG增强 {page_type} 页面prompt[/green]")
            
            prompt = enhanced_prompt
        else:
            prompt = base_prompt
        
        # 在verbose模式下打印prompt
        if self.verbose:
            self.console.print(f"\n[bold cyan]📝 生成 {page_type} 页面的Prompt:[/bold cyan]")
            self.console.print(Panel(prompt, title=f"{page_type.upper()} Prompt", border_style="cyan"))
            self.console.print("\n")
        
        content = self.model_client.generate_text(prompt)
        return self._format_markdown_content(content)
    
    def _generate_rag_query(self, page_type: str, analysis: Dict) -> str:
        """根据页面类型生成RAG查询"""
        project_name = analysis.get('git_info', {}).get('repo_name', Path(self.project_dir).name)
        
        queries = {
            'home': f"项目 {project_name} 主要功能 核心特性 入口点 主要类和函数",
            'installation': f"项目 {project_name} 安装 依赖 配置 setup 初始化",
            'usage': f"项目 {project_name} 使用方法 API 接口 主要函数 示例代码",
            'examples': f"项目 {project_name} 示例 演示 用法 代码片段 实际应用",
            'architecture': f"项目 {project_name} 架构 设计 模块结构 类关系 组件",
            'contributing': f"项目 {project_name} 开发 贡献 测试 代码规范 工具",
            'changelog': f"项目 {project_name} 版本 更新 变更 新功能 修复"
        }
        
        return queries.get(page_type, f"项目 {project_name} {page_type}")
        
    def _generate_debug_page_content(self, page_type: str, analysis: Dict) -> str:
        """在debug模式下生成简单的占位符页面内容"""
        project_name = self.project_dir.name
        
        debug_contents = {
            'installation': f"""# 安装指南

## 系统要求

- Python 3.7+
- pip

## 安装步骤

```bash
# 克隆仓库
git clone <repository-url>
cd {project_name}

# 安装依赖
pip install -r requirements.txt
```

*注意：此页面在debug模式下生成，未使用AI生成内容。*
""",
            'usage': f"""# 使用说明

## 快速开始

```python
# 导入模块
from {project_name} import main

# 运行示例
main()
```

## 基本用法

详细的使用说明请参考项目文档。

*注意：此页面在debug模式下生成，未使用AI生成内容。*
""",
            'examples': f"""# 示例

## 基本示例

```python
# 示例代码
print("Hello, {project_name}!")
```

## 更多示例

更多示例请查看项目的examples目录。

*注意：此页面在debug模式下生成，未使用AI生成内容。*
""",
            'architecture': f"""# 项目架构

## 概述

{project_name} 项目的架构设计。

## 主要组件

- 核心模块
- 工具模块
- 配置模块

*注意：此页面在debug模式下生成，未使用AI生成内容。*
""",
            'contributing': f"""# 贡献指南

## 如何贡献

1. Fork 项目
2. 创建功能分支
3. 提交更改
4. 创建 Pull Request

## 开发环境

请确保安装了所有开发依赖。

*注意：此页面在debug模式下生成，未使用AI生成内容。*
""",
            'changelog': f"""# 更新日志

## [未发布]

### 新增
- 新功能开发中

### 修复
- Bug修复

*注意：此页面在debug模式下生成，未使用AI生成内容。*
""",
            'home': f"""# {project_name}

欢迎使用 {project_name}！

## 简介

这是一个Python项目。

## 特性

- 功能1
- 功能2
- 功能3

*注意：此页面在debug模式下生成，未使用AI生成内容。*
"""
        }
        
        return debug_contents.get(page_type, f"""# {page_type.title()}

此页面内容待完善。

*注意：此页面在debug模式下生成，未使用AI生成内容。*
""")
        
    def _format_markdown_content(self, content: str) -> str:
        """格式化markdown内容，避免前端渲染错误"""
        # 移除多余的空行
        lines = content.split('\n')
        formatted_lines = []
        prev_empty = False
        
        for line in lines:
            line = line.rstrip()  # 移除行尾空格
            is_empty = len(line.strip()) == 0
            
            # 避免连续的空行
            if is_empty and prev_empty:
                continue
                
            formatted_lines.append(line)
            prev_empty = is_empty
            
        # 确保代码块正确闭合
        content = '\n'.join(formatted_lines)
        
        # 修复代码块
        content = self._fix_code_blocks(content)
        
        # 确保文档以换行符结尾
        if not content.endswith('\n'):
            content += '\n'
            
        return content
    
    def _generate_readme_as_homepage(self, analysis: Dict) -> str:
        """使用README生成逻辑生成首页内容"""
        try:
            self.console.print("[bold cyan]📝 正在生成README内容作为首页...[/bold cyan]")
            
            # 创建readmex实例，启用silent模式避免交互式输入
            from readmex.core import readmex
            readme_generator = readmex(str(self.project_dir), silent=True, debug=self.debug)
            
            # 设置基本配置
            readme_generator.output_dir = str(self.project_dir / "temp_readme_output")
            os.makedirs(readme_generator.output_dir, exist_ok=True)
            
            # 加载配置
            readme_generator._load_configuration()
            
            # 获取项目信息
            readme_generator._get_git_info()
            readme_generator._get_user_info()
            readme_generator._get_project_meta_info()
            
            # 分析项目
            structure = readme_generator._get_project_structure()
            dependencies = readme_generator._get_project_dependencies()
            descriptions = readme_generator._get_script_descriptions()
            
            # 自动生成项目描述等信息
            if not readme_generator.config["project_description"]:
                readme_generator.config["project_description"] = readme_generator._generate_project_description(structure, dependencies, descriptions)
            
            if not readme_generator.config["entry_file"]:
                readme_generator.config["entry_file"] = readme_generator._generate_entry_file(structure, dependencies, descriptions)
            
            if not readme_generator.config["key_features"]:
                readme_generator.config["key_features"] = readme_generator._generate_key_features(structure, dependencies, descriptions)
            
            if not readme_generator.config["additional_info"]:
                readme_generator.config["additional_info"] = readme_generator._generate_additional_info(structure, dependencies, descriptions)
            
            # 生成README内容（传递logo路径以保留logo）
            # 查找项目中的logo文件
            logo_path = None
            project_images_dir = self.project_dir / "images"
            for logo_file in ['logo.svg', 'logo.png']:
                logo_source = project_images_dir / logo_file
                if logo_source.exists():
                    logo_path = str(logo_source)
                    break
            
            # 如果没有找到现有logo且非debug模式，生成logo
            if not logo_path and not self.debug:
                try:
                    from readmex.utils.logo_generator import generate_logo
                    # 确保images目录存在
                    project_images_dir.mkdir(parents=True, exist_ok=True)
                    # 生成logo到项目images目录
                    logo_path = generate_logo(str(self.project_dir), descriptions, self.model_client, self.console)
                    if self.verbose and logo_path:
                        self.console.print(f"[green]✅ Logo已生成到: {logo_path}[/green]")
                except Exception as e:
                    if self.verbose:
                        self.console.print(f"[yellow]⚠️  Logo生成失败: {e}[/yellow]")
            
            readme_content = readme_generator._generate_readme_content(structure, dependencies, descriptions, logo_path)
            
            # 清理临时目录
            if os.path.exists(readme_generator.output_dir):
                shutil.rmtree(readme_generator.output_dir)
            
            self.console.print("[green]✅ README内容生成完成[/green]")
            
            # 在verbose模式下显示生成的README内容
            if self.verbose:
                self.console.print(f"\n[bold cyan]📝 生成的README内容作为首页:[/bold cyan]")
                self.console.print(Panel(readme_content[:500] + "..." if len(readme_content) > 500 else readme_content, 
                                        title="README Homepage Content", border_style="cyan"))
                self.console.print("\n")
            
            return readme_content
            
        except Exception as e:
            self.console.print(f"[red]使用README生成逻辑失败，回退到原始方法: {e}[/red]")
            # 回退到原始的页面生成方法
            return self._generate_page_content('home', analysis)
        
    def _fix_code_blocks(self, content: str) -> str:
        """修复代码块格式"""
        lines = content.split('\n')
        fixed_lines = []
        in_code_block = False
        code_block_lang = ''
        
        for line in lines:
            # 检测代码块开始
            if line.strip().startswith('```'):
                if not in_code_block:
                    in_code_block = True
                    code_block_lang = line.strip()[3:].strip()
                    fixed_lines.append(f'```{code_block_lang}')
                else:
                    in_code_block = False
                    fixed_lines.append('```')
            else:
                fixed_lines.append(line)
                
        # 如果代码块没有正确闭合，添加闭合标记
        if in_code_block:
            fixed_lines.append('```')
            
        return '\n'.join(fixed_lines)
    
    def _write_page(self, filename: str, content: str) -> None:
        """写入页面文件"""
        file_path = self.docs_dir / filename
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
            
    # 辅助方法
    def _get_dependencies(self) -> Dict:
        """获取项目依赖"""
        dependencies = {'python': [], 'npm': [], 'other': []}
        
        # 检查Python依赖
        python_deps = set()  # 使用set避免重复
        
        # 按优先级检查依赖文件
        dep_files = [
            ('pyproject.toml', 'pyproject'),
            ('requirements.txt', 'requirements'),
            ('setup.py', 'setup'),
            ('Pipfile', 'pipfile'),
            ('setup.cfg', 'setup_cfg'),
            ('environment.yml', 'conda'),
            ('poetry.lock', 'poetry')
        ]
        
        for filename, file_type in dep_files:
            file_path = self.project_dir / filename
            if file_path.exists():
                try:
                    parsed_deps = self._parse_python_deps(file_path)
                    if parsed_deps:
                        python_deps.update(parsed_deps)
                        if self.verbose:
                            self.console.print(f"[green]Found {len(parsed_deps)} dependencies in {filename}[/green]")
                except Exception as e:
                    if self.verbose:
                        self.console.print(f"[yellow]Warning: Could not parse {filename}: {e}[/yellow]")
        
        # 如果没有找到依赖文件，尝试从代码中推断
        if not python_deps:
            inferred_deps = self._infer_dependencies_from_code()
            python_deps.update(inferred_deps)
            if inferred_deps and self.verbose:
                self.console.print(f"[blue]Inferred {len(inferred_deps)} dependencies from code analysis[/blue]")
        
        dependencies['python'] = sorted(list(python_deps))
                
        # 检查Node.js依赖
        for js_file in ['package.json', 'package-lock.json', 'yarn.lock']:
            js_path = self.project_dir / js_file
            if js_path.exists():
                try:
                    npm_deps = self._parse_npm_deps(js_path)
                    dependencies['npm'].extend(npm_deps)
                    if npm_deps and self.verbose:
                        self.console.print(f"[green]Found {len(npm_deps)} npm dependencies in {js_file}[/green]")
                    break  # 只解析第一个找到的文件
                except Exception as e:
                    if self.verbose:
                        self.console.print(f"[yellow]Warning: Could not parse {js_file}: {e}[/yellow]")
        
        # 检查其他类型的依赖
        other_deps = self._detect_other_dependencies()
        dependencies['other'] = other_deps
        
        return dependencies
        
    def _extract_functions(self) -> List[Dict]:
        """提取项目中的函数"""
        functions = []
        python_files = list(self.project_dir.rglob('*.py'))
        
        for file_path in python_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                tree = ast.parse(content)
                file_functions = self._extract_functions_from_ast(tree, file_path, content)
                functions.extend(file_functions)
                
            except Exception as e:
                self.console.print(f"[yellow]Warning: Could not parse {file_path}: {e}[/yellow]")
                
        return functions
        
    def _extract_classes(self) -> List[Dict]:
        """提取项目中的类"""
        classes = []
        python_files = list(self.project_dir.rglob('*.py'))
        
        for file_path in python_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                tree = ast.parse(content)
                file_classes = self._extract_classes_from_ast(tree, file_path, content)
                classes.extend(file_classes)
                
            except Exception as e:
                self.console.print(f"[yellow]Warning: Could not parse {file_path}: {e}[/yellow]")
                
        return classes
        
    def _get_modules(self) -> List[str]:
        """获取项目模块列表"""
        modules = []
        python_files = list(self.project_dir.rglob('*.py'))
        
        for file_path in python_files:
            relative_path = file_path.relative_to(self.project_dir)
            module_path = str(relative_path).replace('/', '.').replace('\\', '.').replace('.py', '')
            if not module_path.startswith('.'):
                modules.append(module_path)
                
        return sorted(modules)
        
    def _find_entry_points(self) -> List[str]:
        """查找项目入口点"""
        entry_points = []
        
        # 检查pyproject.toml中的脚本
        pyproject_path = self.project_dir / 'pyproject.toml'
        if pyproject_path.exists():
            entry_points.extend(self._parse_pyproject_scripts(pyproject_path))
            
        # 检查setup.py中的入口点
        setup_path = self.project_dir / 'setup.py'
        if setup_path.exists():
            entry_points.extend(self._parse_setup_scripts(setup_path))
            
        # 检查常见的主文件
        main_files = ['main.py', 'app.py', '__main__.py', 'cli.py']
        for main_file in main_files:
            main_path = self.project_dir / main_file
            if main_path.exists():
                entry_points.append(main_file)
                
        return entry_points
        
    def _get_git_info(self) -> Dict:
        """获取Git信息"""
        git_info = {}
        
        try:
            import subprocess
            
            # 获取远程仓库URL
            result = subprocess.run(
                ['git', 'remote', 'get-url', 'origin'],
                cwd=self.project_dir,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                git_info['remote_url'] = result.stdout.strip()
                
                # 解析GitHub信息
                github_match = re.search(
                    r'github\.com[:/]([^/]+)/([^/\.]+)(?:\.git)?/?$',
                    git_info['remote_url']
                )
                
                if github_match:
                    git_info['github_username'] = github_match.group(1)
                    git_info['repo_name'] = github_match.group(2)
                    
        except Exception as e:
            self.console.print(f"[yellow]Warning: Could not get git info: {e}[/yellow]")
            
        return git_info
    
    def _get_git_commit_history(self, limit: int = 20) -> List[Dict]:
        """获取增强的Git提交历史，包含文件变更统计"""
        commits = []
        
        try:
            import subprocess
            
            # 获取最近的提交历史，包含文件变更统计
            result = subprocess.run(
                ['git', 'log', f'--max-count={limit}', '--pretty=format:%H|%an|%ae|%ad|%s', '--date=short', '--stat', '--oneline'],
                cwd=self.project_dir,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                i = 0
                while i < len(lines):
                    line = lines[i]
                    if '|' in line and len(line.split('|')) >= 5:
                        parts = line.split('|', 4)
                        if len(parts) == 5:
                            commit_hash = parts[0][:8]
                            
                            # 获取该提交的详细文件变更信息
                            stat_result = subprocess.run(
                                ['git', 'show', '--stat', '--format=', parts[0]],
                                cwd=self.project_dir,
                                capture_output=True,
                                text=True
                            )
                            
                            files_changed = []
                            insertions = 0
                            deletions = 0
                            
                            if stat_result.returncode == 0:
                                stat_lines = stat_result.stdout.strip().split('\n')
                                for stat_line in stat_lines:
                                    if '|' in stat_line and ('+' in stat_line or '-' in stat_line):
                                        file_info = stat_line.split('|')
                                        if len(file_info) >= 2:
                                            filename = file_info[0].strip()
                                            changes = file_info[1].strip()
                                            files_changed.append({
                                                'file': filename,
                                                'changes': changes
                                            })
                                    elif 'insertion' in stat_line or 'deletion' in stat_line:
                                        # 解析插入和删除行数
                                        import re
                                        ins_match = re.search(r'(\d+) insertion', stat_line)
                                        del_match = re.search(r'(\d+) deletion', stat_line)
                                        if ins_match:
                                            insertions = int(ins_match.group(1))
                                        if del_match:
                                            deletions = int(del_match.group(1))
                            
                            # 分析提交类型（基于 Conventional Commits）
                            commit_type = self._analyze_commit_type(parts[4])
                            
                            commits.append({
                                'hash': commit_hash,
                                'author': parts[1],
                                'email': parts[2],
                                'date': parts[3],
                                'message': parts[4],
                                'files_changed': files_changed,
                                'insertions': insertions,
                                'deletions': deletions,
                                'type': commit_type,
                                'is_breaking': self._is_breaking_change(parts[4])
                            })
                    i += 1
                            
        except Exception as e:
            self.console.print(f"[yellow]Warning: Could not get git commit history: {e}[/yellow]")
            
        return commits
    
    def _get_git_contributors(self) -> List[Dict]:
        """获取Git贡献者信息"""
        contributors = []
        
        try:
            import subprocess
            
            # 获取贡献者统计
            result = subprocess.run(
                ['git', 'shortlog', '-sn', '--all'],
                cwd=self.project_dir,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if line:
                        parts = line.strip().split('\t', 1)
                        if len(parts) == 2:
                            commit_count = int(parts[0])
                            author_name = parts[1]
                            
                            # 获取作者邮箱
                            email_result = subprocess.run(
                                ['git', 'log', '--author', author_name, '--pretty=format:%ae', '-1'],
                                cwd=self.project_dir,
                                capture_output=True,
                                text=True
                            )
                            
                            email = email_result.stdout.strip() if email_result.returncode == 0 else ''
                            
                            contributors.append({
                                'name': author_name,
                                'email': email,
                                'commits': commit_count,
                                'avatar_url': f'https://github.com/{author_name}.png' if email else ''
                            })
                            
        except Exception as e:
            self.console.print(f"[yellow]Warning: Could not get git contributors: {e}[/yellow]")
            
        return contributors
    
    def _analyze_commit_statistics(self, commits: List[Dict]) -> Dict[str, int]:
        """分析提交统计信息"""
        stats = {}
        
        for commit in commits:
            commit_type = commit.get('type', 'other')
            stats[commit_type] = stats.get(commit_type, 0) + 1
        
        return stats
    
    def _analyze_commit_type(self, message: str) -> str:
        """分析提交类型（基于 Conventional Commits 规范）"""
        message_lower = message.lower()
        
        # Conventional Commits 类型映射
        type_patterns = {
            'feat': ['feat:', 'feature:', 'add:', 'new:'],
            'fix': ['fix:', 'bug:', 'hotfix:', 'patch:'],
            'docs': ['docs:', 'doc:', 'documentation:'],
            'style': ['style:', 'format:', 'lint:'],
            'refactor': ['refactor:', 'refact:', 'restructure:'],
            'test': ['test:', 'tests:', 'testing:'],
            'chore': ['chore:', 'build:', 'ci:', 'deps:'],
            'perf': ['perf:', 'performance:', 'optimize:'],
            'revert': ['revert:', 'rollback:']
        }
        
        for commit_type, patterns in type_patterns.items():
            for pattern in patterns:
                if message_lower.startswith(pattern):
                    return commit_type
        
        # 基于关键词的启发式分析
        if any(word in message_lower for word in ['add', 'new', 'create', 'implement']):
            return 'feat'
        elif any(word in message_lower for word in ['fix', 'bug', 'error', 'issue']):
            return 'fix'
        elif any(word in message_lower for word in ['update', 'change', 'modify']):
            return 'refactor'
        elif any(word in message_lower for word in ['remove', 'delete', 'clean']):
            return 'chore'
        
        return 'other'
    
    def _is_breaking_change(self, message: str) -> bool:
        """检测是否为破坏性变更"""
        breaking_indicators = [
            'BREAKING CHANGE',
            'breaking change',
            'breaking:',
            '!:',  # Conventional Commits 的破坏性变更标记
            'major:',
            'incompatible'
        ]
        
        return any(indicator in message for indicator in breaking_indicators)
    
    def _get_git_tags(self) -> List[Dict]:
        """获取Git标签信息"""
        tags = []
        
        try:
            import subprocess
            
            # 获取标签列表，按日期排序
            result = subprocess.run(
                ['git', 'tag', '-l', '--sort=-creatordate', '--format=%(refname:short)|%(creatordate:short)|%(subject)'],
                cwd=self.project_dir,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if line:
                        parts = line.split('|', 2)
                        if len(parts) >= 2:
                            tags.append({
                                'name': parts[0],
                                'date': parts[1],
                                'message': parts[2] if len(parts) > 2 else ''
                            })
                            
        except Exception as e:
            if self.verbose:
                self.console.print(f"[yellow]Warning: Could not get git tags: {e}[/yellow]")
            
        return tags
    
    def _validate_drawio_content(self, content: str) -> bool:
        """
        验证drawio内容是否完整
        
        Args:
            content: drawio XML内容
            
        Returns:
            bool: 是否完整有效
        """
        if not content or not content.strip():
            return False
            
        # 检查基本的XML结构
        required_tags = ['<mxfile', '</mxfile>', '<diagram', '</diagram>', '<mxGraphModel', '</mxGraphModel>']
        for tag in required_tags:
            if tag not in content:
                return False
                
        # 检查是否被截断（通常截断的文件会缺少结束标签）
        if not content.strip().endswith('</mxfile>'):
            return False
            
        # 检查内容长度（太短可能不完整）
        if len(content.strip()) < 500:
            return False
            
        # 尝试基本的XML解析验证
        try:
            import xml.etree.ElementTree as ET
            ET.fromstring(content)
            return True
        except ET.ParseError:
            return False
        except Exception:
            # 如果没有xml模块或其他错误，使用基本验证
            return True
    
    def _generate_drawio_diagram(self, analysis: Dict) -> str:
        """
        生成架构图的 drawio 代码（带重试逻辑）
        
        Args:
            analysis: 项目分析结果
            
        Returns:
            str: drawio XML 代码
        """
        git_info = analysis.get('git_info', {})
        project_name = git_info.get('repo_name', Path(self.project_dir).name)
        modules = analysis.get('modules', [])
        functions = analysis.get('functions', [])
        classes = analysis.get('classes', [])
        dependencies = analysis.get('dependencies', {})
        
        # 准备脚本简介信息
        script_descriptions_file = self.project_dir / "script_descriptions.json"
        script_descriptions = {}
        if script_descriptions_file.exists():
            try:
                with open(script_descriptions_file, 'r', encoding='utf-8') as f:
                    script_descriptions = json.load(f)
            except Exception as e:
                if self.verbose:
                    self.console.print(f"[yellow]Warning: 无法读取脚本描述文件: {e}[/yellow]")
        
        # 构建架构图生成的提示词
        architecture_info = f"""
项目架构信息：
- 项目名称: {project_name}
- 模块数量: {len(modules)}
- 函数数量: {len(functions)}
- 类数量: {len(classes)}
- 主要依赖: {list(dependencies.keys())[:10]}

模块列表:
{chr(10).join([f"- {module}" for module in modules[:15]])}

主要类:
{chr(10).join([f"- {cls}" for cls in classes[:10]])}

脚本描述:
{json.dumps(script_descriptions, ensure_ascii=False, indent=2)[:1000]}...
"""
        
        prompt = f"""
请基于以下项目信息生成一个架构图的 draw.io XML 代码。

{architecture_info}

要求：
1. 生成完整的 draw.io XML 格式代码
2. 包含项目的主要模块和组件
3. 显示模块之间的依赖关系
4. 使用清晰的布局和颜色区分不同类型的组件
5. 包含数据流向和交互关系
6. 适合在 MkDocs 中使用 drawio 插件显示
7. 确保XML格式完整，包含所有必要的开始和结束标签

请直接返回完整的 draw.io XML 代码，不要包含其他解释文字。
"""
        
        # 重试逻辑
        max_retries = 3
        for attempt in range(max_retries):
            try:
                if self.verbose:
                    if attempt == 0:
                        self.console.print("[blue]正在生成架构图...[/blue]")
                    else:
                        self.console.print(f"[yellow]架构图生成重试 {attempt}/{max_retries-1}...[/yellow]")
                
                drawio_code = self.model_client.get_answer(prompt)
                
                # 验证生成的内容是否完整
                if self._validate_drawio_content(drawio_code):
                    if self.verbose and attempt > 0:
                        self.console.print(f"[green]架构图生成成功（重试 {attempt} 次后）[/green]")
                    return drawio_code
                else:
                    if self.verbose:
                        self.console.print(f"[yellow]生成的架构图不完整或被截断，准备重试...[/yellow]")
                    
                    # 如果是最后一次尝试，记录详细信息
                    if attempt == max_retries - 1:
                        if self.verbose:
                            self.console.print(f"[red]架构图验证失败详情：[/red]")
                            self.console.print(f"[red]- 内容长度: {len(drawio_code) if drawio_code else 0}[/red]")
                            self.console.print(f"[red]- 内容预览: {drawio_code[:200] if drawio_code else 'None'}...[/red]")
                    continue
                    
            except Exception as e:
                if self.verbose:
                    self.console.print(f"[red]生成架构图失败 (尝试 {attempt + 1}/{max_retries}): {e}[/red]")
                
                # 如果是最后一次尝试，返回默认架构图
                if attempt == max_retries - 1:
                    if self.verbose:
                        self.console.print(f"[yellow]所有重试均失败，使用默认架构图[/yellow]")
                    return self._get_default_drawio_diagram(project_name)
        
        # 如果所有重试都失败，返回默认架构图
        if self.verbose:
            self.console.print(f"[yellow]架构图生成验证失败，使用默认架构图[/yellow]")
        return self._get_default_drawio_diagram(project_name)
    
    def _get_default_drawio_diagram(self, project_name: str) -> str:
        """
        获取默认的 drawio 架构图
        
        Args:
            project_name: 项目名称
            
        Returns:
            str: 默认的 drawio XML 代码
        """
        return f'''<mxfile host="app.diagrams.net" modified="2024-01-01T00:00:00.000Z" agent="5.0" version="22.1.16">
  <diagram name="Architecture" id="architecture">
    <mxGraphModel dx="1422" dy="794" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="827" pageHeight="1169" math="0" shadow="0">
      <root>
        <mxCell id="0" />
        <mxCell id="1" parent="0" />
        <mxCell id="2" value="{project_name}" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;fontSize=16;fontStyle=1" vertex="1" parent="1">
          <mxGeometry x="300" y="100" width="200" height="60" as="geometry" />
        </mxCell>
        <mxCell id="3" value="Core Module" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#d5e8d4;strokeColor=#82b366" vertex="1" parent="1">
          <mxGeometry x="150" y="250" width="120" height="60" as="geometry" />
        </mxCell>
        <mxCell id="4" value="API Module" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#d5e8d4;strokeColor=#82b366" vertex="1" parent="1">
          <mxGeometry x="350" y="250" width="120" height="60" as="geometry" />
        </mxCell>
        <mxCell id="5" value="Utils Module" style="rounded=1;whiteSpace=wrap;html=1;fillColor=#d5e8d4;strokeColor=#82b366" vertex="1" parent="1">
          <mxGeometry x="550" y="250" width="120" height="60" as="geometry" />
        </mxCell>
        <mxCell id="6" value="" style="endArrow=classic;html=1;rounded=0;exitX=0.25;exitY=1;exitDx=0;exitDy=0;entryX=0.5;entryY=0;entryDx=0;entryDy=0" edge="1" parent="1" source="2" target="3">
          <mxGeometry width="50" height="50" relative="1" as="geometry">
            <mxPoint x="390" y="300" as="sourcePoint" />
            <mxPoint x="440" y="250" as="targetPoint" />
          </mxGeometry>
        </mxCell>
        <mxCell id="7" value="" style="endArrow=classic;html=1;rounded=0;exitX=0.5;exitY=1;exitDx=0;exitDy=0;entryX=0.5;entryY=0;entryDx=0;entryDy=0" edge="1" parent="1" source="2" target="4">
          <mxGeometry width="50" height="50" relative="1" as="geometry">
            <mxPoint x="390" y="300" as="sourcePoint" />
            <mxPoint x="440" y="250" as="targetPoint" />
          </mxGeometry>
        </mxCell>
        <mxCell id="8" value="" style="endArrow=classic;html=1;rounded=0;exitX=0.75;exitY=1;exitDx=0;exitDy=0;entryX=0.5;entryY=0;entryDx=0;entryDy=0" edge="1" parent="1" source="2" target="5">
          <mxGeometry width="50" height="50" relative="1" as="geometry">
            <mxPoint x="390" y="300" as="sourcePoint" />
            <mxPoint x="440" y="250" as="targetPoint" />
          </mxGeometry>
        </mxCell>
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>'''
        
    def _convert_git_url_to_https(self, git_url: str) -> str:
        """将git@格式的URL转换为https格式"""
        if not git_url:
            return ''
            
        # 如果已经是https格式，直接返回（去掉.git后缀）
        if git_url.startswith('https://'):
            return git_url.rstrip('.git')
            
        # 转换git@格式到https格式
        if git_url.startswith('git@'):
            # git@github.com:user/repo.git -> https://github.com/user/repo
            import re
            match = re.match(r'git@([^:]+):(.+?)(?:\.git)?/?$', git_url)
            if match:
                host, path = match.groups()
                return f'https://{host}/{path}'
                
        # 如果是其他格式，尝试直接返回
        return git_url.rstrip('.git')
        
    def _generate_api_index(self, apis: List[Dict]) -> str:
        """生成API索引页面"""
        content = "# API 文档\n\n"
        content += "本页面包含项目的主要API文档。\n\n"
        
        # 按模块分组
        modules = {}
        for api in apis:
            module = api['module']
            if module not in modules:
                modules[module] = []
            modules[module].append(api)
            
        # 生成索引
        for module, module_apis in sorted(modules.items()):
            content += f"## {module}\n\n"
            
            for api in module_apis:
                api_type = api['type']
                api_name = api['name']
                link = f"[{api_name}]({module}/{api_name}.md)"
                
                if api_type == 'class':
                    content += f"- 🏛️ {link} - 类\n"
                else:
                    content += f"- 🔧 {link} - 函数\n"
                    
            content += "\n"
            
        return content
        
    def _create_page_prompt(self, page_type: str, analysis: Dict) -> str:
        """创建页面生成的提示词 - 路由到具体的页面prompt方法"""
        prompt_methods = {
            'home': self._create_home_prompt,
            'installation': self._create_installation_prompt,
            'usage': self._create_usage_prompt,
            'examples': self._create_examples_prompt,
            'architecture': self._create_architecture_prompt,
            'contributing': self._create_contributing_prompt,
            'changelog': self._create_changelog_prompt
        }
        
        method = prompt_methods.get(page_type)
        if method:
            return method(analysis)
        else:
            return "请生成相关文档。"
    
    def _create_home_prompt(self, analysis: Dict) -> str:
        """
        创建首页文档生成的提示词
        
        所需输入信息：
        - analysis['git_info']['repo_name']: 项目名称
        - analysis['git_info']: Git仓库信息
        - analysis['modules']: 模块列表
        - analysis['functions']: 函数列表
        - analysis['classes']: 类列表
        - analysis['dependencies']: 依赖信息
        - analysis['entry_points']: 入口点信息
        - self.project_dir: 项目路径
        """
        git_info = analysis.get('git_info', {})
        project_name = git_info.get('repo_name', Path(self.project_dir).name)
        
        # 获取贡献者信息
        contributors = self._get_git_contributors(max_contributors=5)
        contributors_info = "\n项目贡献者：\n"
        for contributor in contributors:
            contributors_info += f"- {contributor['name']} ({contributor['commits']} commits)"
            if contributor['email']:
                contributors_info += f" - {contributor['email']}"
            contributors_info += "\n"
        
        project_info = f"""
项目信息：
- 项目名称: {project_name}
- 项目路径: {self.project_dir}
- 模块数量: {len(analysis.get('modules', []))}
- 函数数量: {len(analysis.get('functions', []))}
- 类数量: {len(analysis.get('classes', []))}
- Git信息: {git_info}
- 依赖信息: {analysis.get('dependencies', {})}
- 入口点: {analysis.get('entry_points', [])}

{contributors_info}
"""
        
        return f"""
请为这个项目生成一个专业的首页文档，包括：
1. 项目简介和主要功能
2. 快速开始指南
3. 主要特性列表
4. 项目结构概览
5. 相关链接

{project_info}

请使用Markdown格式，风格要专业且易读。
"""
    
    def _create_installation_prompt(self, analysis: Dict) -> str:
        """
        创建安装指南文档生成的提示词
        
        所需输入信息：
        - analysis['git_info']['repo_name']: 项目名称
        - analysis['git_info']: Git仓库信息
        - analysis['dependencies']: 依赖信息（重点使用）
        - analysis['modules']: 模块列表
        - analysis['functions']: 函数列表
        - analysis['classes']: 类列表
        - analysis['entry_points']: 入口点信息
        - self.project_dir: 项目路径
        """
        git_info = analysis.get('git_info', {})
        project_name = git_info.get('repo_name', Path(self.project_dir).name)
        dependencies = analysis.get('dependencies', {})
        
        project_info = f"""
项目信息：
- 项目名称: {project_name}
- 项目路径: {self.project_dir}
- 模块数量: {len(analysis.get('modules', []))}
- 函数数量: {len(analysis.get('functions', []))}
- 类数量: {len(analysis.get('classes', []))}
- Git信息: {git_info}
- 依赖信息: {dependencies}
- 入口点: {analysis.get('entry_points', [])}
"""
        
        return f"""
请为这个项目生成详细的安装指南，包括：
1. 系统要求
2. 依赖安装
3. 不同平台的安装步骤
4. 验证安装
5. 常见安装问题

{project_info}

请使用Markdown格式。
"""
    
    def _create_usage_prompt(self, analysis: Dict) -> str:
        """
        创建使用说明文档生成的提示词
        
        所需输入信息：
        - analysis['git_info']['repo_name']: 项目名称
        - analysis['git_info']: Git仓库信息
        - analysis['functions']: 函数列表（重点使用，用于生成API示例）
        - analysis['classes']: 类列表（重点使用，用于生成API示例）
        - analysis['entry_points']: 入口点信息（重点使用，用于CLI示例）
        - analysis['modules']: 模块列表
        - analysis['dependencies']: 依赖信息
        - self.project_dir: 项目路径
        """
        git_info = analysis.get('git_info', {})
        project_name = git_info.get('repo_name', Path(self.project_dir).name)
        
        # 构建基础项目信息
        project_info = f"""
项目信息：
- 项目名称: {project_name}
- 项目路径: {self.project_dir}
- 模块数量: {len(analysis.get('modules', []))}
- 函数数量: {len(analysis.get('functions', []))}
- 类数量: {len(analysis.get('classes', []))}
- Git信息: {git_info}
- 依赖信息: {analysis.get('dependencies', {})}
- 入口点: {analysis.get('entry_points', [])}
"""
        
        # 添加详细的函数和类信息
        functions_info = "\n主要函数详情:\n"
        for func in analysis.get('functions', [])[:5]:
            functions_info += f"- {func.get('name', '')}: {func.get('definition', '')[:100]}...\n"
        
        classes_info = "\n主要类详情:\n"
        for cls in analysis.get('classes', [])[:3]:
            classes_info += f"- {cls.get('name', '')}: {cls.get('definition', '')[:100]}...\n"
        
        detailed_info = project_info + functions_info + classes_info
        
        return f"""
请为这个项目生成详细的使用说明文档。请仔细分析提供的项目信息，特别是入口点、函数定义和类定义，生成准确实用的使用指南。

包括以下内容：
1. 基本用法（基于实际的入口点和主要API）
2. 命令行接口说明（如果有CLI入口点）
3. 编程接口说明（如果有Python API）
4. 配置选项（基于实际的配置文件或参数）
5. 常用场景示例（基于实际功能推断）
6. 最佳实践

{detailed_info}

重要提示：
- 请基于提供的实际函数和类信息生成示例，不要编造不存在的API
- 如果是命令行工具，请基于入口点信息生成正确的命令示例
- 如果是Python库，请基于实际的类和函数生成导入和使用示例
- 避免使用虚构的功能或参数

请使用Markdown格式。
"""
    
    def _create_examples_prompt(self, analysis: Dict) -> str:
        """
        创建示例文档生成的提示词
        
        所需输入信息：
        - analysis['git_info']['repo_name']: 项目名称
        - analysis['git_info']: Git仓库信息
        - analysis['functions']: 函数列表（重点使用，用于生成代码示例）
        - analysis['classes']: 类列表（重点使用，用于生成代码示例）
        - analysis['entry_points']: 入口点信息（重点使用，用于CLI示例）
        - analysis['modules']: 模块列表
        - analysis['dependencies']: 依赖信息
        - self.project_dir: 项目路径
        """
        git_info = analysis.get('git_info', {})
        project_name = git_info.get('repo_name', Path(self.project_dir).name)
        
        project_info = f"""
项目信息：
- 项目名称: {project_name}
- 项目路径: {self.project_dir}
- 模块数量: {len(analysis.get('modules', []))}
- 函数数量: {len(analysis.get('functions', []))}
- 类数量: {len(analysis.get('classes', []))}
- Git信息: {git_info}
- 依赖信息: {analysis.get('dependencies', {})}
- 入口点: {analysis.get('entry_points', [])}
"""
        
        return f"""
请为这个项目生成示例文档。请仔细分析项目的实际功能和API，生成真实可用的示例代码。

包括以下内容：
1. 基础使用示例（基于主要入口点和核心功能）
2. 高级功能示例（基于复杂的类和方法）
3. 集成示例（如何与其他工具或库集成）
4. 完整项目示例（端到端的使用场景）
5. 代码片段说明

{project_info}

生成指导原则：
- 仔细分析提供的函数和类定义，确保示例代码使用真实存在的API
- 根据函数参数和返回值类型生成合理的示例
- 如果是命令行工具，提供实际可执行的命令示例
- 如果是Python库，提供正确的导入语句和方法调用
- 为每个示例添加清晰的注释说明
- 确保示例代码的语法正确性
- 避免使用不存在的方法、参数或配置选项

请使用Markdown格式，包含可运行的代码示例。
"""
    
    def _create_architecture_prompt(self, analysis: Dict) -> str:
        """
        创建架构文档生成的提示词
        
        所需输入信息：
        - analysis['git_info']['repo_name']: 项目名称
        - analysis['git_info']: Git仓库信息
        - analysis['modules']: 模块列表（重点使用，用于架构分析）
        - analysis['functions']: 函数列表
        - analysis['classes']: 类列表
        - analysis['dependencies']: 依赖信息
        - analysis['entry_points']: 入口点信息
        - self.project_dir: 项目路径
        """
        git_info = analysis.get('git_info', {})
        project_name = git_info.get('repo_name', Path(self.project_dir).name)
        modules = analysis.get('modules', [])
        
        # 读取脚本简介信息
        script_descriptions_file = self.project_dir / "script_descriptions.json"
        script_descriptions = {}
        if script_descriptions_file.exists():
            try:
                with open(script_descriptions_file, 'r', encoding='utf-8') as f:
                    script_descriptions = json.load(f)
            except Exception as e:
                if self.verbose:
                    self.console.print(f"[yellow]Warning: 无法读取脚本描述文件: {e}[/yellow]")
        
        # 格式化脚本简介
        scripts_info = "\n脚本简介：\n"
        for script_path, description in script_descriptions.items():
            scripts_info += f"- {script_path}: {description[:200]}...\n"
        
        project_info = f"""
项目信息：
- 项目名称: {project_name}
- 项目路径: {self.project_dir}
- 模块数量: {len(analysis.get('modules', []))}
- 函数数量: {len(analysis.get('functions', []))}
- 类数量: {len(analysis.get('classes', []))}
- Git信息: {git_info}
- 依赖信息: {analysis.get('dependencies', {})}
- 入口点: {analysis.get('entry_points', [])}
- 模块列表: {modules}

{scripts_info}
"""
        
        return f"""
请基于项目的脚本简介和模块信息生成专业的架构文档，包括：

1. **项目架构概览**：
   - 整体架构设计理念
   - 核心组件和模块介绍
   - 架构图引用：{{{{ARCHITECTURE_DIAGRAM_PLACEHOLDER}}}}

2. **模块详细说明**：
   - 基于脚本简介分析各模块的职责
   - 模块之间的依赖关系
   - 核心类和函数的作用

3. **数据流和交互**：
   - 数据在系统中的流转过程
   - 模块间的交互方式
   - 关键接口和协议

4. **设计模式和原则**：
   - 项目中使用的设计模式
   - 架构设计原则
   - 代码组织方式

5. **扩展性设计**：
   - 系统的扩展点
   - 插件机制（如果有）
   - 未来发展方向

6. **技术栈说明**：
   - 主要技术选型
   - 依赖库的作用
   - 技术决策的考虑因素

{project_info}

注意：
- 重点结合脚本简介来分析架构
- 架构图将单独生成为 drawio 文件
- 使用专业的技术术语
- 提供清晰的层次结构
- 使用标准的Markdown格式
- 包含实用的架构建议
"""
    
    def _create_contributing_prompt(self, analysis: Dict) -> str:
        """
        创建贡献指南文档生成的提示词
        
        所需输入信息：
        - analysis['git_info']['repo_name']: 项目名称
        - analysis['git_info']: Git仓库信息（重点使用，用于贡献流程）
        - analysis['dependencies']: 依赖信息（用于开发环境搭建）
        - analysis['modules']: 模块列表
        - analysis['functions']: 函数列表
        - analysis['classes']: 类列表
        - analysis['entry_points']: 入口点信息
        - self.project_dir: 项目路径
        """
        git_info = analysis.get('git_info', {})
        project_name = git_info.get('repo_name', Path(self.project_dir).name)
        
        # 获取Git贡献者信息
        contributors = self._get_git_contributors()
        
        # 格式化贡献者信息
        contributors_info = "\n项目贡献者：\n"
        for contributor in contributors[:10]:  # 只显示前10个贡献者
            contributors_info += f"- {contributor['name']} ({contributor['commits']} commits)"
            if contributor['email']:
                contributors_info += f" - {contributor['email']}"
            contributors_info += "\n"
        
        project_info = f"""
项目信息：
- 项目名称: {project_name}
- 项目路径: {self.project_dir}
- 模块数量: {len(analysis.get('modules', []))}
- 函数数量: {len(analysis.get('functions', []))}
- 类数量: {len(analysis.get('classes', []))}
- Git信息: {git_info}
- 依赖信息: {analysis.get('dependencies', {})}
- 入口点: {analysis.get('entry_points', [])}
"""
        
        return f"""
请基于项目的Git仓库信息和现有贡献者生成专业的贡献指南文档，包括：

1. **项目贡献者致谢**：
   - 展示现有贡献者的头像和贡献统计
   - 使用GitHub头像链接格式：![avatar](https://github.com/username.png?size=50)
   - 按贡献次数排序展示贡献者

2. **如何开始贡献**：
   - Fork项目流程
   - 克隆和设置本地开发环境
   - 创建功能分支的最佳实践

3. **开发环境搭建**：
   - 基于项目依赖信息提供详细的环境配置步骤
   - 包含虚拟环境设置、依赖安装等

4. **代码贡献规范**：
   - 代码风格和格式要求
   - 提交信息规范（基于现有提交历史的模式）
   - 代码审查流程

5. **测试要求**：
   - 如何运行测试
   - 新功能的测试覆盖要求
   - 测试最佳实践

6. **Pull Request流程**：
   - PR模板和要求
   - 代码审查流程
   - 合并标准

7. **问题报告**：
   - Bug报告模板
   - 功能请求格式
   - 问题分类和标签

8. **社区准则**：
   - 行为准则
   - 沟通方式
   - 获取帮助的渠道

{project_info}

注意：
- 为每个贡献者生成GitHub头像链接
- 基于实际的Git信息提供具体的贡献流程
- 使用友好和鼓励性的语调
- 提供清晰的步骤说明
- 使用标准的Markdown格式
- 包含实用的代码示例和命令
"""
    
    def _create_changelog_prompt(self, analysis: Dict) -> str:
        """
        创建增强的更新日志文档生成提示词
        
        所需输入信息：
        - analysis['git_info']['repo_name']: 项目名称
        - analysis['git_info']: Git仓库信息
        - analysis['modules']: 模块列表
        - analysis['functions']: 函数列表
        - analysis['classes']: 类列表
        - analysis['dependencies']: 依赖信息
        - analysis['entry_points']: 入口点信息
        - self.project_dir: 项目路径
        """
        git_info = analysis.get('git_info', {})
        project_name = git_info.get('repo_name', Path(self.project_dir).name)
        
        # 获取增强的Git提交历史
        commit_history = self._get_git_commit_history(limit=30)
        
        # 获取Git标签信息
        tags = self._get_git_tags()
        
        # 分析提交统计
        commit_stats = self._analyze_commit_statistics(commit_history)
        
        # 格式化详细的提交历史
        commit_info = "\n=== 详细提交历史分析 ===\n"
        
        # 按类型分组显示提交
        commits_by_type = {}
        for commit in commit_history:
            commit_type = commit.get('type', 'other')
            if commit_type not in commits_by_type:
                commits_by_type[commit_type] = []
            commits_by_type[commit_type].append(commit)
        
        for commit_type, commits in commits_by_type.items():
            commit_info += f"\n{commit_type.upper()} 类型提交 ({len(commits)} 个):\n"
            for commit in commits[:5]:  # 每种类型最多显示5个
                files_info = f" (影响 {len(commit.get('files_changed', []))} 个文件)" if commit.get('files_changed') else ""
                breaking_mark = " [BREAKING]" if commit.get('is_breaking') else ""
                commit_info += f"  - {commit['date']} [{commit['hash']}] {commit['message']}{files_info}{breaking_mark}\n"
                
                # 显示主要变更文件
                if commit.get('files_changed'):
                    main_files = [f['file'] for f in commit['files_changed'][:3]]
                    commit_info += f"    主要文件: {', '.join(main_files)}\n"
        
        # 添加标签信息
        tags_info = "\n=== 版本标签历史 ===\n"
        if tags:
            for tag in tags[:10]:
                tags_info += f"- {tag['name']} ({tag['date']}) - {tag['message']}\n"
        else:
            tags_info += "暂无版本标签\n"
        
        # 添加统计信息
        stats_info = f"\n=== 提交统计分析 ===\n"
        stats_info += f"- 总提交数: {len(commit_history)}\n"
        stats_info += f"- 功能提交: {commit_stats.get('feat', 0)} 个\n"
        stats_info += f"- 修复提交: {commit_stats.get('fix', 0)} 个\n"
        stats_info += f"- 文档提交: {commit_stats.get('docs', 0)} 个\n"
        stats_info += f"- 重构提交: {commit_stats.get('refactor', 0)} 个\n"
        stats_info += f"- 破坏性变更: {sum(1 for c in commit_history if c.get('is_breaking'))} 个\n"
        stats_info += f"- 主要贡献者: {', '.join(list(set([c['author'] for c in commit_history[:10]])))[:100]}...\n"
        
        project_info = f"""
项目信息：
- 项目名称: {project_name}
- 项目路径: {self.project_dir}
- 模块数量: {len(analysis.get('modules', []))}
- 函数数量: {len(analysis.get('functions', []))}
- 类数量: {len(analysis.get('classes', []))}
- Git信息: {git_info}
- 依赖信息: {analysis.get('dependencies', {})}
- 入口点: {analysis.get('entry_points', [])}

{commit_info}
{tags_info}
{stats_info}
"""
        
        return f"""
请基于项目的详细Git提交历史和分析结果生成专业的更新日志文档，包括：

1. **版本管理规范**：
   - 语义化版本控制 (Semantic Versioning) 说明
   - 版本号格式：MAJOR.MINOR.PATCH
   - 版本发布策略和周期

2. **更新日志结构**：
   - 按版本时间倒序组织
   - 标准分类：Added（新增）、Changed（变更）、Deprecated（弃用）、Removed（移除）、Fixed（修复）、Security（安全）
   - 破坏性变更单独标注 [BREAKING CHANGE]

3. **基于实际提交历史的智能分析**：
   - 根据提交类型统计自动生成版本条目
   - 将技术性提交信息转换为用户友好的描述
   - 合并相关提交为有意义的功能变更
   - 识别和突出显示破坏性变更
   - 基于文件变更范围评估变更影响

4. **版本发布建议**：
   - 基于提交类型建议下一个版本号
   - 根据破坏性变更建议主版本升级
   - 基于功能提交建议次版本升级
   - 基于修复提交建议补丁版本升级

5. **详细的版本条目示例**：
   - 根据实际提交历史生成具体版本
   - 展示完整的变更分类和描述
   - 包含贡献者信息和提交链接
   - 显示每个版本的影响范围和重要性

6. **维护指南**：
   - 如何维护更新日志
   - 提交信息规范建议
   - 版本发布流程说明

7. **贡献者致谢**：
   - 按版本列出主要贡献者
   - 感谢社区贡献和反馈

{project_info}

特别要求：
- 深度分析提交历史，生成真实可信的版本变更
- 智能识别功能模块，按模块组织变更说明
- 将技术性提交转换为业务价值描述
- 突出显示用户关心的功能改进和问题修复
- 基于文件变更统计评估每个版本的影响范围
- 使用 Keep a Changelog 标准格式
- 提供版本间的升级指导和注意事项
- 包含具体的代码示例和使用说明（如适用）
- 生成可操作的版本发布检查清单
"""
        
    def _create_mkdocs_config(self, analysis: Dict) -> Dict:
        """创建MkDocs配置"""
        git_info = analysis.get('git_info', {})
        repo_name = git_info.get('repo_name', 'project')
        github_username = git_info.get('github_username', '')
        
        # 处理repo_url，确保使用https格式
        remote_url = git_info.get('remote_url', '')
        repo_url = self._convert_git_url_to_https(remote_url)
        
        config = {
            'site_name': f'{repo_name} 文档',
            'site_description': f'{repo_name} 项目文档',
            'site_author': github_username,
            'repo_url': repo_url,
            'repo_name': f'{github_username}/{repo_name}' if github_username else repo_name,
            
            'theme': {
                'name': 'material',
                'language': 'zh',
                'features': [
                    'navigation.tabs',
                    'navigation.sections',
                    'navigation.expand',
                    'navigation.top',
                    'search.highlight',
                    'search.share',
                    'content.code.copy'
                ],
                'palette': [
                    {
                        'scheme': 'default',
                        'primary': 'blue',
                        'accent': 'blue',
                        'toggle': {
                            'icon': 'material/brightness-7',
                            'name': '切换到深色模式'
                        }
                    },
                    {
                        'scheme': 'slate',
                        'primary': 'blue',
                        'accent': 'blue',
                        'toggle': {
                            'icon': 'material/brightness-4',
                            'name': '切换到浅色模式'
                        }
                    }
                ]
            },
            
            'nav': [
                {'首页': 'index.md'},
                {'安装': 'installation.md'},
                {'使用说明': 'usage.md'},
                {'API文档': 'api/index.md'},
                {'示例': 'examples.md'},
                {'架构': 'architecture.md'},
                {'贡献指南': 'contributing.md'},
                {'更新日志': 'changelog.md'}
            ],
            
            'markdown_extensions': [
                'codehilite',
                'admonition',
                'pymdownx.details',
                'pymdownx.superfences',
                'pymdownx.tabbed',
                'toc'
            ],
            
            'plugins': [
                'search',
                'drawio'
            ]
        }
        
        return config
        
    def _dict_to_yaml_string(self, data: Dict, indent: int = 0) -> str:
        """将字典转换为YAML格式字符串（修复版本，确保字符串值被正确引用）"""
        yaml_lines = []
        indent_str = '  ' * indent
        
        for key, value in data.items():
            if isinstance(value, dict):
                yaml_lines.append(f"{indent_str}{key}:")
                yaml_lines.append(self._dict_to_yaml_string(value, indent + 1))
            elif isinstance(value, list):
                yaml_lines.append(f"{indent_str}{key}:")
                for item in value:
                    if isinstance(item, dict):
                        yaml_lines.append(f"{indent_str}  -")
                        for sub_key, sub_value in item.items():
                            formatted_value = self._format_yaml_value(sub_value)
                            yaml_lines.append(f"{indent_str}    {sub_key}: {formatted_value}")
                    else:
                        formatted_item = self._format_yaml_value(item)
                        yaml_lines.append(f"{indent_str}  - {formatted_item}")
            else:
                formatted_value = self._format_yaml_value(value)
                yaml_lines.append(f"{indent_str}{key}: {formatted_value}")
                
        return '\n'.join(yaml_lines)
    
    def _format_yaml_value(self, value) -> str:
        """格式化YAML值，确保字符串被正确引用"""
        if isinstance(value, str):
            # 检查是否需要引用
            if (value.isdigit() or 
                value.lower() in ['true', 'false', 'null', 'yes', 'no'] or
                ':' in value or 
                value.startswith('#') or
                '\n' in value or
                value.strip() != value):
                return f'"{value}"'
            return value
        elif isinstance(value, bool):
            return 'true' if value else 'false'
        elif value is None:
            return 'null'
        else:
            return str(value)
    
    # AST解析辅助方法
    def _extract_functions_from_ast(self, tree: ast.AST, file_path: Path, content: str) -> List[Dict]:
        """从AST中提取函数信息"""
        functions = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                func_info = {
                    'name': node.name,
                    'module': self._get_module_name(file_path),
                    'file_path': str(file_path),
                    'line_start': node.lineno,
                    'line_end': getattr(node, 'end_lineno', node.lineno),
                    'definition': self._extract_function_definition(node, content),
                    'context': self._extract_function_context(node, content),
                    'metadata': self._extract_function_metadata(node),
                    'lines': getattr(node, 'end_lineno', node.lineno) - node.lineno + 1
                }
                functions.append(func_info)
                
        return functions
        
    def _extract_classes_from_ast(self, tree: ast.AST, file_path: Path, content: str) -> List[Dict]:
        """从AST中提取类信息"""
        classes = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                class_info = {
                    'name': node.name,
                    'module': self._get_module_name(file_path),
                    'file_path': str(file_path),
                    'line_start': node.lineno,
                    'line_end': getattr(node, 'end_lineno', node.lineno),
                    'definition': self._extract_class_definition(node, content),
                    'context': self._extract_class_context(node, content),
                    'metadata': self._extract_class_metadata(node),
                    'methods': self._extract_class_methods(node)
                }
                classes.append(class_info)
                
        return classes
        
    def _get_module_name(self, file_path: Path) -> str:
        """获取模块名"""
        relative_path = file_path.relative_to(self.project_dir)
        return str(relative_path).replace('/', '.').replace('\\', '.').replace('.py', '')
        
    def _extract_function_definition(self, node: ast.FunctionDef, content: str) -> str:
        """提取函数定义"""
        lines = content.split('\n')
        start_line = node.lineno - 1
        end_line = getattr(node, 'end_lineno', node.lineno)
        
        # 提取函数签名和文档字符串
        definition_lines = []
        
        # 添加装饰器
        for decorator in node.decorator_list:
            decorator_line = start_line - len(node.decorator_list) + node.decorator_list.index(decorator)
            if 0 <= decorator_line < len(lines):
                definition_lines.append(lines[decorator_line].strip())
                
        # 添加函数签名
        if start_line < len(lines):
            func_line = lines[start_line].strip()
            definition_lines.append(func_line)
            
        # 添加文档字符串
        if (isinstance(node.body[0], ast.Expr) and 
            isinstance(node.body[0].value, ast.Constant) and 
            isinstance(node.body[0].value.value, str)):
            docstring = node.body[0].value.value
            definition_lines.append(f'    """\n    {docstring}\n    """')
            
        return '\n'.join(definition_lines)
        
    def _extract_class_definition(self, node: ast.ClassDef, content: str) -> str:
        """提取类定义"""
        lines = content.split('\n')
        start_line = node.lineno - 1
        
        definition_lines = []
        
        # 添加装饰器
        for decorator in node.decorator_list:
            decorator_line = start_line - len(node.decorator_list) + node.decorator_list.index(decorator)
            if 0 <= decorator_line < len(lines):
                definition_lines.append(lines[decorator_line].strip())
                
        # 添加类签名
        if start_line < len(lines):
            class_line = lines[start_line].strip()
            definition_lines.append(class_line)
            
        # 添加文档字符串
        if (node.body and isinstance(node.body[0], ast.Expr) and 
            isinstance(node.body[0].value, ast.Constant) and 
            isinstance(node.body[0].value.value, str)):
            docstring = node.body[0].value.value
            definition_lines.append(f'    """\n    {docstring}\n    """')
            
        return '\n'.join(definition_lines)
        
    def _extract_function_context(self, node: ast.FunctionDef, content: str) -> str:
        """提取函数上下文信息"""
        lines = content.split('\n')
        start_line = max(0, node.lineno - 5)  # 前5行
        end_line = min(len(lines), getattr(node, 'end_lineno', node.lineno) + 3)  # 后3行
        
        context_lines = lines[start_line:end_line]
        return '\n'.join(context_lines)
        
    def _extract_class_context(self, node: ast.ClassDef, content: str) -> str:
        """提取类上下文信息"""
        lines = content.split('\n')
        start_line = max(0, node.lineno - 3)
        end_line = min(len(lines), node.lineno + 10)  # 类的前几行
        
        context_lines = lines[start_line:end_line]
        return '\n'.join(context_lines)
        
    def _extract_function_metadata(self, node: ast.FunctionDef) -> Dict:
        """提取函数元数据"""
        metadata = {
            'args': [arg.arg for arg in node.args.args],
            'defaults': len(node.args.defaults),
            'returns': bool(node.returns),
            'is_async': isinstance(node, ast.AsyncFunctionDef),
            'decorators': [ast.unparse(d) for d in node.decorator_list] if hasattr(ast, 'unparse') else [],
            'complexity': self._calculate_complexity(node)
        }
        return metadata
        
    def _extract_class_metadata(self, node: ast.ClassDef) -> Dict:
        """提取类元数据"""
        metadata = {
            'bases': [ast.unparse(base) for base in node.bases] if hasattr(ast, 'unparse') else [],
            'decorators': [ast.unparse(d) for d in node.decorator_list] if hasattr(ast, 'unparse') else [],
            'methods': len([n for n in node.body if isinstance(n, ast.FunctionDef)]),
            'properties': len([n for n in node.body if isinstance(n, ast.FunctionDef) and 
                             any(isinstance(d, ast.Name) and d.id == 'property' for d in n.decorator_list)])
        }
        return metadata
        
    def _extract_class_methods(self, node: ast.ClassDef) -> List[str]:
        """提取类方法名列表"""
        methods = []
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                methods.append(item.name)
        return methods
        
    def _calculate_complexity(self, node: ast.FunctionDef) -> int:
        """计算函数复杂度（简单版本）"""
        complexity = 1  # 基础复杂度
        
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.While, ast.For, ast.Try, ast.With)):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                complexity += len(child.values) - 1
                
        return complexity
        
    # 依赖解析辅助方法
    def _parse_python_deps(self, file_path: Path) -> List[str]:
        """解析Python依赖"""
        deps = []
        filename = file_path.name.lower()
        
        try:
            if filename == 'requirements.txt' or filename.endswith('.txt'):
                deps = self._parse_requirements_txt(file_path)
            elif filename == 'pyproject.toml':
                deps = self._parse_pyproject_toml(file_path)
            elif filename == 'setup.py':
                deps = self._parse_setup_py(file_path)
            elif filename == 'pipfile':
                deps = self._parse_pipfile(file_path)
            elif filename == 'setup.cfg':
                deps = self._parse_setup_cfg(file_path)
            elif filename == 'environment.yml':
                deps = self._parse_conda_env(file_path)
            elif filename == 'poetry.lock':
                deps = self._parse_poetry_lock(file_path)
                
        except Exception as e:
            if self.verbose:
                self.console.print(f"[yellow]Warning: Error parsing {file_path}: {e}[/yellow]")
                
        return deps
    
    def _parse_requirements_txt(self, file_path: Path) -> List[str]:
        """解析requirements.txt文件"""
        deps = []
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # 跳过注释、空行和-r/-e选项
                if line and not line.startswith('#') and not line.startswith('-'):
                    # 处理git+https://等URL依赖
                    if line.startswith('git+') or line.startswith('http'):
                        # 尝试从URL中提取包名
                        if '#egg=' in line:
                            pkg_name = line.split('#egg=')[1].split('&')[0]
                        else:
                            continue
                    else:
                        # 提取包名（去除版本号和额外选项）
                        pkg_name = re.split(r'[>=<!=\[\s]', line)[0].strip()
                    
                    if pkg_name and pkg_name not in deps:
                        deps.append(pkg_name)
        return deps
    
    def _parse_pyproject_toml(self, file_path: Path) -> List[str]:
        """解析pyproject.toml文件"""
        deps = []
        
        try:
            import tomli
            with open(file_path, 'rb') as f:
                data = tomli.load(f)
                
            # 从project.dependencies中提取
            project_deps = data.get('project', {}).get('dependencies', [])
            for dep in project_deps:
                pkg_name = re.split(r'[>=<!=\[\s]', dep)[0].strip()
                if pkg_name:
                    deps.append(pkg_name)
            
            # 从tool.poetry.dependencies中提取（Poetry格式）
            poetry_deps = data.get('tool', {}).get('poetry', {}).get('dependencies', {})
            for pkg_name in poetry_deps.keys():
                if pkg_name != 'python':  # 排除python版本要求
                    deps.append(pkg_name)
                    
        except ImportError:
            # 如果没有tomli，尝试简单解析
            deps = self._parse_toml_fallback(file_path)
            
        return deps
    
    def _parse_toml_fallback(self, file_path: Path) -> List[str]:
        """TOML文件的fallback解析方法"""
        deps = []
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # 匹配dependencies数组
        deps_patterns = [
            r'dependencies\s*=\s*\[(.*?)\]',
            r'\[tool\.poetry\.dependencies\](.*?)(?=\[|$)'
        ]
        
        for pattern in deps_patterns:
            matches = re.findall(pattern, content, re.DOTALL)
            for match in matches:
                # 提取引号内的依赖
                dep_matches = re.findall(r'["\']([^"\'><=!\[]+)', match)
                for dep in dep_matches:
                    if dep and dep != 'python':
                        deps.append(dep)
                        
        return deps
    
    def _parse_setup_py(self, file_path: Path) -> List[str]:
        """解析setup.py文件"""
        deps = []
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # 匹配install_requires
        install_requires_match = re.search(r'install_requires\s*=\s*\[(.*?)\]', content, re.DOTALL)
        if install_requires_match:
            deps_str = install_requires_match.group(1)
            dep_matches = re.findall(r'["\']([^"\'><=!\[]+)', deps_str)
            deps.extend(dep_matches)
            
        return deps
    
    def _parse_pipfile(self, file_path: Path) -> List[str]:
        """解析Pipfile文件"""
        deps = []
        try:
            import tomli
            with open(file_path, 'rb') as f:
                data = tomli.load(f)
                
            # 从packages和dev-packages中提取
            for section in ['packages', 'dev-packages']:
                if section in data:
                    deps.extend(data[section].keys())
                    
        except ImportError:
            # fallback解析
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            sections = re.findall(r'\[(packages|dev-packages)\](.*?)(?=\[|$)', content, re.DOTALL)
            for section_name, section_content in sections:
                dep_matches = re.findall(r'^([a-zA-Z0-9_-]+)\s*=', section_content, re.MULTILINE)
                deps.extend(dep_matches)
                
        return deps
    
    def _parse_setup_cfg(self, file_path: Path) -> List[str]:
        """解析setup.cfg文件"""
        deps = []
        try:
            import configparser
            config = configparser.ConfigParser()
            config.read(file_path)
            
            if 'options' in config and 'install_requires' in config['options']:
                install_requires = config['options']['install_requires']
                for line in install_requires.split('\n'):
                    line = line.strip()
                    if line:
                        pkg_name = re.split(r'[>=<!=\[\s]', line)[0].strip()
                        if pkg_name:
                            deps.append(pkg_name)
                            
        except Exception:
            pass
            
        return deps
    
    def _parse_conda_env(self, file_path: Path) -> List[str]:
        """解析conda environment.yml文件"""
        deps = []
        try:
            import yaml
            with open(file_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                
            if 'dependencies' in data:
                for dep in data['dependencies']:
                    if isinstance(dep, str):
                        # 跳过conda-forge等channel信息
                        if '::' not in dep:
                            pkg_name = re.split(r'[>=<!=\s]', dep)[0].strip()
                            if pkg_name:
                                deps.append(pkg_name)
                                
        except ImportError:
            pass
        except Exception:
            pass
            
        return deps
    
    def _parse_poetry_lock(self, file_path: Path) -> List[str]:
        """解析poetry.lock文件"""
        deps = []
        try:
            import tomli
            with open(file_path, 'rb') as f:
                data = tomli.load(f)
                
            if 'package' in data:
                for package in data['package']:
                    if 'name' in package:
                        deps.append(package['name'])
                        
        except ImportError:
            pass
        except Exception:
            pass
            
        return deps
    
    def _infer_dependencies_from_code(self) -> List[str]:
        """从代码中推断依赖包"""
        deps = set()
        
        # 常见的第三方包映射
        import_to_package = {
            'numpy': 'numpy', 'np': 'numpy',
            'pandas': 'pandas', 'pd': 'pandas',
            'requests': 'requests',
            'flask': 'Flask',
            'django': 'Django',
            'fastapi': 'fastapi',
            'click': 'click',
            'rich': 'rich',
            'typer': 'typer',
            'pydantic': 'pydantic',
            'sqlalchemy': 'SQLAlchemy',
            'pytest': 'pytest',
            'matplotlib': 'matplotlib',
            'seaborn': 'seaborn',
            'sklearn': 'scikit-learn',
            'cv2': 'opencv-python',
            'PIL': 'Pillow',
            'yaml': 'PyYAML',
            'dotenv': 'python-dotenv',
            'openai': 'openai',
            'transformers': 'transformers',
            'torch': 'torch',
            'tensorflow': 'tensorflow',
            'streamlit': 'streamlit',
            'gradio': 'gradio'
        }
        
        python_files = list(self.project_dir.rglob('*.py'))
        
        for file_path in python_files[:50]:  # 限制文件数量避免过慢
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # 匹配import语句
                import_patterns = [
                    r'^import\s+([a-zA-Z_][a-zA-Z0-9_]*)',
                    r'^from\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+import',
                    r'^\s*import\s+([a-zA-Z_][a-zA-Z0-9_]*)',
                    r'^\s*from\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+import'
                ]
                
                for pattern in import_patterns:
                    matches = re.findall(pattern, content, re.MULTILINE)
                    for match in matches:
                        # 只取第一级包名
                        pkg_name = match.split('.')[0]
                        if pkg_name in import_to_package:
                            deps.add(import_to_package[pkg_name])
                        elif not pkg_name.startswith('_') and len(pkg_name) > 2:
                            # 可能是第三方包
                            deps.add(pkg_name)
                            
            except Exception:
                continue
                
        return list(deps)
    
    def _detect_other_dependencies(self) -> List[str]:
        """检测其他类型的依赖"""
        other_deps = []
        
        # Go语言
        if (self.project_dir / 'go.mod').exists():
            other_deps.extend(self._parse_go_mod(self.project_dir / 'go.mod'))
        if (self.project_dir / 'go.sum').exists():
            other_deps.append('Go modules')
            
        # Rust语言
        if (self.project_dir / 'Cargo.toml').exists():
            other_deps.extend(self._parse_cargo_toml(self.project_dir / 'Cargo.toml'))
        if (self.project_dir / 'Cargo.lock').exists():
            other_deps.append('Rust crates')
            
        # Java/Kotlin
        if (self.project_dir / 'pom.xml').exists():
            other_deps.extend(self._parse_maven_pom(self.project_dir / 'pom.xml'))
        if (self.project_dir / 'build.gradle').exists() or (self.project_dir / 'build.gradle.kts').exists():
            other_deps.append('Gradle dependencies')
            
        # C/C++
        if (self.project_dir / 'CMakeLists.txt').exists():
            other_deps.append('CMake')
        if (self.project_dir / 'conanfile.txt').exists() or (self.project_dir / 'conanfile.py').exists():
            other_deps.append('Conan packages')
            
        # Ruby
        if (self.project_dir / 'Gemfile').exists():
            other_deps.extend(self._parse_gemfile(self.project_dir / 'Gemfile'))
            
        # PHP
        if (self.project_dir / 'composer.json').exists():
            other_deps.extend(self._parse_composer_json(self.project_dir / 'composer.json'))
        
        # 检查Docker
        if (self.project_dir / 'Dockerfile').exists():
            other_deps.append('Docker')
        if (self.project_dir / 'docker-compose.yml').exists():
            other_deps.append('Docker Compose')
            
        # 检查数据库
        db_files = ['*.db', '*.sqlite', '*.sqlite3']
        for pattern in db_files:
            if list(self.project_dir.rglob(pattern)):
                other_deps.append('SQLite')
                break
                
        # 检查配置文件
        config_files = {
            '.env': 'Environment Variables',
            'config.yaml': 'YAML Config',
            'config.yml': 'YAML Config',
            'config.json': 'JSON Config',
            'settings.py': 'Django Settings',
            'manage.py': 'Django',
            'app.py': 'Flask/FastAPI',
            'main.py': 'Python Application',
            'Makefile': 'Make'
        }
        
        for filename, dep_name in config_files.items():
            if (self.project_dir / filename).exists():
                other_deps.append(dep_name)
                
        # 检查CI/CD
        ci_files = [
            '.github/workflows',
            '.gitlab-ci.yml',
            '.travis.yml',
            'Jenkinsfile',
            '.circleci'
        ]
        
        for ci_file in ci_files:
            if (self.project_dir / ci_file).exists():
                other_deps.append('CI/CD')
                break
                
        return other_deps
        
    def _parse_npm_deps(self, file_path: Path) -> List[str]:
        """解析NPM依赖"""
        deps = []
        filename = file_path.name.lower()
        
        try:
            if filename == 'package.json':
                deps = self._parse_package_json(file_path)
            elif filename == 'package-lock.json':
                deps = self._parse_package_lock(file_path)
            elif filename == 'yarn.lock':
                deps = self._parse_yarn_lock(file_path)
                
        except Exception as e:
            if self.verbose:
                self.console.print(f"[yellow]Warning: Could not parse {file_path}: {e}[/yellow]")
            
        return deps
    
    def _parse_package_json(self, file_path: Path) -> List[str]:
        """解析package.json文件"""
        deps = []
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        # 提取dependencies和devDependencies
        for dep_type in ['dependencies', 'devDependencies', 'peerDependencies', 'optionalDependencies']:
            if dep_type in data:
                deps.extend(data[dep_type].keys())
                
        return deps
    
    def _parse_package_lock(self, file_path: Path) -> List[str]:
        """解析package-lock.json文件"""
        deps = []
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        # 从dependencies中提取
        if 'dependencies' in data:
            deps.extend(data['dependencies'].keys())
        elif 'packages' in data:
            # npm v7+ 格式
            for pkg_path, pkg_info in data['packages'].items():
                if pkg_path.startswith('node_modules/'):
                    pkg_name = pkg_path.replace('node_modules/', '')
                    deps.append(pkg_name)
                    
        return deps
    
    def _parse_yarn_lock(self, file_path: Path) -> List[str]:
        """解析yarn.lock文件"""
        deps = set()
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # 匹配包名模式
        # yarn.lock格式: "package-name@version":
        pkg_patterns = [
            r'^"?([a-zA-Z0-9@/_-]+)@',
            r'^([a-zA-Z0-9@/_-]+)@'
        ]
        
        for pattern in pkg_patterns:
            matches = re.findall(pattern, content, re.MULTILINE)
            for match in matches:
                # 清理包名
                pkg_name = match.split('@')[0] if '@' in match else match
                if pkg_name and not pkg_name.startswith('.'):
                    deps.add(pkg_name)
                    
        return list(deps)
    
    def _parse_go_mod(self, file_path: Path) -> List[str]:
        """解析go.mod文件"""
        deps = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 匹配require块中的依赖
            require_pattern = r'require\s*\(([^)]+)\)'
            require_match = re.search(require_pattern, content, re.DOTALL)
            if require_match:
                require_block = require_match.group(1)
                # 匹配每个依赖行
                dep_pattern = r'([a-zA-Z0-9./\\-_]+)\s+v[0-9.]+'
                deps.extend(re.findall(dep_pattern, require_block))
            
            # 匹配单行require
            single_require_pattern = r'require\s+([a-zA-Z0-9./\\-_]+)\s+v[0-9.]+'
            deps.extend(re.findall(single_require_pattern, content))
            
        except Exception as e:
            if self.verbose:
                self.console.print(f"[yellow]Warning: Could not parse {file_path}: {e}[/yellow]")
        
        return deps
    
    def _parse_cargo_toml(self, file_path: Path) -> List[str]:
        """解析Cargo.toml文件"""
        deps = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 尝试使用tomli解析
            try:
                import tomli
                data = tomli.loads(content)
                
                # 提取dependencies
                for dep_type in ['dependencies', 'dev-dependencies', 'build-dependencies']:
                    if dep_type in data:
                        deps.extend(data[dep_type].keys())
                        
            except ImportError:
                # 简单的正则匹配
                dep_pattern = r'^([a-zA-Z0-9_\\-]+)\s*='
                in_deps_section = False
                
                for line in content.split('\n'):
                    line = line.strip()
                    if line.startswith('[dependencies') or line.startswith('[dev-dependencies') or line.startswith('[build-dependencies'):
                        in_deps_section = True
                        continue
                    elif line.startswith('[') and in_deps_section:
                        in_deps_section = False
                        continue
                    elif in_deps_section and '=' in line:
                        match = re.match(dep_pattern, line)
                        if match:
                            deps.append(match.group(1))
                            
        except Exception as e:
            if self.verbose:
                self.console.print(f"[yellow]Warning: Could not parse {file_path}: {e}[/yellow]")
        
        return deps
    
    def _parse_maven_pom(self, file_path: Path) -> List[str]:
        """解析Maven pom.xml文件"""
        deps = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 匹配dependency标签中的artifactId
            artifact_pattern = r'<artifactId>([^<]+)</artifactId>'
            deps.extend(re.findall(artifact_pattern, content))
            
        except Exception as e:
            if self.verbose:
                self.console.print(f"[yellow]Warning: Could not parse {file_path}: {e}[/yellow]")
        
        return deps
    
    def _parse_gemfile(self, file_path: Path) -> List[str]:
        """解析Ruby Gemfile"""
        deps = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 匹配gem声明
            gem_pattern = r"gem\s+['\"]([^'\"]+)['\"]"
            deps.extend(re.findall(gem_pattern, content))
            
        except Exception as e:
            if self.verbose:
                self.console.print(f"[yellow]Warning: Could not parse {file_path}: {e}[/yellow]")
        
        return deps
    
    def _parse_composer_json(self, file_path: Path) -> List[str]:
        """解析PHP composer.json文件"""
        deps = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 提取require和require-dev
            for dep_type in ['require', 'require-dev']:
                if dep_type in data:
                    deps.extend(data[dep_type].keys())
                    
        except Exception as e:
            if self.verbose:
                self.console.print(f"[yellow]Warning: Could not parse {file_path}: {e}[/yellow]")
        
        return deps
        
    def _parse_pyproject_scripts(self, file_path: Path) -> List[str]:
        """解析pyproject.toml中的脚本"""
        scripts = []
        
        try:
            import tomli
            with open(file_path, 'rb') as f:
                data = tomli.load(f)
                
            # 提取project.scripts
            project_scripts = data.get('project', {}).get('scripts', {})
            scripts.extend(project_scripts.keys())
            
        except ImportError:
            # 简单解析
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                scripts_match = re.search(r'\[project\.scripts\](.*?)(?=\[|$)', content, re.DOTALL)
                if scripts_match:
                    scripts_section = scripts_match.group(1)
                    for line in scripts_section.split('\n'):
                        if '=' in line:
                            script_name = line.split('=')[0].strip()
                            if script_name:
                                scripts.append(script_name)
                                
        except Exception as e:
            self.console.print(f"[yellow]Warning: Could not parse pyproject.toml: {e}[/yellow]")
            
        return scripts
        
    def _parse_setup_scripts(self, file_path: Path) -> List[str]:
        """解析setup.py中的脚本"""
        scripts = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # 简单的正则匹配entry_points
            entry_points_match = re.search(r'entry_points\s*=\s*{(.*?)}', content, re.DOTALL)
            if entry_points_match:
                entry_points_str = entry_points_match.group(1)
                console_scripts_match = re.search(r'["\']console_scripts["\']\s*:\s*\[(.*?)\]', entry_points_str, re.DOTALL)
                if console_scripts_match:
                    console_scripts = console_scripts_match.group(1)
                    for line in console_scripts.split(','):
                        line = line.strip().strip('"\'')
                        if '=' in line:
                            script_name = line.split('=')[0].strip()
                            scripts.append(script_name)
                            
        except Exception as e:
            self.console.print(f"[yellow]Warning: Could not parse setup.py: {e}[/yellow]")
            
        return scripts


class APIDocumentationFilter:
    """API文档筛选器 - 决定哪些函数值得生成文档"""
    
    def __init__(self):
        # 低价值函数的特征模式
        self.low_value_patterns = [
            r'^test_.*',  # 测试函数
            r'^_.*',      # 所有私有函数（以_开头）
            r'.*temp.*',  # 临时函数
            r'.*junk.*',  # 垃圾函数
            r'.*debug.*', # 调试函数
            r'.*tmp.*',   # 临时函数
            r'^Mock.*',   # Mock类
            r'^Test.*',   # 测试类
        ]
        
        # 低价值文件模式
        self.low_value_files = [
            r'.*test.*\.py$',
            r'.*temp.*\.py$',
            r'.*junk.*\.py$',
            r'.*debug.*\.py$',
            r'setup\.py$',
            r'conftest\.py$',
        ]
        
    def filter_valuable_apis(self, functions: List[Dict], classes: List[Dict]) -> List[Dict]:
        """筛选有价值的API"""
        valuable_apis = []
        
        # 筛选函数
        for func in functions:
            if self._is_valuable_function(func):
                valuable_apis.append({
                    'type': 'function',
                    'name': func['name'],
                    'module': func['module'],
                    'definition': func['definition'],
                    'context': func['context'],
                    'metadata': func['metadata']
                })
                
        # 筛选类
        for cls in classes:
            if self._is_valuable_class(cls):
                valuable_apis.append({
                    'type': 'class',
                    'name': cls['name'],
                    'module': cls['module'],
                    'definition': cls['definition'],
                    'context': cls['context'],
                    'metadata': cls['metadata']
                })
                
        return valuable_apis
        
    def _is_valuable_function(self, func: Dict) -> bool:
        """判断函数是否有价值"""
        name = func['name']
        file_path = func.get('file_path', '')
        
        # 检查函数名模式
        for pattern in self.low_value_patterns:
            if re.match(pattern, name, re.IGNORECASE):
                return False
                
        # 检查文件路径模式
        for pattern in self.low_value_files:
            if re.search(pattern, file_path, re.IGNORECASE):
                return False
                
        # 检查函数复杂度和文档质量
        if self._is_trivial_function(func):
            return False
            
        return True
        
    def _is_valuable_class(self, cls: Dict) -> bool:
        """判断类是否有价值"""
        name = cls['name']
        file_path = cls.get('file_path', '')
        
        # 检查类名模式
        for pattern in self.low_value_patterns:
            if re.match(pattern, name, re.IGNORECASE):
                return False
                
        # 检查文件路径模式
        for pattern in self.low_value_files:
            if re.search(pattern, file_path, re.IGNORECASE):
                return False
                
        return True
        
    def _is_trivial_function(self, func: Dict) -> bool:
        """判断是否为简单的辅助函数"""
        # 检查函数行数、复杂度等
        lines = func.get('lines', 0)
        if lines < 5:  # 过于简单的函数
            return True
            
        # 检查是否只是简单的getter/setter
        definition = func.get('definition', '')
        if 'return self.' in definition and lines < 8:
            return True
            
        # 过滤掉一些内部工具函数
        name = func.get('name', '')
        if any(keyword in name.lower() for keyword in ['helper', 'util', 'internal', 'format', 'parse', 'extract']):
            return True
            
        return False


class APIDocumentationGenerator:
    """API文档生成器 - 为单个API生成详细文档"""
    
    def __init__(self, model_client: ModelClient, debug: bool = False):
        self.model_client = model_client
        self.debug = debug
        
    def generate_api_documentation(self, definition: str, context: str, metadata: Dict) -> str:
        """为单个API生成详细的markdown文档"""
        if self.debug:
            # Debug模式下跳过大模型调用，返回简单的API文档
            return self._generate_debug_api_documentation(definition, context, metadata)
        
        # 检查model_client是否可用
        if self.model_client is None:
            return self._generate_debug_api_documentation(definition, context, metadata)
        
        prompt = self._create_api_documentation_prompt(definition, context, metadata)
        return self.model_client.generate_text(prompt)
    
    def _generate_debug_api_documentation(self, definition: str, context: str, metadata: Dict) -> str:
        """在debug模式下生成简单的API文档"""
        api_name = metadata.get('name', 'Unknown API')
        api_type = metadata.get('type', 'function')
        
        return f"""## {api_name}

**类型**: {api_type}

### 功能描述
这是一个{api_type}，具体功能请参考源代码。

### 源代码
```python
{definition}
```

### 使用示例
```python
# 示例代码
# 请根据实际情况调用此{api_type}
```

*注意：此文档在调试模式下生成，内容可能不完整。*
"""
        
    def _create_api_documentation_prompt(self, definition: str, context: str, metadata: Dict) -> str:
        """创建API文档生成的提示词"""
        return f"""
请为以下函数/类生成详细的API文档，包括：

1. 功能描述
2. 参数说明（类型、描述、默认值）
3. 返回值说明（类型、描述）
4. 源代码（在单独的代码块中显示完整的函数/类代码，包含正常的Python语法高亮）
5. 使用示例
6. 注意事项

函数/类定义：
```python
{definition}
```

上下文信息：
{context}

元数据：
{json.dumps(metadata, indent=2, ensure_ascii=False)}

请生成markdown格式的文档，确保在"源代码"部分包含一个独立的代码块，显示完整的函数/类源代码并带有Python语法高亮：
"""