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
            try:
                content = self._generate_openai(system_prompt, user_prompt, effective_max)
                if content:
                    return content
            except Exception:
                pass
            logger.warning("OpenAI failed or returned empty, falling back to HTTP")
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


class DoubaoClient:
    """豆包 Responses API 客户端 — 支持联网搜索 (web_search tool)。
    
    与 LLMClient(DeepSeek) 不同，DoubaoClient 使用 /responses 端点，
    通过 tools: [{"type": "web_search"}] 开启联网搜索。
    """

    def __init__(self, config: dict):
        self.api_key = config.get("api_key", "")
        self.base_url = config.get("base_url", "https://ark.cn-beijing.volces.com/api/v3")
        self.model = config.get("model", "doubao-seed-2-0-pro-260215")
        self.temperature = config.get("temperature", 0.7)
        self.max_tokens = config.get("max_tokens", 4096)

    def search(self, prompt: str, max_tokens: int = 0,
               enable_web_search: bool = True) -> dict:
        """调用 Responses API，返回 {content, annotations, article_urls}。
        
        Returns:
            dict with keys:
                - content: 模型生成的文本
                - annotations: 搜索引用的 annotations 列表
                - article_urls: 提取的文章 URL 列表 (去重)
                - input_tokens / output_tokens: token 用量
        """
        effective_max = max_tokens if max_tokens > 0 else self.max_tokens
        payload = {
            "model": self.model,
            "input": [{"role": "user", "content": [{"type": "input_text", "text": prompt}]}],
            "temperature": self.temperature,
            "max_output_tokens": effective_max,
        }
        if enable_web_search:
            payload["tools"] = [{"type": "web_search"}]

        for attempt in range(3):
            try:
                resp = requests.post(
                    f"{self.base_url}/responses",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=120,
                    proxies={"http": None, "https": None},
                )
                resp.raise_for_status()
                data = resp.json()

                content_text = ""
                annotations = []
                article_urls = []

                for item in data.get("output", []):
                    if item.get("type") == "message":
                        for part in item.get("content", []):
                            if part.get("type") == "output_text":
                                content_text += part.get("text", "")
                            for ann in part.get("annotations", []):
                                annotations.append(ann)
                                if ann.get("type") == "url_citation" and ann.get("url"):
                                    article_urls.append(ann["url"])

                usage = data.get("usage", {})
                logger.info(
                    f"Doubao: tokens in={usage.get('input_tokens',0)} "
                    f"out={usage.get('output_tokens',0)} "
                    f"urls={len(article_urls)}"
                )
                return {
                    "content": content_text.strip(),
                    "annotations": annotations,
                    "article_urls": list(dict.fromkeys(article_urls)),
                    "input_tokens": usage.get("input_tokens", 0),
                    "output_tokens": usage.get("output_tokens", 0),
                }
            except Exception as e:
                logger.warning(f"Doubao search attempt {attempt + 1} failed: {e}")
                if attempt < 2:
                    time.sleep(2 ** attempt)

        raise RuntimeError("Doubao search failed after 3 retries")
