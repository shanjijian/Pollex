"""
Browser Agent - 浏览器智能体
负责网页搜索和内容获取
"""
import json
from typing import Optional
from openai import AsyncOpenAI

from core.agent import BaseAgent, AgentRole, AgentResponse, Message
from tools.browser import WebSearchTool, FetchURLTool
from utils.log import get_logger

logger = get_logger("agent")
from config import config


BROWSER_AGENT_PROMPT = """你是一个网页浏览智能体。你的任务是：
1. 理解用户的信息搜索需求
2. 使用搜索工具在网上查找信息
3. 必要时获取网页详细内容
4. 整理并返回有用的信息

你可以使用的工具：
- web_search: 搜索互联网信息
- fetch_url: 获取指定网页的内容

规则：
- 优先使用搜索获取概览信息
- 只在需要详细内容时才获取整个网页
- 整理信息时要准确、简洁
- 注明信息来源"""


class BrowserAgent(BaseAgent):
    """浏览器智能体"""
    
    def __init__(self):
        self.search_tool = WebSearchTool()
        self.fetch_tool = FetchURLTool()
        super().__init__(
            name="BrowserAgent",
            role=AgentRole.BROWSER,
            system_prompt=BROWSER_AGENT_PROMPT,
            tools=[self.search_tool, self.fetch_tool]
        )
        self.client: Optional[AsyncOpenAI] = None
    
    def _ensure_client(self):
        """确保 OpenAI 客户端已初始化"""
        if self.client is None:
            if config.llm_config is None:
                raise ValueError("请先调用 init_config() 初始化配置")
            self.client = AsyncOpenAI(api_key=config.llm_config.api_key, base_url=config.llm_config.base_url)
    
    async def think(self, task: str) -> str:
        """分析搜索需求"""
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
            return f"需要搜索: {len(message.tool_calls)} 个操作"
        
        return message.content or "无需搜索"
    
    async def act(self, plan: str) -> AgentResponse:
        """执行搜索操作"""
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
            
            if func_name == "web_search":
                result = await self.search_tool.execute(**func_args)
            elif func_name == "fetch_url":
                result = await self.fetch_tool.execute(**func_args)
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
        """整理搜索结果"""
        self._ensure_client()
        
        if not result.success:
            return f"搜索失败: {result.error}"
        
        self.add_message(Message(
            role="user",
            content=f"请根据搜索结果，整理出关键信息。搜索结果:\n{result.content}"
        ))
        
        response = await self.client.chat.completions.create(
            model=config.llm_config.model,
            messages=self.get_messages_for_llm(),
            temperature=0.3,
            max_tokens=1000
        )
        
        summary = response.choices[0].message.content
        self.add_message(Message(role="assistant", content=summary))
        
        return summary
    
    async def run(self, task: str) -> AgentResponse:
        """运行完整的搜索流程"""
        self.clear_messages()
        
        plan = await self.think(task)
        result = await self.act(plan)
        
        if result.success:
            observation = await self.observe(result)
            result.content = f"{result.content}\n\n📝 整理: {observation}"
        
        return result
