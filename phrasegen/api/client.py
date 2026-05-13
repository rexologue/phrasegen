"""OpenAI-compatible chat completions client."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from phrasegen.config.entities import ApiConfig, SamplingConfig


@dataclass
class ChatMessage:
    """One chat message sent to the API."""

    role: str
    content: str

    def to_json(self) -> dict[str, str]:
        """Return the OpenAI-compatible JSON representation."""
        return {"role": self.role, "content": self.content}


class OpenAICompatibleClient:
    """Small stdlib HTTP client for OpenAI-compatible chat completions APIs."""

    def __init__(self, config: ApiConfig) -> None:
        """Store API config and resolve the API key."""
        self.config = config
        self.api_key = self._resolve_api_key(config)

    def complete(self, messages: list[ChatMessage], sampling: SamplingConfig) -> str:
        """Call the chat completions endpoint and return assistant text."""
        payload = self._build_payload(messages, sampling)
        last_error: Exception | None = None
        for attempt in range(0, self.config.max_retries + 1):
            try:
                response = self._post_json(payload)
                return self._extract_text(response)
            except Exception as exc:
                last_error = exc
                if attempt >= self.config.max_retries:
                    break
                time.sleep(self.config.retry_sleep_sec * (attempt + 1))
        raise RuntimeError(f"API request failed after retries: {last_error}") from last_error

    def _build_payload(self, messages: list[ChatMessage], sampling: SamplingConfig) -> dict[str, Any]:
        """Build the JSON request body."""
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": [message.to_json() for message in messages],
            "temperature": sampling.temperature,
            "top_p": sampling.top_p,
            "max_tokens": sampling.max_tokens,
        }
        if sampling.presence_penalty is not None:
            payload["presence_penalty"] = sampling.presence_penalty
        if sampling.frequency_penalty is not None:
            payload["frequency_penalty"] = sampling.frequency_penalty
        if sampling.stop:
            payload["stop"] = sampling.stop
        payload.update(sampling.extra_body)
        return payload

    def _post_json(self, payload: dict[str, Any]) -> dict[str, Any]:
        """POST JSON to the configured endpoint and return decoded JSON."""
        request = urllib.request.Request(
            self._url(),
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_sec) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {exc.code}: {error_body}") from exc
        return json.loads(body)

    def _extract_text(self, response: dict[str, Any]) -> str:
        """Extract assistant content from an OpenAI-compatible response."""
        choices = response.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ValueError("API response does not contain choices")
        first = choices[0]
        if isinstance(first, dict):
            message = first.get("message")
            if isinstance(message, dict) and isinstance(message.get("content"), str):
                return message["content"]
            if isinstance(first.get("text"), str):
                return first["text"]
        raise ValueError("API response does not contain assistant text")

    def _headers(self) -> dict[str, str]:
        """Build HTTP headers for the API request."""
        headers = {
            "Content-Type": "application/json",
            **self.config.headers,
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _url(self) -> str:
        """Return the full endpoint URL."""
        return f"{self.config.base_url.rstrip('/')}/{self.config.endpoint.lstrip('/')}"

    def _resolve_api_key(self, config: ApiConfig) -> str | None:
        """Resolve an API key from inline config or environment."""
        if config.api_key:
            return config.api_key
        if config.api_key_env:
            return os.environ.get(config.api_key_env)
        return None
