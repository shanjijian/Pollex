"""
Orchestrator - 编排器
中央智能体，负责任务分解和智能体调度
"""
import json
from typing import Dict, List, Optional
from openai import AsyncOpenAI
from dataclasses import dataclass

from core.agent import BaseAgent, AgentRole, AgentResponse, Message
from agents.code import CodeAgent
from agents.browser import BrowserAgent
from agents.file import FileAgent
from agents.data import DataAgent
from core.memory import Memory
from config import config
from utils.log import get_logger

logger = get_logger("core")


@dataclass
class TaskPlan:
    """任务计划"""
    original_task: str
    subtasks: List[Dict]
    current_step: int = 0


ORCHESTRATOR_PROMPT = """你是一个任务编排智能体（Orchestrator）。你负责：
1. 分析用户的复杂任务
2. 将任务分解为可执行的子任务
3. 为每个子任务选择合适的专业智能体
4. 协调智能体之间的协作
5. 汇总结果返回给用户

你可用的专业智能体：
- code: 代码生成和执行（Python）
- browser: 网页搜索和内容获取
- file: 文件读写和目录管理
- data: 数据分析和可视化

你需要分析任务，然后调用 assign_task 工具来分配子任务。

输出格式要求：当你决定分配任务时，使用 assign_task 工具，参数如下：
- agent: 选择的智能体类型（code/browser/file/data）
- task: 具体的子任务描述
- reason: 选择该智能体的原因

如果任务可以直接回答不需要调用智能体，直接回复即可。"""


