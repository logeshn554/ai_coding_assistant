from typing import Any, Dict, List
from agent_os.context.interfaces import IContextManager

class VirtualMemoryContextManager(IContextManager):
    """Context Virtual Memory manager implementing Hot, Warm, and Cold pools with LRU paging."""
    def __init__(self, token_budget: int = 2000) -> None:
        self.token_budget = token_budget
        self._hot: Dict[str, str] = {}
        self._warm: Dict[str, str] = {}
        self._cold: Dict[str, str] = {}
        self._lru_order: List[str] = [] # Tracks access order (oldest first)

    def _update_lru(self, key: str) -> None:
        if key in self._lru_order:
            self._lru_order.remove(key)
        self._lru_order.append(key)

    def _find_lru_in(self, keys: List[str]) -> str | None:
        for item in self._lru_order:
            if item in keys:
                return item
        return keys[0] if keys else None

    def _page_out(self) -> None:
        """Paging engine: demotes or evicts context entries until total tokens fit within the budget."""
        while self.estimate_tokens() > self.token_budget:
            # 1. Evict from Cold
            if self._cold:
                lru_cold = self._find_lru_in(list(self._cold.keys()))
                if lru_cold:
                    del self._cold[lru_cold]
                    if lru_cold in self._lru_order:
                        self._lru_order.remove(lru_cold)
                    continue

            # 2. Demote Warm -> Cold
            if self._warm:
                lru_warm = self._find_lru_in(list(self._warm.keys()))
                if lru_warm:
                    self._cold[lru_warm] = self._warm[lru_warm]
                    del self._warm[lru_warm]
                    continue

            # 3. Demote Hot -> Warm
            if self._hot:
                lru_hot = self._find_lru_in(list(self._hot.keys()))
                if lru_hot:
                    self._warm[lru_hot] = self._hot[lru_hot]
                    del self._hot[lru_hot]
                    continue

            break

    def load_context(self, key: str, content: str, level: str) -> None:
        level = level.lower()
        
        # Evict key from other levels
        self._hot.pop(key, None)
        self._warm.pop(key, None)
        self._cold.pop(key, None)

        if level == "hot":
            self._hot[key] = content
        elif level == "warm":
            self._warm[key] = content
        else:
            self._cold[key] = content

        self._update_lru(key)
        self._page_out()

    def promote(self, key: str) -> None:
        if key in self._cold:
            self._warm[key] = self._cold.pop(key)
            self._update_lru(key)
            self._page_out()
        elif key in self._warm:
            self._hot[key] = self._warm.pop(key)
            self._update_lru(key)
            self._page_out()

    def demote(self, key: str) -> None:
        if key in self._hot:
            self._warm[key] = self._hot.pop(key)
            self._update_lru(key)
        elif key in self._warm:
            self._cold[key] = self._warm.pop(key)
            self._update_lru(key)

    def clear(self) -> None:
        self._hot.clear()
        self._warm.clear()
        self._cold.clear()
        self._lru_order.clear()

    def estimate_tokens(self, key: str | None = None) -> int:
        """Estimates token usage using character length conversions (4 chars = 1 token)."""
        if key is not None:
            content = self._hot.get(key) or self._warm.get(key) or self._cold.get(key)
            return len(content) // 4 if content else 0

        # Sum of all stored items
        total_chars = (
            sum(len(v) for v in self._hot.values()) +
            sum(len(v) for v in self._warm.values()) +
            sum(len(v) for v in self._cold.values())
        )
        return total_chars // 4

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
