import json
import logging
import os
import time

import requests

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self, config: dict):
        api_key = config.get("api_key", "")
        if api_key.startswith("${"):
            env_key = api_key.strip("${}").strip()
            api_key = os.environ.get(env_key, "")
        self.api_key = os.environ.get("DEEPSEEK_API_KEY", api_key)

        self.base_url = config.get("base_url", "https://api.deepseek.com/v1")
        self.model = config.get("model", "deepseek-chat")
        self.temperature = config.get("temperature", 0.7)
        self.max_tokens = config.get("max_tokens", 800)

        try:
            from openai import OpenAI
            import httpx
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                http_client=httpx.Client(proxy=None, verify=True),
            )
            self._use_openai = True
        except ImportError:
            self._client = None
            self._use_openai = False

    def generate(self, system_prompt: str, user_prompt: str, max_tokens: int = 0) -> str:
        effective_max = max_tokens if max_tokens > 0 else self.max_tokens
        if self._use_openai and self._client:
            return self._generate_openai(system_prompt, user_prompt, effective_max)
        return self._generate_http(system_prompt, user_prompt, effective_max)

    def _generate_openai(self, system_prompt: str, user_prompt: str, max_tokens: int) -> str:
        for attempt in range(3):
            try:
                response = self._client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=self.temperature,
                    max_tokens=max_tokens,
                )
                content = response.choices[0].message.content
                logger.info(f"LLM: tokens={response.usage.total_tokens}")
                return content.strip() if content else ""
            except Exception as e:
                logger.warning(f"LLM attempt {attempt + 1} failed: {e}")
                if attempt < 2:
                    time.sleep(2 ** attempt)
        raise RuntimeError("LLM call failed after 3 retries")

    def _generate_http(self, system_prompt: str, user_prompt: str, max_tokens: int) -> str:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.temperature,
            "max_tokens": max_tokens,
        }

        for attempt in range(3):
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=60,
                                     proxies={"http": None, "https": None})
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})
                logger.info(
                    f"LLM: tokens={usage.get('total_tokens', '?')}"
                )
                return content.strip() if content else ""
            except Exception as e:
                logger.warning(f"LLM attempt {attempt + 1} failed: {e}")
                if attempt < 2:
                    time.sleep(2 ** attempt)
        raise RuntimeError("LLM call failed after 3 retries")