class Orchestrator(BaseAgent):
    """
    编排器 - 多智能体系统的核心
    
    负责：
    - 任务分析和分解
    - 智能体选择和调度
    - 结果汇总和迭代
    """
    
    def __init__(self):
        super().__init__(
            name="Orchestrator",
            role=AgentRole.ORCHESTRATOR,
            system_prompt=ORCHESTRATOR_PROMPT,
            tools=[]
        )
        
        # 初始化专业智能体
        self.agents: Dict[str, BaseAgent] = {
            "code": CodeAgent(),
            "browser": BrowserAgent(),
            "file": FileAgent(),
            "data": DataAgent(),
        }
        
        # 内存系统
        self.memory = Memory()
        
        # 当前任务计划
        self.current_plan: Optional[TaskPlan] = None
        
        # OpenAI 客户端
        self.client: Optional[AsyncOpenAI] = None
    
    def _ensure_client(self):
        """确保 OpenAI 客户端已初始化"""
        if self.client is None:
            if config.llm_config is None:
                raise ValueError("请先调用 init_config() 初始化配置")
            self.client = AsyncOpenAI(api_key=config.llm_config.api_key, base_url=config.llm_config.base_url)
    
    def _get_tools_schema(self) -> List[Dict]:
        """获取编排器可用的工具"""
        return [{
            "type": "function",
            "function": {
                "name": "assign_task",
                "description": "将子任务分配给专业智能体执行",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "agent": {
                            "type": "string",
                            "enum": ["code", "browser", "file", "data"],
                            "description": "选择的智能体类型"
                        },
                        "task": {
                            "type": "string",
                            "description": "具体的子任务描述"
                        },
                        "reason": {
                            "type": "string",
                            "description": "选择该智能体的原因"
                        }
                    },
                    "required": ["agent", "task", "reason"]
                }
            }
        }]
    
    async def think(self, task: str) -> str:
        """
        分析任务，制定执行计划
        """
        logger.info("\n🤖 [ORCHESTRATOR] 思考中...")
        self._ensure_client()
        
        # 添加上下文
        context = self.memory.get_context(limit=5)
        if context:
            enhanced_task = f"上下文:\n{context}\n\n当前任务: {task}"
            logger.info(f"   添加上下文信息")
            logger.info(f"   上下文内容: {context}")
        else:
            enhanced_task = task
        
        self.add_message(Message(role="user", content=enhanced_task))
        
        response = await self.client.chat.completions.create(
            model=config.llm_config.model,
            messages=self.get_messages_for_llm(),
            tools=self._get_tools_schema(),
            temperature=config.llm_config.temperature,
        )
        message = response.choices[0].message
        
        self.add_message(Message(
            role="assistant",
            content=message.content or "",
            tool_calls=[tc.model_dump() for tc in message.tool_calls] if message.tool_calls else None
        ))
        
        # 保存到记忆
        self.memory.add_short_term(f"任务: {task}", type="task")
        
        if message.tool_calls:
            subtasks = []
            for tc in message.tool_calls:
                func = tc.function
                args = json.loads(func.arguments)
                subtasks.append({
                    "id": tc.id,
                    "agent": args["agent"],
                    "task": args["task"],
                    "reason": args["reason"]
                })
            
            self.current_plan = TaskPlan(
                original_task=task,
                subtasks=subtasks
            )
            logger.info(f"   生成 {len(subtasks)} 个子任务")
            logger.info(f"   子任务详情: {subtasks}")
            return f"计划执行 {len(subtasks)} 个子任务"
        
        return message.content or "无需执行子任务"
    
    async def act(self, plan: str) -> AgentResponse:
        """
        执行计划：调用专业智能体完成子任务
        """
        if not self.current_plan or not self.current_plan.subtasks:
            # 没有子任务，直接返回 LLM 的回复
            if self.messages:
                return AgentResponse(
                    success=True,
                    content=self.messages[-1].content,
                    data=None
                )
            return AgentResponse(success=False, content="", error="没有执行计划")
        
        results = []
        logger.info("\n🤖 [ORCHESTRATOR] 执行子任务...")
        for i, subtask in enumerate(self.current_plan.subtasks, 1):
            agent_type = subtask["agent"]
            task_desc = subtask["task"]
            logger.debug(f"执行子任务 {i}/{len(self.current_plan.subtasks)}: {agent_type} - {task_desc[:50]}...")
            
            if config.system_config.verbose:
                logger.info(f"\n🤖 [{agent_type.upper()}] 执行: {task_desc[:50]}...")
            
            # 获取对应的智能体并执行
            agent = self.agents.get(agent_type)
            if agent:
                try:
                    logger.debug(f"调用智能体 {agent_type}")
                    result = await agent.run(task_desc)
                    logger.debug(f"智能体 {agent_type} 执行完成，结果长度: {len(result.content)}")
                    results.append({
                        "agent": agent_type,
                        "task": task_desc,
                        "success": result.success,
                        "output": result.content
                    })
                    
                    # 添加工具结果消息
                    self.add_message(Message(
                        role="tool",
                        content=f"[{agent_type}] {result.content[:1000]}",
                        tool_call_id=subtask["id"]
                    ))
                    
                except Exception as e:
                    logger.error(f"智能体 {agent_type} 执行失败: {e}", exc_info=True)
                    results.append({
                        "agent": agent_type,
                        "task": task_desc,
                        "success": False,
                        "error": str(e)
                    })
            else:
                logger.warning(f"未找到智能体: {agent_type}")
                results.append({
                    "agent": agent_type,
                    "task": task_desc,
                    "success": False,
                    "error": f"未找到智能体 {agent_type}"
                })
        
        # 汇总结果
        all_success = all(r.get("success", False) for r in results)
        logger.info(f"子任务执行完成，成功率: {sum(1 for r in results if r.get('success'))}/{len(results)}")
        
        output_parts = []
        for r in results:
            status = "✅" if r.get("success") else "❌"
            output_parts.append(f"{status} [{r['agent']}] {r['task']}\n{r.get('output', r.get('error', ''))}")
        
        content = "\n\n---\n\n".join(output_parts)
        logger.info(f"子任务结果汇总:\n{content[:1000]}...")
        return AgentResponse(
            success=all_success,
            content=content,
            data=results
        )
    
    async def observe(self, result: AgentResponse) -> str:
        """
        观察执行结果，生成最终总结
        """
        self._ensure_client()
        
        # 保存结果到记忆
        self.memory.add_short_term(
            f"执行结果: {'成功' if result.success else '失败'}",
            type="result"
        )
        
        # 让 LLM 生成最终总结
        self.add_message(Message(
            role="user",
            content=f"请根据以上执行结果，给用户一个简洁清晰的最终回复。包括：\n1. 完成了什么\n2. 关键结果\n3. 需要注意的事项（如果有）"
        ))
        
        response = await self.client.chat.completions.create(
            model=config.llm_config.model,
            messages=self.get_messages_for_llm(),
            temperature=0.3,
            max_tokens=1000
        )
        
        summary = response.choices[0].message.content
        self.add_message(Message(role="assistant", content=summary))
        
        # 保存到长期记忆
        if self.current_plan:
            self.memory.add_long_term(
                f"任务: {self.current_plan.original_task}\n结果: {summary[:500]}",
                type="observation",
                importance=0.7
            )
        logger.info(f"\n🤖 [ORCHESTRATOR] 观察总结:\n{summary[:1000]}...")
        return summary
    
    async def run(self, task: str) -> AgentResponse:
        """
        运行完整的任务编排流程
        
        Args:
            task: 用户任务描述
            
        Returns:
            AgentResponse: 最终结果
        """
        self.clear_messages()
        self.current_plan = None
        if config.system_config.verbose:
            logger.info(f"\n📋 收到任务: {task}")
            logger.info("=" * 50)
        
        # 迭代执行循环
        for iteration in range(config.system_config.max_iterations):
            if config.system_config.verbose:
                logger.info(f"\n🔄 迭代 {iteration + 1}")
            
            # Think
            plan = await self.think(task)
            if config.system_config.verbose:
                logger.info(f"   思考: {plan}")
            
            # Act
            result = await self.act(plan)
            if config.system_config.verbose:
                logger.info(f"   执行: {'成功' if result.success else '失败'}")
            
            # Observe
            observation = await self.observe(result)
            
            # 检查是否需要继续迭代
            if result.success or not self.current_plan:
                break
            
            # 准备下一轮迭代
            task = f"上一步结果:\n{observation}\n\n请继续完成原始任务或处理遇到的问题。"
        
        if config.system_config.verbose:
            logger.info("\n" + "=" * 50)
            logger.info("✅ 任务完成")
        
        return AgentResponse(
            success=result.success,
            content=observation,
            data=result.data
        )
    
    def get_status(self) -> str:
        """获取编排器状态"""
        status = f"编排器状态:\n"
        status += f"  - 可用智能体: {', '.join(self.agents.keys())}\n"
        status += f"  - {self.memory.summarize()}\n"
        if self.current_plan:
            status += f"  - 当前计划: {len(self.current_plan.subtasks)} 个子任务\n"
        return status
