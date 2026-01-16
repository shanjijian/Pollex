# Pollex

**Pollex** 是一个多智能体系统（Multi-Agent System）学习实践项目，目标是实现类似 **Manus** 的 Agent 架构。项目将从基础的单 Agent 架构出发，逐步演进为具备协作、编排与自治能力的完整多智能体系统。项目名称 **Pollex** 源自拉丁语“拇指”，呼应 **Manus**（手）的释义。

多智能体系统的发展可以分为几个关键阶段，每个阶段在架构和功能上都有不同的进步：

1. **单一智能体系统（初期）（对应 V1.0 版本）**
    
    在这个阶段，系统主要聚焦于单个智能体的独立执行任务。系统的核心是单一的智能体，它负责完成用户指定的任务，不具备协调和协作的能力。
    
2. **多智能体系统（中期）**
    
    随着需求的增多，系统逐步发展为多智能体架构。多个智能体分别负责不同的任务或功能，但这些智能体之间缺乏紧密的协作和编排，往往是相互独立工作。
    
3. **协作与编排（进阶）**
    
    随着技术的发展，多个智能体不仅能独立工作，还能进行协作。系统引入了编排机制，能够根据任务需求动态地分配和调度智能体的执行。这时，智能体之间开始协调工作，增强了系统的灵活性和复杂性。
    
4. **自治与自组织（高级）**
    
    在这个阶段，智能体不仅可以进行协作，还能够自我组织和自主决策。智能体能够根据环境和任务的变化，自主调整策略和行为，整个系统具有一定的自适应能力。
    

## V1.0

### 核心实现

V1.0 采用 **中心化单 Orchestrator 的 Plan-and-Execute 架构**，作为多智能体系统的最小可用原型（MVP），验证了以下能力：

- LLM 驱动的任务拆解（Planning）
- 多 Agent 的工具化调用（Execution）
- 基于执行结果的循环迭代（Observe → Replan）
- 统一 Memory 与上下文管理

```
Orchestrator (编排器)
    ├── CodeAgent (代码智能体)
    ├── BrowserAgent (浏览器智能体)
    ├── FileAgent (文件智能体)
    └── DataAgent (数据智能体)

```

目录结构为：

```
pollex/
├── pollex/                 # 源码包
│   ├── config.py           # 配置管理
│   ├── main.py             # 主逻辑
│   ├── core/               # 核心组件
│   │   ├── agent.py        # 智能体基类
│   │   ├── memory.py       # 内存系统
│   │   └── orchestrator.py # 编排器
│   ├── agents/             # 专业智能体
│   │   ├── code.py
│   │   ├── browser.py
│   │   ├── file.py
│   │   └── data.py
│   └── tools/              # 工具库
│       ├── base.py
│       ├── code.py
│       ├── browser.py
│       └── file.py
├── run.py                  # 启动脚本
├── requirements.txt
└── README.md

```

但该架构在设计上仍存在明显的阶段性问题，比如：

1. **Orchestrator 过度中心化（Single Point of Control）：**所有 **计划生成、任务拆解、调度、失败重试、结果汇总** 均由 Orchestrator 负责；
2. **Agent 缺乏自治能力：**各 Agent 仅作为 被调用的执行单元，Agent 不具备自主决策能能力；
3. **Memory 为全局共享：**缺乏如Orchestrator 记忆、横向记忆、纵向记忆的区分。

### 快速开始

1. 安装依赖
    
    推荐使用conda进行环境管理。
    
    ```bash
    conda create --name pollex python=3.12
    source activate pollex
    pip install -r requirements.txt
    
    ```
    
2. 自定义API
    
    修改`config/config.py`中`model`、`base_url`及`api_key`。
    
    > 默认使用硅基流动 API (DeepSeek-V3)。设置 `OPENAI_API_KEY` 环境变量可设置密钥。
    > 
    
    ```jsx
    export OPENAI_API_KEY="sk-你的密钥"
    ```
    
3. 运行系统
    
    ```bash
    python run.py
    ```
    

### 核心功能代码

任务由`Orchestrator` 核心驱动。

```python
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
```

收到任务后首先开始对迭代次数进行记录，然后开始正式的思考循环：

1. 通过Think模块进行规划，确认任务执行的步骤，核心代码为：
    
    ```python
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
    ```
    
    如输出：
    
    ```json
    [
      {
        "id": "019ba20b3975853d09a9c69f574dee6e",
        "agent": "browser",
        "task": "访问zbss.site并获取页面标题",
        "reason": "需要通过网络浏览器访问目标网站并提取页面标题信息"
      }
    ]
    ```
    
    判断需要使用browser模块Agent，并将相关内容添加到记忆中。
    
