"""
Base Tool - 工具基类
定义所有工具的通用接口
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class ToolResult:
    """工具执行结果"""
    success: bool
    output: Any
    error: Optional[str] = None
    
    def __str__(self):
        if self.success:
            return str(self.output)
        return f"Error: {self.error}"


class BaseTool(ABC):
    """
    工具基类
    
    所有工具都应继承此类并实现 execute 方法。
    每个工具需要定义 schema 用于 OpenAI 函数调用。
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """工具名称"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """工具描述"""
        pass
    
    @property
    @abstractmethod
    def parameters(self) -> Dict[str, Any]:
        """参数定义（JSON Schema 格式）"""
        pass
    
    @property
    def schema(self) -> Dict[str, Any]:
        """OpenAI 函数调用格式的 schema"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters
        }
    
    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """
        执行工具
        
        Args:
            **kwargs: 工具参数
            
        Returns:
            ToolResult: 执行结果
        """
        pass
    
    def __repr__(self):
        return f"<Tool: {self.name}>"
