from typing import Any, Dict, List
from collections import OrderedDict
from .interfaces import IContextManager

class VirtualMemoryContextManager(IContextManager):
    """Context Virtual Memory manager implementing Hot, Warm, and Cold pools with LRU paging."""
    def __init__(self, token_budget: int = 2000) -> None:
        self.token_budget = token_budget
        self._hot: OrderedDict[str, str] = OrderedDict()
        self._warm: OrderedDict[str, str] = OrderedDict()
        self._cold: OrderedDict[str, str] = OrderedDict()
        self._total_chars: int = 0

    def _page_out(self) -> None:
        """Paging engine: demotes or evicts context entries until total tokens fit within the budget."""
        while self.estimate_tokens() > self.token_budget:
            # 1. Evict from Cold
            if self._cold:
                k, v = self._cold.popitem(last=False)
                self._total_chars -= len(v)
                continue

            # 2. Demote Warm -> Cold
            if self._warm:
                k, v = self._warm.popitem(last=False)
                self._cold[k] = v
                continue

            # 3. Demote Hot -> Warm
            if self._hot:
                k, v = self._hot.popitem(last=False)
                self._warm[k] = v
                continue

            break

    def load_context(self, key: str, content: str, level: str) -> None:
        level = level.lower()
        
        # Evict key from other levels
        for pool in (self._hot, self._warm, self._cold):
            if key in pool:
                v = pool.pop(key)
                self._total_chars -= len(v)

        if level == "hot":
            self._hot[key] = content
        elif level == "warm":
            self._warm[key] = content
        else:
            self._cold[key] = content

        self._total_chars += len(content)
        self._page_out()

    def promote(self, key: str) -> None:
        if key in self._cold:
            v = self._cold.pop(key)
            self._warm[key] = v
            self._page_out()
        elif key in self._warm:
            v = self._warm.pop(key)
            self._hot[key] = v
            self._page_out()
        elif key in self._hot:
            self._hot.move_to_end(key)

    def demote(self, key: str) -> None:
        if key in self._hot:
            v = self._hot.pop(key)
            self._warm[key] = v
        elif key in self._warm:
            v = self._warm.pop(key)
            self._cold[key] = v

    def clear(self) -> None:
        self._hot.clear()
        self._warm.clear()
        self._cold.clear()
        self._total_chars = 0

    def estimate_tokens(self, key: str | None = None) -> int:
        """Estimates token usage using character length conversions (4 chars = 1 token)."""
        if key is not None:
            content = self._hot.get(key) or self._warm.get(key) or self._cold.get(key)
            return len(content) // 4 if content else 0
        return self._total_chars // 4

    def add_to_context(self, name: str, data: Any) -> None:
        self.load_context(name, str(data), "hot")

    def get_prompt_payload(self) -> str:
        payloads = []
        if self._hot:
            payloads.append("[HOT CONTEXT]")
            for k, v in self._hot.items():
                payloads.append(f"{k}: {v}")
                
        if self._warm:
            payloads.append("\n[WARM CONTEXT]")
            for k, v in self._warm.items():
                payloads.append(f"{k}: {v}")
                
        if self._cold:
            payloads.append("\n[COLD CONTEXT]")
            for k, v in self._cold.items():
                payloads.append(f"{k}: {v}")
                
        return "\n".join(payloads)

