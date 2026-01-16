"""
Base Agent - 智能体基类
定义所有智能体的通用接口和行为
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum


class AgentRole(Enum):
    """智能体角色"""
    ORCHESTRATOR = "orchestrator"
    CODE = "code"
    BROWSER = "browser"
    FILE = "file"
    DATA = "data"


@dataclass
class Message:
    """消息结构"""
    role: str  # "user", "assistant", "system", "tool"
    content: str
    name: Optional[str] = None
    tool_calls: Optional[List[Dict]] = None
    tool_call_id: Optional[str] = None


@dataclass
class AgentResponse:
    """智能体响应"""
    success: bool
    content: str
    data: Optional[Any] = None
    error: Optional[str] = None
    tool_calls: List[Dict] = field(default_factory=list)


class BaseAgent(ABC):
    """
    智能体基类
    
    所有专业智能体都应继承此类并实现相应方法。
    遵循 Think-Act-Observe 循环模式。
    """
    
    def __init__(
        self,
        name: str,
        role: AgentRole,
        system_prompt: str,
        tools: Optional[List] = None
    ):
        self.name = name
        self.role = role
        self.system_prompt = system_prompt
        self.tools = tools or []
        self.messages: List[Message] = []
        
    def add_message(self, message: Message):
        """添加消息到历史"""
        self.messages.append(message)
        
    def get_messages_for_llm(self) -> List[Dict]:
        """获取用于 LLM 调用的消息格式"""
        result = [{"role": "system", "content": self.system_prompt}]
        for msg in self.messages:
            msg_dict = {"role": msg.role, "content": msg.content}
            if msg.name:
                msg_dict["name"] = msg.name
            if msg.tool_calls:
                msg_dict["tool_calls"] = msg.tool_calls
            if msg.tool_call_id:
                msg_dict["tool_call_id"] = msg.tool_call_id
            result.append(msg_dict)
        return result
    
    def clear_messages(self):
        """清空消息历史"""
        self.messages = []
    
    @abstractmethod
    async def think(self, task: str) -> str:
        """
        思考阶段：分析任务，决定下一步行动
        
        Args:
            task: 任务描述
            
        Returns:
            思考结果/行动计划
        """
        pass
    
    @abstractmethod
    async def act(self, plan: str) -> AgentResponse:
        """
        行动阶段：执行具体操作
        
        Args:
            plan: 行动计划
            
        Returns:
            执行结果
        """
        pass
    
    @abstractmethod
    async def observe(self, result: AgentResponse) -> str:
        """
        观察阶段：评估执行结果
        
        Args:
            result: 行动结果
            
        Returns:
            观察总结
        """
        pass
    
    async def run(self, task: str) -> AgentResponse:
        """
        运行智能体：完整的 Think-Act-Observe 循环
        
        Args:
            task: 任务描述
            
        Returns:
            最终结果
        """
        # Think
        plan = await self.think(task)
        
        # Act
        result = await self.act(plan)
        
        # Observe
        observation = await self.observe(result)
        
        # 更新结果
        result.content = f"{result.content}\n\n观察: {observation}"
        return result
    
    def get_tools_schema(self) -> List[Dict]:
        """获取工具的 OpenAI 函数调用格式"""
        schemas = []
        for tool in self.tools:
            schemas.append({
                "type": "function",
                "function": tool.schema
            })
        return schemas
    
    def __repr__(self):
        return f"<{self.__class__.__name__} name={self.name} role={self.role.value}>"
