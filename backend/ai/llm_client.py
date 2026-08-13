from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from backend.errors import LLMError


MAX_RESPONSE_BYTES = 2 * 1024 * 1024


def validate_base_url(value: str) -> str:
    parsed = urlparse(value.strip())
    if parsed.scheme != "https" or not parsed.hostname:
        raise LLMError("Base URL 必须是公开可访问的 HTTPS 地址。")
    host = parsed.hostname.casefold()
    if host in {"localhost", "127.0.0.1", "::1"}:
        raise LLMError("Base URL 不能指向本机或局域网地址。")
    try:
        addresses = socket.getaddrinfo(host, parsed.port or 443, type=socket.SOCK_STREAM)
        for address in addresses:
            ip = ipaddress.ip_address(address[4][0])
            if not ip.is_global:
                raise LLMError("Base URL 不能解析到本机或私有网络。")
    except socket.gaierror as exc:
        raise LLMError("Base URL 域名无法解析。请检查地址。") from exc
    return value.rstrip("/")


@dataclass(frozen=True)
class ClientSettings:
    provider: str
    model: str
    base_url: str
    api_key: str
    timeout_seconds: float = 90


class OpenAICompatibleClient:
    def __init__(self, settings: ClientSettings):
        if not settings.api_key.strip():
            raise LLMError("API Key 不可用。请先保存配置。")
        if not settings.model.strip():
            raise LLMError("模型名称不能为空。")
        self.settings = settings
        self.base_url = validate_base_url(settings.base_url)

    async def complete_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema_name: str,
        temperature: float = 0.2,
    ) -> str:
        max_tokens = 4000 if schema_name.startswith(("resume_structure", "jd_analysis")) else 2400
        if schema_name.startswith("resume_advice"):
            max_tokens = 3200
        if schema_name.startswith("hr_message"):
            max_tokens = 1200
        payload: dict = {
            "model": self.settings.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }
        try:
            return await self._request(payload)
        except LLMError as exc:
            if "HTTP 400" not in str(exc) and "HTTP 422" not in str(exc):
                raise
        payload.pop("response_format", None)
        return await self._request(payload)

    async def test_connection(self) -> None:
        payload = {
            "model": self.settings.model,
            "messages": [{"role": "user", "content": "Reply with OK."}],
            "temperature": 0,
            "max_tokens": 4,
        }
        await self._request(payload)

    async def _request(self, payload: dict) -> str:
        headers = {
            "Authorization": f"Bearer {self.settings.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Resume-Matcher-Local/2.5",
        }
        try:
            async with httpx.AsyncClient(timeout=self.settings.timeout_seconds, follow_redirects=False) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise LLMError("模型连接失败。请检查网络、Base URL，或稍后重试。") from exc
        if response.status_code in {401, 403}:
            raise LLMError("API 鉴权失败。请检查密钥、模型权限与接口地址。")
        if response.status_code == 429:
            raise LLMError("模型额度不足或请求过于频繁。请稍后重试。")
        if response.status_code >= 400:
            raise LLMError(
                f"模型接口返回 HTTP {response.status_code}。请检查模型名称、接口兼容性或稍后重试。"
            )
        if len(response.content) > MAX_RESPONSE_BYTES:
            raise LLMError("模型返回内容过大，已停止处理。")
        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMError("模型接口返回结构不兼容。请确认它支持 OpenAI Chat Completions。") from exc
        return str(content)
