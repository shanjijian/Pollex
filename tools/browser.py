"""
Browser Tools - 网页浏览工具
"""
import aiohttp
from typing import Any, Dict
from .base import BaseTool, ToolResult
from utils.log import get_logger

logger = get_logger("tool")


class WebSearchTool(BaseTool):
    """网页搜索工具（使用 DuckDuckGo）"""

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return "在互联网上搜索信息。返回搜索结果的标题、链接和摘要。"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词"
                },
                "max_results": {
                    "type": "integer",
                    "description": "最大结果数量，默认为5",
                    "default": 5
                }
            },
            "required": ["query"]
        }

    async def execute(self, query: str, max_results: int = 5) -> ToolResult:
        """
        执行网页搜索

        Args:
            query: 搜索关键词
            max_results: 最大结果数量

        Returns:
            ToolResult: 搜索结果
        """
        try:
            # 使用 DuckDuckGo HTML 搜索（无需 API key）
            url = "https://html.duckduckgo.com/html/"
            params = {"q": query}

            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=params) as response:
                    if response.status != 200:
                        return ToolResult(
                            success=False,
                            output=None,
                            error=f"搜索请求失败: HTTP {response.status}"
                        )

                    html = await response.text()

            # 简单解析搜索结果
            results = self._parse_results(html, max_results)

            if not results:
                return ToolResult(
                    success=True,
                    output="未找到相关结果"
                )

            # 格式化输出
            output = f"搜索 '{query}' 的结果:\n\n"
            for i, result in enumerate(results, 1):
                output += f"{i}. {result['title']}\n"
                output += f"   链接: {result['url']}\n"
                output += f"   摘要: {result['snippet']}\n\n"

            return ToolResult(success=True, output=output)

        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))

    def _parse_results(self, html: str, max_results: int) -> list:
        """解析 DuckDuckGo 搜索结果 HTML"""
        results = []

        # 简单的正则解析（生产环境应使用 BeautifulSoup）
        import re

        # 查找结果块
        result_pattern = r'<a rel="nofollow" class="result__a" href="([^"]+)"[^>]*>([^<]+)</a>.*?<a class="result__snippet"[^>]*>([^<]+)</a>'
        matches = re.findall(result_pattern, html, re.DOTALL)

        for url, title, snippet in matches[:max_results]:
            results.append({
                "title": title.strip(),
                "url": url.strip(),
                "snippet": snippet.strip()
            })

        return results


class FetchURLTool(BaseTool):
    """获取网页内容工具"""

    @property
    def name(self) -> str:
        return "fetch_url"

    @property
    def description(self) -> str:
        return "获取指定 URL 的网页内容。返回网页的文本内容。"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "要获取的网页 URL"
                },
                "max_length": {
                    "type": "integer",
                    "description": "返回内容的最大字符数，默认为5000",
                    "default": 5000
                }
            },
            "required": ["url"]
        }

    async def execute(self, url: str, max_length: int = 5000) -> ToolResult:
        """
        获取网页内容

        Args:
            url: 网页 URL
            max_length: 最大返回字符数

        Returns:
            ToolResult: 网页内容
        """
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=30) as response:
                    if response.status != 200:
                        return ToolResult(
                            success=False,
                            output=None,
                            error=f"获取网页失败: HTTP {response.status}"
                        )

                    html = await response.text()

            # 提取文本内容
            text = self._extract_text(html)

            if len(text) > max_length:
                text = text[:max_length] + "...(内容已截断)"

            return ToolResult(success=True, output=text)

        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e))

    def _extract_text(self, html: str) -> str:
        """从 HTML 中提取纯文本"""
        import re

        # 移除 script 和 style
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)

        # 移除 HTML 标签
        text = re.sub(r'<[^>]+>', ' ', text)

        # 处理 HTML 实体
        text = text.replace('&nbsp;', ' ')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        text = text.replace('&amp;', '&')

        # 清理空白
        text = re.sub(r'\s+', ' ', text)

        return text.strip()
