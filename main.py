"""
Multi-Agent System - Main Entry Point
多智能体系统主入口
"""
import asyncio

from config.config import init_config, system_config
from core.orchestrator import Orchestrator
from utils.log import get_logger

logger = get_logger("main")


def print_banner():
    """打印欢迎横幅"""
    banner = """
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
"""
    print(banner)


def print_help():
    """打印帮助信息"""
    help_text = """
📖 使用帮助:

1. 直接输入任务描述，系统会自动分析并分配给合适的智能体

2. 示例任务:
   • "帮我写一个计算斐波那契数列的函数"
   • "搜索 Python 最新版本是什么"
   • "读取当前目录的文件列表"
   • "分析这组数据的统计特征: [1,2,3,4,5,6,7,8,9,10]"
   • "帮我创建一个简单的 TODO 应用的代码"

3. 命令:
   • status - 显示系统状态
   • clear  - 清空历史记录
   • help   - 显示此帮助
   • quit   - 退出系统
"""
    print(help_text)


async def main():
    """主函数"""
    logger.info("🚀 系统启动中...")
    print_banner()
    
    # 初始化配置
    logger.debug("初始化系统配置...")
    init_config()
    logger.info("✅ 配置加载成功")
    
    # 创建编排器
    logger.debug("创建编排器实例...")
    orchestrator = Orchestrator()
    logger.info("✅ 编排器初始化完成")
    
    print("🚀 系统已就绪，请输入您的任务:\n")
    logger.info("系统已就绪，等待用户输入")
    
    while True:
        try:
            # 获取用户输入
            user_input = input("👤 You: ").strip()
            logger.debug(f"收到用户输入: {user_input[:50]}...")
            
            if not user_input:
                logger.debug("用户输入为空，跳过")
                continue
            
            # 处理命令
            if user_input.lower() in ["quit", "exit", "q"]:
                logger.info("用户请求退出系统")
                print("\n👋 再见！")
                break
            
            if user_input.lower() == "help":
                logger.debug("显示帮助信息")
                print_help()
                continue
            
            if user_input.lower() == "status":
                status = orchestrator.get_status()
                logger.debug(f"显示系统状态: {status}")
                print(f"\n{status}")
                continue
            
            if user_input.lower() == "clear":
                logger.info("清空历史记录")
                orchestrator.memory.short_term.clear()
                orchestrator.clear_messages()
                print("✅ 历史记录已清空\n")
                continue
            
            # 执行任务
            logger.info(f"开始执行任务: {user_input}")
            print()  # 空行
            result = await orchestrator.run(user_input)
            
            # 显示结果
            logger.info("任务执行完成")
            print(f"\n🤖 Assistant:\n{result.content}\n")
            
        except KeyboardInterrupt:
            logger.info("收到键盘中断信号，退出系统")
            print("\n\n👋 再见！")
            break
        except Exception as e:
            logger.error(f"主循环中发生错误: {e}", exc_info=True)
            print(f"\n❌ 错误: {e}\n")
            if system_config.verbose:
                import traceback
                traceback.print_exc()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        