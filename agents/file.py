"""
File Agent - 文件智能体
负责文件读写和目录管理
"""
import json
from typing import Optional
from openai import AsyncOpenAI

from core.agent import BaseAgent, AgentRole, AgentResponse, Message
from tools.file import ReadFileTool, WriteFileTool, ListDirTool
from utils.log import get_logger
from config import config

logger = get_logger("agent")


FILE_AGENT_PROMPT = """你是一个文件管理智能体。你的任务是：
1. 理解用户的文件操作需求
2. 执行文件读取、写入和目录操作
3. 安全地处理文件系统

你可以使用的工具：
- read_file: 读取文件内容
- write_file: 写入文件
- list_dir: 列出目录内容

规则：
- 操作前确认路径正确
- 写入前提醒可能覆盖现有内容
- 不操作敏感系统文件
- 遇到错误时给出清晰的说明"""


class FileAgent(BaseAgent):
    """文件智能体"""
    
    def __init__(self):
        self.read_tool = ReadFileTool()
        self.write_tool = WriteFileTool()
        self.list_tool = ListDirTool()
        super().__init__(
            name="FileAgent",
            role=AgentRole.FILE,
            system_prompt=FILE_AGENT_PROMPT,
            tools=[self.read_tool, self.write_tool, self.list_tool]
        )
        self.client: Optional[AsyncOpenAI] = None
    
    def _ensure_client(self):
        """确保 OpenAI 客户端已初始化"""
        if self.client is None:
            if config.llm_config is None:
                raise ValueError("请先调用 init_config() 初始化配置")
            self.client = AsyncOpenAI(api_key=config.llm_config.api_key, base_url=config.llm_config.base_url)
    
    async def think(self, task: str) -> str:
        """分析文件操作需求"""
        self._ensure_client()
        
        self.add_message(Message(role="user", content=task))
        
        response = await self.client.chat.completions.create(
            model=config.llm_config.model,
            messages=self.get_messages_for_llm(),
            tools=self.get_tools_schema(),
            temperature=config.llm_config.temperature,
        )
        
        message = response.choices[0].message
        
        self.add_message(Message(
            role="assistant",
            content=message.content or "",
            tool_calls=[tc.model_dump() for tc in message.tool_calls] if message.tool_calls else None
        ))
        
        if message.tool_calls:
            return f"需要执行文件操作: {len(message.tool_calls)} 个"
        
        return message.content or "无需文件操作"
    
    async def act(self, plan: str) -> AgentResponse:
        """执行文件操作"""
        if not self.messages:
            return AgentResponse(success=False, content="", error="没有待执行的操作")
        
        last_message = self.messages[-1]
        if not last_message.tool_calls:
            return AgentResponse(
                success=True,
                content=last_message.content,
                data=None
            )
        
        results = []
        for tool_call in last_message.tool_calls:
            func = tool_call.get("function", {})
            func_name = func.get("name")
            func_args = json.loads(func.get("arguments", "{}"))
            
            if func_name == "read_file":
                result = await self.read_tool.execute(**func_args)
            elif func_name == "write_file":
                result = await self.write_tool.execute(**func_args)
            elif func_name == "list_dir":
                result = await self.list_tool.execute(**func_args)
            else:
                continue
            
            results.append(result)
            self.add_message(Message(
                role="tool",
                content=str(result),
                tool_call_id=tool_call.get("id")
            ))
        
        all_success = all(r.success for r in results)
        content = "\n\n".join(str(r) for r in results)
        
        return AgentResponse(
            success=all_success,
            content=content,
            data=results
        )
    
    async def observe(self, result: AgentResponse) -> str:
        """总结文件操作结果"""
        self._ensure_client()
        
        if not result.success:
            return f"操作失败: {result.error}"
        
        self.add_message(Message(
            role="user",
            content=f"请简要说明完成了什么文件操作。结果:\n{result.content[:2000]}"
        ))
        
        response = await self.client.chat.completions.create(
            model=config.llm_config.model,
            messages=self.get_messages_for_llm(),
            temperature=0.3,
            max_tokens=300
        )
        
        summary = response.choices[0].message.content
        self.add_message(Message(role="assistant", content=summary))
        
        return summary
    
    async def run(self, task: str) -> AgentResponse:
        """运行完整的文件操作流程"""
        self.clear_messages()
        
        plan = await self.think(task)
        result = await self.act(plan)
        
        if result.success:
            observation = await self.observe(result)
            result.content = f"{result.content}\n\n📝 总结: {observation}"
        
        return result
