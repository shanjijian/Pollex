"""
Memory System - 内存管理系统
管理智能体的短期和长期记忆
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime
import json
import os


@dataclass
class MemoryItem:
    """记忆条目"""
    content: str
    timestamp: datetime
    type: str  # "task", "result", "observation", "context"
    metadata: Dict[str, Any] = field(default_factory=dict)
    importance: float = 0.5  # 0-1 重要性评分


class Memory:
    """
    内存管理器
    
    支持：
    - 短期记忆：当前会话的上下文
    - 长期记忆：持久化的重要信息
    - 工作记忆：当前任务的临时数据
    """
    
    def __init__(self, persist_path: Optional[str] = None):
        self.short_term: List[MemoryItem] = []
        self.long_term: List[MemoryItem] = []
        self.working: Dict[str, Any] = {}
        self.persist_path = persist_path
        
        # 配置
        self.short_term_limit = 50  # 短期记忆容量
        self.long_term_limit = 200  # 长期记忆容量
        
        # 加载持久化数据
        if persist_path and os.path.exists(persist_path):
            self._load()
    
    def add_short_term(self, content: str, type: str = "context", **metadata):
        """添加短期记忆"""
        item = MemoryItem(
            content=content,
            timestamp=datetime.now(),
            type=type,
            metadata=metadata
        )
        self.short_term.append(item)
        
        # 超出容量时移除最旧的
        if len(self.short_term) > self.short_term_limit:
            self.short_term.pop(0)
    
    def add_long_term(self, content: str, type: str = "context", importance: float = 0.5, **metadata):
        """添加长期记忆"""
        item = MemoryItem(
            content=content,
            timestamp=datetime.now(),
            type=type,
            importance=importance,
            metadata=metadata
        )
        self.long_term.append(item)
        
        # 超出容量时移除最不重要的
        if len(self.long_term) > self.long_term_limit:
            self.long_term.sort(key=lambda x: x.importance)
            self.long_term.pop(0)
    
    def set_working(self, key: str, value: Any):
        """设置工作记忆"""
        self.working[key] = value
    
    def get_working(self, key: str, default: Any = None) -> Any:
        """获取工作记忆"""
        return self.working.get(key, default)
    
    def clear_working(self):
        """清空工作记忆"""
        self.working = {}
    
    def get_context(self, limit: int = 10) -> str:
        """获取最近的上下文，用于提供给 LLM"""
        recent = self.short_term[-limit:]
        context_parts = []
        for item in recent:
            context_parts.append(f"[{item.type}] {item.content}")
        return "\n".join(context_parts)
    
    def get_relevant(self, query: str, limit: int = 5) -> List[MemoryItem]:
        """
        获取与查询相关的记忆（简单实现：关键词匹配）
        实际应用中可使用向量检索
        """
        query_lower = query.lower()
        scored = []
        
        for item in self.short_term + self.long_term:
            content_lower = item.content.lower()
            # 简单的关键词匹配评分
            score = sum(1 for word in query_lower.split() if word in content_lower)
            if score > 0:
                scored.append((score * item.importance, item))
        
        scored.sort(key=lambda x: -x[0])
        return [item for _, item in scored[:limit]]
    
    def save_todo(self, tasks: List[str], filepath: str = "todo.md"):
        """保存任务列表（Manus 风格的文件记忆）"""
        content = "# TODO\n\n"
        for i, task in enumerate(tasks, 1):
            status = "[ ]" if not task.startswith("[x]") else "[x]"
            task_text = task.replace("[x]", "").strip()
            content += f"- {status} {task_text}\n"
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
    
    def load_todo(self, filepath: str = "todo.md") -> List[Dict[str, Any]]:
        """加载任务列表"""
        if not os.path.exists(filepath):
            return []
        
        tasks = []
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("- ["):
                    done = line.startswith("- [x]")
                    text = line[6:].strip()
                    tasks.append({"text": text, "done": done})
        return tasks
    
    def _save(self):
        """持久化到文件"""
        if not self.persist_path:
            return
        
        data = {
            "long_term": [
                {
                    "content": item.content,
                    "timestamp": item.timestamp.isoformat(),
                    "type": item.type,
                    "metadata": item.metadata,
                    "importance": item.importance
                }
                for item in self.long_term
            ]
        }
        
        os.makedirs(os.path.dirname(self.persist_path), exist_ok=True)
        with open(self.persist_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def _load(self):
        """从文件加载"""
        if not self.persist_path or not os.path.exists(self.persist_path):
            return
        
        with open(self.persist_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        for item_data in data.get("long_term", []):
            self.long_term.append(MemoryItem(
                content=item_data["content"],
                timestamp=datetime.fromisoformat(item_data["timestamp"]),
                type=item_data["type"],
                metadata=item_data.get("metadata", {}),
                importance=item_data.get("importance", 0.5)
            ))
    
    def summarize(self) -> str:
        """获取记忆摘要"""
        return f"记忆状态: 短期={len(self.short_term)}, 长期={len(self.long_term)}, 工作={len(self.working)}"
