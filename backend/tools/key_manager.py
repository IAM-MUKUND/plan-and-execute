import os
import logging
from typing import List, Callable, Any
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("key_manager")

class KeyManager:
    """
    Manages API keys for Groq and Tavily services with automatic key rotation
    when rate limit (429) or quota errors are encountered.
    """
    def __init__(self):
        self.groq_keys: List[str] = self._load_keys("GROQ_API_KEY")
        self.tavily_keys: List[str] = self._load_keys("TAVILY_API_KEY")
        
        self.groq_index: int = 0
        self.tavily_index: int = 0

    def _load_keys(self, prefix: str) -> List[str]:
        keys = []
        # Check standard exact key first if set
        primary = os.getenv(prefix)
        if primary:
            keys.append(primary)
        
        # Look for numbered indexed keys e.g. GROQ_API_KEY1, GROQ_API_KEY2, etc.
        i = 1
        while True:
            k = os.getenv(f"{prefix}{i}")
            if not k:
                break
            if k not in keys:
                keys.append(k)
            i += 1
            
        if not keys:
            logger.warning(f"No API keys found for prefix: {prefix}")
        return keys

    def get_current_groq_key(self) -> str:
        if not self.groq_keys:
            raise ValueError("No Groq API keys configured in environment.")
        return self.groq_keys[self.groq_index]

    def cycle_groq_key(self) -> str:
        if len(self.groq_keys) <= 1:
            logger.warning("Only 1 Groq API key available; key rotation not possible.")
            return self.get_current_groq_key()
        
        old_idx = self.groq_index
        self.groq_index = (self.groq_index + 1) % len(self.groq_keys)
        logger.info(f"Cycled Groq API key from index {old_idx} -> {self.groq_index}")
        return self.groq_keys[self.groq_index]

    def get_current_tavily_key(self) -> str:
        if not self.tavily_keys:
            raise ValueError("No Tavily API keys configured in environment.")
        return self.tavily_keys[self.tavily_index]

    def cycle_tavily_key(self) -> str:
        if len(self.tavily_keys) <= 1:
            logger.warning("Only 1 Tavily API key available; key rotation not possible.")
            return self.get_current_tavily_key()
        
        old_idx = self.tavily_index
        self.tavily_index = (self.tavily_index + 1) % len(self.tavily_keys)
        logger.info(f"Cycled Tavily API key from index {old_idx} -> {self.tavily_index}")
        return self.tavily_keys[self.tavily_index]

    def execute_groq(self, call_factory: Callable[[str], Any], max_retries: int = None) -> Any:
        """
        Executes a Groq call using `call_factory(api_key)`.
        If rate-limited (HTTP 429 / RateLimitError), automatically cycles to the next key and retries.
        """
        if max_retries is None:
            max_retries = max(len(self.groq_keys), 1) * 2

        attempts = 0
        last_error = None

        while attempts < max_retries:
            api_key = self.get_current_groq_key()
            try:
                return call_factory(api_key)
            except Exception as e:
                err_str = str(e).lower()
                is_rate_limit = "429" in err_str or "rate limit" in err_str or "quota" in err_str or "ratelimit" in type(e).__name__.lower()
                if is_rate_limit:
                    logger.debug(f"Groq API key at index {self.groq_index} hit rate limit. Cycling to next key...")
                    self.cycle_groq_key()
                    attempts += 1
                    last_error = e
                else:
                    raise e
        raise RuntimeError(f"All Groq API keys exhausted after {attempts} attempts. Last error: {last_error}")

    def execute_tavily(self, call_factory: Callable[[str], Any], max_retries: int = None) -> Any:
        """
        Executes a Tavily call using `call_factory(api_key)`.
        If rate-limited (HTTP 429 / quota error), automatically cycles to the next key and retries.
        """
        if max_retries is None:
            max_retries = max(len(self.tavily_keys), 1) * 2

        attempts = 0
        last_error = None

        while attempts < max_retries:
            api_key = self.get_current_tavily_key()
            try:
                return call_factory(api_key)
            except Exception as e:
                err_str = str(e).lower()
                is_rate_limit = "429" in err_str or "rate limit" in err_str or "quota" in err_str or "limit exceeded" in err_str
                if is_rate_limit:
                    logger.debug(f"Tavily API key at index {self.tavily_index} hit rate limit. Cycling to next key...")
                    self.cycle_tavily_key()
                    attempts += 1
                    last_error = e
                else:
                    raise e
        raise RuntimeError(f"All Tavily API keys exhausted after {attempts} attempts. Last error: {last_error}")

# Global singleton instance
key_manager = KeyManager()
