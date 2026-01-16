"""
Data Agent - 数据分析智能体
负责数据处理和分析
"""
import json
from typing import Optional
from openai import AsyncOpenAI

from core.agent import BaseAgent, AgentRole, AgentResponse, Message
from tools.code import ExecutePythonTool
from config import config
from utils.log import get_logger

logger = get_logger("agent")


DATA_AGENT_PROMPT = """你是一个数据分析智能体。你的任务是：
1. 理解用户的数据分析需求
2. 使用 Python 进行数据处理和分析
3. 生成统计结果和可视化

你可以使用 execute_python 工具执行数据分析代码。

可用的库：
- pandas: 数据处理
- numpy: 数值计算
- matplotlib: 数据可视化
- json, csv: 数据格式处理

规则：
- 代码要高效、可读
- 处理缺失值和异常数据
- 可视化图表要清晰
- 给出分析结论"""


class DataAgent(BaseAgent):
    """数据分析智能体"""
    
    def __init__(self):
        self.execute_tool = ExecutePythonTool()
        super().__init__(
            name="DataAgent",
            role=AgentRole.DATA,
            system_prompt=DATA_AGENT_PROMPT,
            tools=[self.execute_tool]
        )
        self.client: Optional[AsyncOpenAI] = None
    
    def _ensure_client(self):
        """确保 OpenAI 客户端已初始化"""
        if self.client is None:
            if config.llm_config is None:
                raise ValueError("请先调用 init_config() 初始化配置")
            self.client = AsyncOpenAI(api_key=config.llm_config.api_key, base_url=config.llm_config.base_url)
    
    async def think(self, task: str) -> str:
        """分析数据处理需求"""
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
            return f"需要执行数据分析: {len(message.tool_calls)} 个操作"
        
        return message.content or "无需数据分析"
    
    async def act(self, plan: str) -> AgentResponse:
        """执行数据分析"""
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
            
            if func_name == "execute_python":
                result = await self.execute_tool.execute(**func_args)
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
        """分析执行结果，给出数据洞察"""
        self._ensure_client()
        
        if not result.success:
            return f"分析失败: {result.error}"
        
        self.add_message(Message(
            role="user",
            content=f"请根据数据分析结果，给出关键洞察和结论。分析结果:\n{result.content}"
        ))
        
        response = await self.client.chat.completions.create(
            model=config.llm_config.model,
            messages=self.get_messages_for_llm(),
            temperature=0.3,
            max_tokens=800
        )
        
        summary = response.choices[0].message.content
        self.add_message(Message(role="assistant", content=summary))
        
        return summary
    
    async def run(self, task: str) -> AgentResponse:
        """运行完整的数据分析流程"""
        self.clear_messages()
        
        plan = await self.think(task)
        result = await self.act(plan)
        
        if result.success:
            observation = await self.observe(result)
            result.content = f"{result.content}\n\n📊 洞察: {observation}"
        
        return result
