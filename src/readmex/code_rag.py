#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
代码RAG (Retrieval-Augmented Generation) 模块

提供基于语义搜索的代码理解和检索功能，用于增强文档生成的准确性和深度。

主要功能：
1. 代码块语义分析和向量化
2. 基于查询的相关代码检索
3. 上下文增强的prompt生成
4. 代码关系图构建
"""

import ast
import hashlib
import json
import pickle
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict
import re

try:
    import numpy as np
except ImportError:
    np = None

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None

try:
    import faiss
except ImportError:
    faiss = None

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

# 导入配置模块
try:
    from .config import get_embedding_config
except ImportError:
    # 如果是直接运行此文件，使用相对导入
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent))
    from config import get_embedding_config


@dataclass
class CodeBlock:
    """代码块数据结构"""
    id: str
    type: str  # 'function', 'class', 'method', 'import', 'variable'
    name: str
    content: str
    file_path: str
    module: str
    line_start: int
    line_end: int
    docstring: Optional[str] = None
    signature: Optional[str] = None
    dependencies: List[str] = None
    complexity: int = 1
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []
        if self.metadata is None:
            self.metadata = {}


@dataclass
class CodeRelation:
    """代码关系数据结构"""
    source_id: str
    target_id: str
    relation_type: str  # 'calls', 'inherits', 'imports', 'uses', 'defines'
    strength: float = 1.0
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class CodeRAG:
    """代码RAG系统核心类"""
    
    def __init__(self, project_dir: str, cache_dir: str = None, model_name: str = None, use_local_embedding: bool = None):
        self.project_dir = Path(project_dir)
        self.cache_dir = Path(cache_dir) if cache_dir else self.project_dir / ".rag_cache"
        self.cache_dir.mkdir(exist_ok=True)
        
        self.console = Console()
        
        # 获取embedding配置
        self.embedding_config = get_embedding_config()
        
        # 确定是否使用本地embedding
        if use_local_embedding is not None:
            self.use_local_embedding = use_local_embedding
        else:
            self.use_local_embedding = self.embedding_config.get('local_embedding', True)
        
        # 设置模型名称
        if model_name is not None:
            self.model_name = model_name
        elif self.use_local_embedding:
            self.model_name = "Kwaipilot/OASIS-code-embedding-1.5B"  # 默认本地模型
        else:
            self.model_name = self.embedding_config.get('model_name', 'text-embedding-3-small')
        
        self.embedding_model = None
        self.index = None
        
        # 数据存储
        self.code_blocks: Dict[str, CodeBlock] = {}
        self.relations: List[CodeRelation] = []
        self.embeddings: Optional[np.ndarray] = None
        self.id_to_index: Dict[str, int] = {}
        
        # 缓存文件路径
        self.blocks_cache_file = self.cache_dir / "code_blocks.pkl"
        self.relations_cache_file = self.cache_dir / "relations.pkl"
        self.embeddings_cache_file = self.cache_dir / "embeddings.pkl"
        self.index_cache_file = self.cache_dir / "faiss_index.bin"
        
        self._check_dependencies()
    
    def _check_dependencies(self):
        """检查依赖包"""
        missing_deps = []
        
        if SentenceTransformer is None:
            missing_deps.append("sentence-transformers")
        if np is None:
            missing_deps.append("numpy")
        if faiss is None:
            missing_deps.append("faiss-cpu")
            
        if missing_deps:
            self.console.print(f"[yellow]警告: 缺少RAG高级功能依赖包: {', '.join(missing_deps)}[/yellow]")
            self.console.print("[yellow]将使用基础文本匹配模式[/yellow]")
            self.console.print("[dim]如需完整RAG功能，请运行: pip install sentence-transformers numpy faiss-cpu[/dim]")
            return False
        return True
    
    def _load_embedding_model(self):
        """加载嵌入模型"""
        if self.embedding_model is not None:
            return True
            
        if self.use_local_embedding:
            # 使用本地模型
            if SentenceTransformer is not None:
                try:
                    self.embedding_model = SentenceTransformer(self.model_name)
                    self.console.print(f"[green]已加载本地嵌入模型: {self.model_name}[/green]")
                    return True
                except Exception as e:
                    self.console.print(f"[red]加载本地嵌入模型失败: {e}[/red]")
                    return False
            else:
                self.console.print("[red]缺少sentence-transformers依赖包，无法使用本地embedding模型[/red]")
                return False
        else:
            # 使用web模型
            try:
                from .utils.model_client import ModelClient
                self.embedding_model = ModelClient()
                self.console.print(f"[green]已配置Web嵌入模型: {self.model_name}[/green]")
                return True
            except Exception as e:
                self.console.print(f"[red]配置Web嵌入模型失败: {e}[/red]")
                return False
    
    def _generate_block_id(self, file_path: str, name: str, line_start: int) -> str:
        """生成代码块唯一ID"""
        content = f"{file_path}:{name}:{line_start}"
        return hashlib.md5(content.encode()).hexdigest()[:12]
    
    def extract_code_blocks(self, force_refresh: bool = False) -> Dict[str, CodeBlock]:
        """提取项目中的所有代码块"""
        if not force_refresh and self._load_from_cache():
            return self.code_blocks
            
        self.console.print("[blue]开始提取代码块...[/blue]")
        self.code_blocks.clear()
        
        python_files = list(self.project_dir.rglob('*.py'))
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console
        ) as progress:
            task = progress.add_task("提取代码块", total=len(python_files))
            
            for file_path in python_files:
                try:
                    self._extract_file_blocks(file_path)
                    progress.advance(task)
                except Exception as e:
                    self.console.print(f"[red]处理文件 {file_path} 时出错: {e}[/red]")
                    progress.advance(task)
        
        self._extract_relations()
        self._save_to_cache()
        
        self.console.print(f"[green]提取完成，共 {len(self.code_blocks)} 个代码块[/green]")
        return self.code_blocks
    
    def _extract_file_blocks(self, file_path: Path):
        """从单个文件提取代码块"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            module_name = self._get_module_name(file_path)
            
            # 提取导入语句
            self._extract_imports(tree, file_path, module_name, content)
            
            # 提取函数和类
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    self._extract_function_block(node, file_path, module_name, content)
                elif isinstance(node, ast.ClassDef):
                    self._extract_class_block(node, file_path, module_name, content)
                    
        except Exception as e:
            self.console.print(f"[red]解析文件 {file_path} 失败: {e}[/red]")
    
    def _extract_imports(self, tree: ast.AST, file_path: Path, module_name: str, content: str):
        """提取导入语句"""
        lines = content.split('\n')
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                import_content = lines[node.lineno - 1].strip()
                
                block_id = self._generate_block_id(str(file_path), f"import_{node.lineno}", node.lineno)
                
                block = CodeBlock(
                    id=block_id,
                    type='import',
                    name=import_content,
                    content=import_content,
                    file_path=str(file_path),
                    module=module_name,
                    line_start=node.lineno,
                    line_end=node.lineno,
                    metadata={'import_type': 'from' if isinstance(node, ast.ImportFrom) else 'direct'}
                )
                
                self.code_blocks[block_id] = block
    
    def _extract_function_block(self, node: ast.FunctionDef, file_path: Path, module_name: str, content: str):
        """提取函数代码块"""
        lines = content.split('\n')
        
        # 提取函数内容
        start_line = node.lineno
        end_line = getattr(node, 'end_lineno', node.lineno)
        func_content = '\n'.join(lines[start_line-1:end_line])
        
        # 提取文档字符串
        docstring = ast.get_docstring(node)
        
        # 生成函数签名
        signature = self._generate_function_signature(node)
        
        # 计算复杂度
        complexity = self._calculate_complexity(node)
        
        # 提取依赖（函数调用）
        dependencies = self._extract_function_dependencies(node)
        
        block_id = self._generate_block_id(str(file_path), node.name, start_line)
        
        block = CodeBlock(
            id=block_id,
            type='function',
            name=node.name,
            content=func_content,
            file_path=str(file_path),
            module=module_name,
            line_start=start_line,
            line_end=end_line,
            docstring=docstring,
            signature=signature,
            dependencies=dependencies,
            complexity=complexity,
            metadata={
                'args': [arg.arg for arg in node.args.args],
                'returns': bool(node.returns),
                'is_async': isinstance(node, ast.AsyncFunctionDef),
                'decorators': [ast.unparse(d) for d in node.decorator_list] if hasattr(ast, 'unparse') else []
            }
        )
        
        self.code_blocks[block_id] = block
    
    def _extract_class_block(self, node: ast.ClassDef, file_path: Path, module_name: str, content: str):
        """提取类代码块"""
        lines = content.split('\n')
        
        # 提取类内容
        start_line = node.lineno
        end_line = getattr(node, 'end_lineno', node.lineno)
        class_content = '\n'.join(lines[start_line-1:end_line])
        
        # 提取文档字符串
        docstring = ast.get_docstring(node)
        
        # 提取方法
        methods = [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
        
        # 提取基类
        bases = [ast.unparse(base) for base in node.bases] if hasattr(ast, 'unparse') else []
        
        block_id = self._generate_block_id(str(file_path), node.name, start_line)
        
        block = CodeBlock(
            id=block_id,
            type='class',
            name=node.name,
            content=class_content,
            file_path=str(file_path),
            module=module_name,
            line_start=start_line,
            line_end=end_line,
            docstring=docstring,
            metadata={
                'methods': methods,
                'bases': bases,
                'decorators': [ast.unparse(d) for d in node.decorator_list] if hasattr(ast, 'unparse') else []
            }
        )
        
        self.code_blocks[block_id] = block
        
        # 提取类中的方法
        for method_node in node.body:
            if isinstance(method_node, ast.FunctionDef):
                self._extract_method_block(method_node, node.name, file_path, module_name, content)
    
    def _extract_method_block(self, node: ast.FunctionDef, class_name: str, file_path: Path, module_name: str, content: str):
        """提取方法代码块"""
        lines = content.split('\n')
        
        start_line = node.lineno
        end_line = getattr(node, 'end_lineno', node.lineno)
        method_content = '\n'.join(lines[start_line-1:end_line])
        
        docstring = ast.get_docstring(node)
        signature = self._generate_function_signature(node)
        complexity = self._calculate_complexity(node)
        dependencies = self._extract_function_dependencies(node)
        
        block_id = self._generate_block_id(str(file_path), f"{class_name}.{node.name}", start_line)
        
        block = CodeBlock(
            id=block_id,
            type='method',
            name=f"{class_name}.{node.name}",
            content=method_content,
            file_path=str(file_path),
            module=module_name,
            line_start=start_line,
            line_end=end_line,
            docstring=docstring,
            signature=signature,
            dependencies=dependencies,
            complexity=complexity,
            metadata={
                'class': class_name,
                'method_name': node.name,
                'args': [arg.arg for arg in node.args.args],
                'returns': bool(node.returns),
                'is_async': isinstance(node, ast.AsyncFunctionDef),
                'decorators': [ast.unparse(d) for d in node.decorator_list] if hasattr(ast, 'unparse') else []
            }
        )
        
        self.code_blocks[block_id] = block
    
    def _generate_function_signature(self, node: ast.FunctionDef) -> str:
        """生成函数签名"""
        args = []
        
        # 普通参数
        for arg in node.args.args:
            arg_str = arg.arg
            if arg.annotation:
                if hasattr(ast, 'unparse'):
                    arg_str += f": {ast.unparse(arg.annotation)}"
            args.append(arg_str)
        
        # 默认参数
        defaults = node.args.defaults
        if defaults:
            for i, default in enumerate(defaults):
                arg_index = len(args) - len(defaults) + i
                if hasattr(ast, 'unparse'):
                    args[arg_index] += f" = {ast.unparse(default)}"
        
        # 返回类型
        return_annotation = ""
        if node.returns and hasattr(ast, 'unparse'):
            return_annotation = f" -> {ast.unparse(node.returns)}"
        
        return f"def {node.name}({', '.join(args)}){return_annotation}:"
    
    def _extract_function_dependencies(self, node: ast.FunctionDef) -> List[str]:
        """提取函数依赖（调用的其他函数）"""
        dependencies = []
        
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name):
                    dependencies.append(child.func.id)
                elif isinstance(child.func, ast.Attribute):
                    if hasattr(ast, 'unparse'):
                        dependencies.append(ast.unparse(child.func))
        
        return list(set(dependencies))  # 去重
    
    def _calculate_complexity(self, node: ast.FunctionDef) -> int:
        """计算函数复杂度
        
        使用简化的圈复杂度(Cyclomatic Complexity)计算方法，评估代码的复杂程度。
        复杂度计算标准:
        - 基础复杂度为1
        - 每个控制流语句(if/while/for/try/with)增加1点复杂度
        - 每个布尔运算(and/or)增加相应的复杂度
        
        复杂度参考标准:
        1-5: 简单函数
        6-10: 中等复杂
        >10: 高复杂度,建议重构
        
        Args:
            node: AST函数节点
            
        Returns:
            int: 计算出的复杂度分数
        """
        complexity = 1  # 基础复杂度
        
        for child in ast.walk(node):
            # 控制流语句增加复杂度
            if isinstance(child, (ast.If, ast.While, ast.For, ast.Try, ast.With)):
                complexity += 1
            # 布尔运算(and/or)增加复杂度
            elif isinstance(child, ast.BoolOp):
                # 例如: a and b and c 的复杂度为2(操作数数量-1)
                complexity += len(child.values) - 1
        
        return complexity
    
    def _extract_relations(self):
        """提取代码块之间的关系"""
        self.relations.clear()
        
        for block in self.code_blocks.values():
            # 函数调用关系
            for dep in block.dependencies:
                target_blocks = [b for b in self.code_blocks.values() if b.name == dep or b.name.endswith(f".{dep}")]
                for target in target_blocks:
                    relation = CodeRelation(
                        source_id=block.id,
                        target_id=target.id,
                        relation_type='calls',
                        strength=1.0
                    )
                    self.relations.append(relation)
            
            # 类继承关系
            if block.type == 'class' and 'bases' in block.metadata:
                for base in block.metadata['bases']:
                    target_blocks = [b for b in self.code_blocks.values() if b.name == base]
                    for target in target_blocks:
                        relation = CodeRelation(
                            source_id=block.id,
                            target_id=target.id,
                            relation_type='inherits',
                            strength=1.0
                        )
                        self.relations.append(relation)
    
    def _get_module_name(self, file_path: Path) -> str:
        """获取模块名"""
        try:
            relative_path = file_path.relative_to(self.project_dir)
            return str(relative_path).replace('/', '.').replace('\\', '.').replace('.py', '')
        except ValueError:
            return file_path.stem
    
    def build_embeddings(self, force_rebuild: bool = False) -> bool:
        """构建代码块的向量嵌入"""
        if not self._load_embedding_model():
            self.console.print("[yellow]向量嵌入功能不可用，将使用文本匹配模式[/yellow]")
            return False
            
        if not force_rebuild and self._load_embeddings_from_cache():
            return True
        
        if not self.code_blocks:
            self.console.print("[yellow]没有代码块数据，请先运行 extract_code_blocks()[/yellow]")
            return False
        
        self.console.print("[blue]开始构建向量嵌入...[/blue]")
        
        # 准备文本数据
        texts = []
        block_ids = []
        
        for block_id, block in self.code_blocks.items():
            # 构建用于嵌入的文本
            text_parts = []
            
            # 添加名称和类型
            text_parts.append(f"Type: {block.type}")
            text_parts.append(f"Name: {block.name}")
            
            # 添加签名（如果有）
            if block.signature:
                text_parts.append(f"Signature: {block.signature}")
            
            # 添加文档字符串
            if block.docstring:
                text_parts.append(f"Documentation: {block.docstring}")
            
            # 添加代码内容（截取前500字符）
            content_preview = block.content[:500] if len(block.content) > 500 else block.content
            text_parts.append(f"Code: {content_preview}")
            
            # 添加依赖信息
            if block.dependencies:
                text_parts.append(f"Dependencies: {', '.join(block.dependencies)}")
            
            text = "\n".join(text_parts)
            texts.append(text)
            block_ids.append(block_id)
        
        # 生成嵌入
        try:
            if self.embedding_model is None:
                self.console.print("[yellow]向量嵌入模型未加载，跳过向量化[/yellow]")
                return False
                
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=self.console
            ) as progress:
                task = progress.add_task("生成向量嵌入", total=1)
                
                if self.use_local_embedding:
                    # 使用本地模型
                    self.embeddings = self.embedding_model.encode(texts, show_progress_bar=False)
                else:
                    # 使用web模型
                    self.embeddings = self._get_web_embeddings(texts)
                    
                self.id_to_index = {block_id: i for i, block_id in enumerate(block_ids)}
                
                progress.advance(task)
            
            # 构建FAISS索引
            if faiss is not None:
                self._build_faiss_index()
            
            self._save_embeddings_to_cache()
            
            self.console.print(f"[green]向量嵌入构建完成，共 {len(texts)} 个向量[/green]")
            return True
            
        except Exception as e:
            self.console.print(f"[red]构建向量嵌入失败: {e}[/red]")
            return False
    
    def _get_web_embeddings(self, texts: List[str]) -> np.ndarray:
        """使用web API获取文本嵌入"""
        try:
            import requests
            import json
            
            # 获取配置
            api_key = self.embedding_config.get('api_key')
            base_url = self.embedding_config.get('base_url', 'https://api.openai.com/v1')
            model_name = self.embedding_config.get('model_name', 'text-embedding-3-small')
            
            if not api_key:
                raise ValueError("缺少embedding API key")
            
            # 准备请求
            url = f"{base_url.rstrip('/')}/embeddings"
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }
            
            embeddings = []
            
            # 批量处理文本（避免单次请求过大）
            batch_size = 100  # 每批处理100个文本
            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i:i + batch_size]
                
                data = {
                    'input': batch_texts,
                    'model': model_name
                }
                
                response = requests.post(url, headers=headers, json=data, timeout=60)
                response.raise_for_status()
                
                result = response.json()
                
                # 提取嵌入向量
                batch_embeddings = [item['embedding'] for item in result['data']]
                embeddings.extend(batch_embeddings)
            
            return np.array(embeddings, dtype=np.float32)
            
        except Exception as e:
            self.console.print(f"[red]获取web embedding失败: {e}[/red]")
            raise
    
    def _build_faiss_index(self):
        """构建FAISS索引"""
        if self.embeddings is None or faiss is None:
            return
        
        dimension = self.embeddings.shape[1]
        self.index = faiss.IndexFlatIP(dimension)  # 使用内积相似度
        
        # 归一化向量
        faiss.normalize_L2(self.embeddings)
        self.index.add(self.embeddings)
    
    def semantic_search(self, query: str, top_k: int = 5, min_score: float = 0.3) -> List[Tuple[CodeBlock, float]]:
        """语义搜索相关代码块"""
        try:
            # 如果有向量嵌入，使用语义搜索
            if self.embeddings is not None and self._load_embedding_model():
                return self._vector_search(query, top_k, min_score)
            else:
                # 否则使用文本匹配搜索
                return self._text_search(query, top_k, min_score)
        except Exception as e:
            self.console.print(f"[yellow]语义搜索失败: {e}，使用文本搜索[/yellow]")
            return self._text_search(query, top_k, min_score)
    
    def _vector_search(self, query: str, top_k: int, min_score: float) -> List[Tuple[CodeBlock, float]]:
        """基于向量的语义搜索"""
        try:
            # 生成查询向量
            if self.use_local_embedding:
                query_embedding = self.embedding_model.encode([query])
            else:
                query_embedding = self._get_web_embeddings([query])
            
            # 检查向量维度是否匹配
            if self.embeddings is not None and query_embedding.shape[1] != self.embeddings.shape[1]:
                self.console.print(f"[yellow]向量维度不匹配: 查询向量 {query_embedding.shape[1]}, 索引向量 {self.embeddings.shape[1]}[/yellow]")
                self.console.print("[yellow]回退到文本搜索模式[/yellow]")
                return self._text_search(query, top_k, min_score)
            
            if faiss is not None and self.index is not None:
                # 使用FAISS搜索
                faiss.normalize_L2(query_embedding)
                scores, indices = self.index.search(query_embedding, top_k)
                
                results = []
                for score, idx in zip(scores[0], indices[0]):
                    if score >= min_score:
                        block_id = list(self.id_to_index.keys())[list(self.id_to_index.values()).index(idx)]
                        block = self.code_blocks[block_id]
                        results.append((block, float(score)))
                
                return results
            else:
                # 使用numpy计算相似度
                similarities = np.dot(self.embeddings, query_embedding.T).flatten()
                
                # 获取top_k结果
                top_indices = np.argsort(similarities)[::-1][:top_k]
                
                results = []
                for idx in top_indices:
                    score = similarities[idx]
                    if score >= min_score:
                        block_id = list(self.id_to_index.keys())[list(self.id_to_index.values()).index(idx)]
                        block = self.code_blocks[block_id]
                        results.append((block, float(score)))
                
                return results
        except Exception as e:
            self.console.print(f"[yellow]向量搜索失败: {e}，回退到文本搜索[/yellow]")
            return self._text_search(query, top_k, min_score)
    
    def _text_search(self, query: str, top_k: int, min_score: float = 0.1) -> List[Tuple[CodeBlock, float]]:
        """基于文本匹配的搜索（备选方案）"""
        if not self.code_blocks:
            return []
        
        query_terms = set(query.lower().split())
        results = []
        
        for block in self.code_blocks.values():
            # 构建搜索文本
            search_text = f"{block.name} {block.type} {block.content}"
            if block.docstring:
                search_text += f" {block.docstring}"
            if block.signature:
                search_text += f" {block.signature}"
            
            search_text = search_text.lower()
            
            # 计算匹配分数
            score = 0.0
            matched_terms = 0
            
            for term in query_terms:
                if term in search_text:
                    matched_terms += 1
                    # 名称匹配权重更高
                    if term in block.name.lower():
                        score += 0.5
                    # 文档字符串匹配
                    elif block.docstring and term in block.docstring.lower():
                        score += 0.3
                    # 代码内容匹配
                    else:
                        score += 0.1
            
            # 计算最终分数（匹配率 * 权重分数）
            if matched_terms > 0:
                match_ratio = matched_terms / len(query_terms)
                final_score = match_ratio * score
                
                if final_score >= min_score:
                    results.append((block, final_score))
        
        # 按分数排序并返回top_k
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]
    
    def get_related_blocks(self, block_id: str, relation_types: List[str] = None, max_depth: int = 2) -> List[CodeBlock]:
        """获取与指定代码块相关的其他代码块"""
        if relation_types is None:
            relation_types = ['calls', 'inherits', 'uses']
        
        visited = set()
        related_blocks = []
        queue = [(block_id, 0)]
        
        while queue:
            current_id, depth = queue.pop(0)
            
            if current_id in visited or depth > max_depth:
                continue
            
            visited.add(current_id)
            
            if current_id != block_id and current_id in self.code_blocks:
                related_blocks.append(self.code_blocks[current_id])
            
            # 查找相关的代码块
            for relation in self.relations:
                if relation.relation_type in relation_types:
                    if relation.source_id == current_id and relation.target_id not in visited:
                        queue.append((relation.target_id, depth + 1))
                    elif relation.target_id == current_id and relation.source_id not in visited:
                        queue.append((relation.source_id, depth + 1))
        
        return related_blocks
    
    def generate_enhanced_prompt(self, base_prompt: str, query: str, max_context_blocks: int = 10) -> str:
        """生成增强的prompt，包含相关代码上下文"""
        # 搜索相关代码块
        relevant_blocks = self.semantic_search(query, top_k=max_context_blocks)
        
        if not relevant_blocks:
            return base_prompt
        
        # 构建上下文信息
        context_parts = []
        context_parts.append("\n=== 相关代码上下文 ===")
        
        for i, (block, score) in enumerate(relevant_blocks, 1):
            context_parts.append(f"\n--- 代码块 {i} (相似度: {score:.3f}) ---")
            context_parts.append(f"类型: {block.type}")
            context_parts.append(f"名称: {block.name}")
            context_parts.append(f"文件: {block.file_path}")
            context_parts.append(f"模块: {block.module}")
            
            if block.signature:
                context_parts.append(f"签名: {block.signature}")
            
            if block.docstring:
                context_parts.append(f"文档: {block.docstring}")
            
            # 添加代码内容（限制长度）
            content = block.content
            if len(content) > 300:
                content = content[:300] + "..."
            context_parts.append(f"代码:\n{content}")
            
            if block.dependencies:
                context_parts.append(f"依赖: {', '.join(block.dependencies)}")
        
        context_parts.append("\n=== 上下文结束 ===\n")
        
        # 组合prompt
        enhanced_prompt = base_prompt + "\n" + "\n".join(context_parts)
        
        return enhanced_prompt
    
    def get_code_statistics(self) -> Dict[str, Any]:
        """获取代码统计信息"""
        if not self.code_blocks:
            return {}
        
        stats = {
            'total_blocks': len(self.code_blocks),
            'by_type': defaultdict(int),
            'by_module': defaultdict(int),
            'complexity_distribution': defaultdict(int),
            'total_lines': 0,
            'avg_complexity': 0
        }
        
        total_complexity = 0
        
        for block in self.code_blocks.values():
            stats['by_type'][block.type] += 1
            stats['by_module'][block.module] += 1
            stats['total_lines'] += block.line_end - block.line_start + 1
            
            complexity = block.complexity
            total_complexity += complexity
            
            if complexity <= 5:
                stats['complexity_distribution']['simple'] += 1
            elif complexity <= 10:
                stats['complexity_distribution']['moderate'] += 1
            else:
                stats['complexity_distribution']['complex'] += 1
        
        stats['avg_complexity'] = total_complexity / len(self.code_blocks) if self.code_blocks else 0
        stats['by_type'] = dict(stats['by_type'])
        stats['by_module'] = dict(stats['by_module'])
        stats['complexity_distribution'] = dict(stats['complexity_distribution'])
        
        return stats
    
    def _save_to_cache(self):
        """保存数据到缓存"""
        try:
            with open(self.blocks_cache_file, 'wb') as f:
                pickle.dump(self.code_blocks, f)
            
            with open(self.relations_cache_file, 'wb') as f:
                pickle.dump(self.relations, f)
                
        except Exception as e:
            self.console.print(f"[yellow]保存缓存失败: {e}[/yellow]")
    
    def _load_from_cache(self) -> bool:
        """从缓存加载数据"""
        try:
            if self.blocks_cache_file.exists() and self.relations_cache_file.exists():
                with open(self.blocks_cache_file, 'rb') as f:
                    self.code_blocks = pickle.load(f)
                
                with open(self.relations_cache_file, 'rb') as f:
                    self.relations = pickle.load(f)
                
                self.console.print(f"[green]从缓存加载了 {len(self.code_blocks)} 个代码块[/green]")
                return True
        except Exception as e:
            self.console.print(f"[yellow]加载缓存失败: {e}[/yellow]")
        
        return False
    
    def _save_embeddings_to_cache(self):
        """保存嵌入向量到缓存"""
        try:
            cache_data = {
                'embeddings': self.embeddings,
                'id_to_index': self.id_to_index
            }
            
            with open(self.embeddings_cache_file, 'wb') as f:
                pickle.dump(cache_data, f)
            
            if self.index is not None and faiss is not None:
                faiss.write_index(self.index, str(self.index_cache_file))
                
        except Exception as e:
            self.console.print(f"[yellow]保存嵌入缓存失败: {e}[/yellow]")
    
    def _load_embeddings_from_cache(self) -> bool:
        """从缓存加载嵌入向量"""
        try:
            if self.embeddings_cache_file.exists():
                with open(self.embeddings_cache_file, 'rb') as f:
                    cache_data = pickle.load(f)
                
                self.embeddings = cache_data['embeddings']
                self.id_to_index = cache_data['id_to_index']
                
                # 加载FAISS索引
                if self.index_cache_file.exists() and faiss is not None:
                    self.index = faiss.read_index(str(self.index_cache_file))
                
                self.console.print(f"[green]从缓存加载了 {len(self.embeddings)} 个向量嵌入[/green]")
                return True
        except Exception as e:
            self.console.print(f"[yellow]加载嵌入缓存失败: {e}[/yellow]")
        
        return False
    
    def clear_cache(self):
        """清除所有缓存"""
        cache_files = [
            self.blocks_cache_file,
            self.relations_cache_file,
            self.embeddings_cache_file,
            self.index_cache_file
        ]
        
        for cache_file in cache_files:
            if cache_file.exists():
                cache_file.unlink()
        
        self.console.print("[green]缓存已清除[/green]")