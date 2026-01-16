"""
Multi-Agent System Configuration
多智能体系统配置
"""
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class LLMConfig:
    """LLM 配置"""
    api_key: Optional[str] = None
    model: str = "Pro/deepseek-ai/DeepSeek-V3"
    base_url: str = "https://api.siliconflow.cn/v1"
    temperature: float = 0.7
    max_tokens: int = 4096

    @classmethod
    def from_env(cls) -> "LLMConfig":
        """从环境变量创建配置"""
        api_key = os.getenv("OPENAI_API_KEY")
        return cls(api_key=api_key)


@dataclass
class SystemConfig:
    """系统配置"""
    max_iterations: int = 10  # 最大迭代次数
    verbose: bool = True      # 是否显示详细日志
    sandbox_enabled: bool = True  # 是否启用沙箱执行
    work_dir: str = "./workspace"  # 工作目录


# 全局配置实例
llm_config: Optional[LLMConfig] = None
system_config = SystemConfig()


def init_config():
    """初始化配置"""
    global llm_config
    llm_config = LLMConfig.from_env()
    # 提供更友好的错误提示，早期捕获未设置 API key 的问题
    if not llm_config or not llm_config.api_key:
        raise EnvironmentError(
            "未配置 LLM API key。请设置环境变量 OPENAI_API_KEY 来提供密钥。"
        )
    os.makedirs(system_config.work_dir, exist_ok=True)
    return llm_config, system_config
