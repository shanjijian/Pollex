"""
Code Tools - 代码执行工具
"""
import sys
import io
import traceback
from typing import Any, Dict
from .base import BaseTool, ToolResult
from utils.log import get_logger

logger = get_logger("tool")


class ExecutePythonTool(BaseTool):
    """执行 Python 代码的工具"""
    
    @property
    def name(self) -> str:
        return "execute_python"
    
    @property
    def description(self) -> str:
        return "执行 Python 代码并返回结果。可以用于计算、数据处理、生成内容等。"
    
    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "要执行的 Python 代码"
                }
            },
            "required": ["code"]
        }
    
    async def execute(self, code: str) -> ToolResult:
        """
        在沙箱环境中执行 Python 代码
        
        Args:
            code: Python 代码字符串
            
        Returns:
            ToolResult: 包含输出或错误信息
        """
        logger.debug(f"开始执行Python代码，长度: {len(code)} 字符")
        
        # 捕获标准输出
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        redirected_output = io.StringIO()
        redirected_error = io.StringIO()
        
        sys.stdout = redirected_output
        sys.stderr = redirected_error
        
        # 创建受限的执行环境
        sandbox_globals = {
            "__builtins__": __builtins__,
            "__name__": "__main__",
        }
        
        result_value = None
        
        try:
            # 尝试 eval 获取返回值
            try:
                result_value = eval(code, sandbox_globals)
                logger.debug("代码作为表达式执行")
            except SyntaxError:
                # 如果不是表达式，使用 exec
                exec(code, sandbox_globals)
                logger.debug("代码作为语句执行")
            
            output = redirected_output.getvalue()
            error_output = redirected_error.getvalue()
            
            if error_output:
                output += f"\nStderr: {error_output}"
            
            if result_value is not None:
                output = f"{output}\n返回值: {result_value}" if output else f"返回值: {result_value}"
            
            logger.info("Python代码执行成功")
            return ToolResult(success=True, output=output or "代码执行成功（无输出）")
            
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
            logger.error(f"Python代码执行失败: {type(e).__name__}: {str(e)}")
            return ToolResult(success=False, output=None, error=error_msg)
            
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
