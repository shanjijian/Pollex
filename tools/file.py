"""
File Tools - 文件操作工具
"""
import os
from typing import Any, Dict
from .base import BaseTool, ToolResult
from utils.log import get_logger

logger = get_logger("tool")


class ReadFileTool(BaseTool):
    """读取文件工具"""
    
    @property
    def name(self) -> str:
        return "read_file"
    
    @property
    def description(self) -> str:
        return "读取指定文件的内容。"
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件路径"
                },
                "encoding": {
                    "type": "string",
                    "description": "文件编码，默认为 utf-8",
                    "default": "utf-8"
                }
            },
            "required": ["path"]
        }
    
    async def execute(self, path: str, encoding: str = "utf-8") -> ToolResult:
        """读取文件内容"""
        try:
            if not os.path.exists(path):
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"文件不存在: {path}"
                )
            
            with open(path, "r", encoding=encoding) as f:
                content = f.read()
            
            return ToolResult(success=True, output=content)
            
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))


class WriteFileTool(BaseTool):
    """写入文件工具"""
    
    @property
    def name(self) -> str:
        return "write_file"
    
    @property
    def description(self) -> str:
        return "将内容写入指定文件。如果文件不存在会创建，存在则覆盖。"
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件路径"
                },
                "content": {
                    "type": "string",
                    "description": "要写入的内容"
                },
                "encoding": {
                    "type": "string",
                    "description": "文件编码，默认为 utf-8",
                    "default": "utf-8"
                }
            },
            "required": ["path", "content"]
        }
    
    async def execute(self, path: str, content: str, encoding: str = "utf-8") -> ToolResult:
        """写入文件"""
        try:
            # 确保目录存在
            dir_path = os.path.dirname(path)
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)
            
            with open(path, "w", encoding=encoding) as f:
                f.write(content)
            
            return ToolResult(
                success=True,
                output=f"成功写入文件: {path} ({len(content)} 字符)"
            )
            
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))


class ListDirTool(BaseTool):
    """列出目录内容工具"""
    
    @property
    def name(self) -> str:
        return "list_dir"
    
    @property
    def description(self) -> str:
        return "列出指定目录下的文件和子目录。"
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "目录路径，默认为当前目录",
                    "default": "."
                },
                "recursive": {
                    "type": "boolean",
                    "description": "是否递归列出子目录，默认为 False",
                    "default": False
                }
            },
            "required": []
        }
    
    async def execute(self, path: str = ".", recursive: bool = False) -> ToolResult:
        """列出目录内容"""
        try:
            if not os.path.exists(path):
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"目录不存在: {path}"
                )
            
            if not os.path.isdir(path):
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"不是目录: {path}"
                )
            
            if recursive:
                items = []
                for root, dirs, files in os.walk(path):
                    rel_root = os.path.relpath(root, path)
                    if rel_root == ".":
                        rel_root = ""
                    for d in dirs:
                        items.append(f"[DIR]  {os.path.join(rel_root, d)}/")
                    for f in files:
                        items.append(f"[FILE] {os.path.join(rel_root, f)}")
            else:
                items = []
                for item in sorted(os.listdir(path)):
                    full_path = os.path.join(path, item)
                    if os.path.isdir(full_path):
                        items.append(f"[DIR]  {item}/")
                    else:
                        size = os.path.getsize(full_path)
                        items.append(f"[FILE] {item} ({size} bytes)")
            
            output = f"目录 '{path}' 的内容:\n" + "\n".join(items)
            return ToolResult(success=True, output=output)
            
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))