2. Act模块收到Think模块发送的任务后会调用对应的Agent完成相应任务。核心代码为：
    
    ```python
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
    ```
    
3. 接下来Observe模块会收到Act模块的执行结果，生成本次任务的总结内容，保存到记忆中。核心代码为：
    
    ```python
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
    ```
    

此时单次循环结束，但如果子任务有执行失败的情况，即成功率不是100%的话，会将本次的Observe模块结果返回给Think模块，Think模块会重新规划直到其计划的任务全部完成。

执行示例如下：

```python
🚀 系统启动中...

╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║     🤖 POLLEX - Multi-Agent System                            ║
║     类 Manus 多智能体系统原型                                    ║
║                                                               ║
║     可用智能体:                                                 ║
║       • 代码智能体 (code)  - Python 代码生成和执行                ║
║       • 浏览器智能体 (browser) - 网页搜索和内容获取                ║
║       • 文件智能体 (file)  - 文件读写和目录管理                    ║
║       • 数据智能体 (data)  - 数据分析和可视化                     ║
║                                                               ║
║     输入 'quit' 或 'exit' 退出                                 ║
║     输入 'status' 查看系统状态                                  ║
║     输入 'help' 获取帮助                                        ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝

✅ 配置加载成功
✅ 编排器初始化完成
🚀 系统已就绪，请输入您的任务:

系统已就绪，等待用户输入
👤 You: 访问zbss.site然后告诉我页面标题是什么？
开始执行任务: 访问zbss.site然后告诉我页面标题是什么？

📋 收到任务: 访问zbss.site然后告诉我页面标题是什么？
==================================================

🔄 迭代 1

🤖 [ORCHESTRATOR] 思考中...
   生成 1 个子任务
   子任务详情: [{'id': '019ba22f062ed68f768c77890590c79a', 'agent': 'browser', 'task': '访问zbss.site并获取页面标题', 'reason': '需要通过网络浏览器访问网页并提取标题信息'}]
   思考: 计划执行 1 个子任务

🤖 [ORCHESTRATOR] 执行子任务...

🤖 [BROWSER] 执行: 访问zbss.site并获取页面标题...
子任务执行完成，成功率: 1/1
子任务结果汇总:
✅ [browser] 访问zbss.site并获取页面标题
在北山上 On the Northern Mountain 在北山上 On the Northern Mountain 明日之花，绽放遍野。欢迎到访，在北山上。 The flowers of tomorrow will bloom across the fields. Welcome to visit, on the Northern Mountain. 我是山己见，欢迎来到我的个人主页。这是我的赛博生命体，我为它买下了10年的域名。更值得一看的，是我的博客文章。我的博客有两个地址，内容完全相同。 I am Shan Ji Jian, welcome to my personal homepage. This is my cyber life form, and I have purchased a 10-year domain for it. What’s more worth checking out are my blog articles. I have two blog addresses with identical content. 我非常喜欢Notion，第一个博客站点就是用Notion的页面公开功能创建；第二个站点则是用WordPress建站，同时使用Notion作为数据源。以下是地址。 I really enjoy Notion. The first blog site is created using Notion's page sharing feature; the second site is built on WordPress, using Notion as the data source. Here are the links. WordPress：https://blo.zbss.site/ Notion：https://blog.zbss.site/ 作为网络安全从业者，我还部署了一些公共服务站，还有我写的一些小玩意，供大家和我一起使用。 As a cybersecurity practitioner, I have also set up some public service stations, along with some small tools I dev...
   执行: 成功

🤖 [ORCHESTRATOR] 观察总结:
已完成任务：访问zbss.site并获取页面标题

关键结果：
- 页面标题是："在北山上 On the Northern Mountain"
- 该网站是山己见的个人主页，包含博客和公共服务站链接
- 博客有两个地址（WordPress和Notion版本）

注意事项：
1. 标题包含中英双语内容
2. 网站提供了两个博客入口，内容完全相同
3. 页面还包含一些网络安全相关的公共服务信息...

==================================================
✅ 任务完成
任务执行完成

🤖 Assistant:
已完成任务：访问zbss.site并获取页面标题

关键结果：
- 页面标题是："在北山上 On the Northern Mountain"
- 该网站是山己见的个人主页，包含博客和公共服务站链接
- 博客有两个地址（WordPress和Notion版本）

注意事项：
1. 标题包含中英双语内容
2. 网站提供了两个博客入口，内容完全相同
3. 页面还包含一些网络安全相关的公共服务信息

👤 You: 
```

## License

MIT