"""
Code Agent - 代码智能体
负责代码生成和执行
"""
import json
from typing import Optional
from openai import AsyncOpenAI

from core.agent import BaseAgent, AgentRole, AgentResponse, Message
from tools.code import ExecutePythonTool
from config import config
from utils.log import get_logger

logger = get_logger("agent")


CODE_AGENT_PROMPT = """你是一个专业的 Python 代码智能体。你的任务是：
1. 理解用户的编程需求
2. 编写高质量的 Python 代码
3. 执行代码并返回结果

你可以使用 execute_python 工具来运行 Python 代码。

规则：
- 代码要简洁、可读
- 包含必要的注释
- 处理可能的错误
- 如果需要导入库，使用标准库或常用库（如 math, json, datetime 等）

当你需要执行代码时，调用 execute_python 工具。"""


class CodeAgent(BaseAgent):
    """代码智能体"""
    
    def __init__(self):
        self.execute_tool = ExecutePythonTool()
        super().__init__(
            name="CodeAgent",
            role=AgentRole.CODE,
            system_prompt=CODE_AGENT_PROMPT,
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
        """分析任务，决定如何处理"""
        logger.debug(f"CodeAgent 开始分析任务: {task[:50]}...")
        self._ensure_client()
        
        self.add_message(Message(role="user", content=task))
        
        response = await self.client.chat.completions.create(
            model=config.llm_config.model,
            messages=self.get_messages_for_llm(),
            tools=self.get_tools_schema() if self.tools else None,
            temperature=config.llm_config.temperature,
        )
        
        message = response.choices[0].message
        
        # 保存助手回复
        self.add_message(Message(
            role="assistant",
            content=message.content or "",
            tool_calls=[tc.model_dump() for tc in message.tool_calls] if message.tool_calls else None
        ))
        
        if message.tool_calls:
            logger.info(f"CodeAgent 决定执行 {len(message.tool_calls)} 个工具调用")
            return f"需要执行代码: {len(message.tool_calls)} 个工具调用"
        
        logger.info("CodeAgent 无需执行代码")
        return message.content or "无需执行代码"
    
    async def act(self, plan: str) -> AgentResponse:
        """执行代码"""
        logger.debug("CodeAgent 开始执行代码...")
        # 检查最后一条消息是否有工具调用
        if not self.messages:
            logger.warning("CodeAgent 没有待执行的操作")
            return AgentResponse(success=False, content="", error="没有待执行的操作")
        
        last_message = self.messages[-1]
        if not last_message.tool_calls:
            logger.info("CodeAgent 无工具调用，直接返回内容")
            return AgentResponse(
                success=True,
                content=last_message.content,
                data=None
            )
        
        # 执行所有工具调用
        results = []
        for tool_call in last_message.tool_calls:
            func = tool_call.get("function", {})
            func_name = func.get("name")
            func_args = json.loads(func.get("arguments", "{}"))
            logger.debug(f"执行工具: {func_name} 带参数: {func_args}")
            
            if func_name == "execute_python":
                result = await self.execute_tool.execute(**func_args)
                logger.debug(f"工具执行结果: 成功={result.success}")
                results.append(result)
                
                # 添加工具结果消息
                self.add_message(Message(
                    role="tool",
                    content=str(result),
                    tool_call_id=tool_call.get("id")
                ))
        
        # 汇总结果
        all_success = all(r.success for r in results)
        content = "\n\n".join(str(r) for r in results)
        logger.info(f"CodeAgent 执行完成，成功率: {sum(1 for r in results if r.success)}/{len(results)}")
        
        return AgentResponse(
            success=all_success,
            content=content,
            data=results
        )
    
    async def observe(self, result: AgentResponse) -> str:
        """观察执行结果，生成总结"""
        self._ensure_client()
        
        if not result.success:
            return f"执行失败: {result.error}"
        
        # 让 LLM 总结结果
        self.add_message(Message(
            role="user",
            content=f"请简要总结执行结果，说明代码做了什么。执行输出:\n{result.content}"
        ))
        
        response = await self.client.chat.completions.create(
            model=config.llm_config.model,
            messages=self.get_messages_for_llm(),
            temperature=0.3,
            max_tokens=500
        )
        
        summary = response.choices[0].message.content
        self.add_message(Message(role="assistant", content=summary))
        
        return summary
    
    async def run(self, task: str) -> AgentResponse:
        """运行完整的代码生成和执行流程"""
        self.clear_messages()
        
        # Think
        plan = await self.think(task)
        
        # Act
        result = await self.act(plan)
        
        # Observe
        if result.success:
            observation = await self.observe(result)
            result.content = f"{result.content}\n\n📝 总结: {observation}"
        
        return result
