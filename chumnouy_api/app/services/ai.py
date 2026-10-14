"""AI provider plumbing, configured per workspace.

A workspace brings its own provider/key, stored in ``workspace.settings``
(``ai_provider``, ``ai_api_key``, ``ai_model``, ``ai_base_url``); the
``AI_*`` environment variables are the fallback so a trial workspace works out
of the box. This is the Chumnouy generalization of Chmaba POS
``services/ai.py`` (same provider dialects and error types, platform-global
settings → per-workspace).

OpenAI/DeepSeek speak ``/chat/completions``; Anthropic speaks ``/messages``. No
SDK is pulled in — a plain ``httpx`` POST keeps the dependency surface tiny.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx

from app.config import settings
from app.models import Workspace

AI_SETTING_KEYS: tuple[str, ...] = ("ai_provider", "ai_api_key", "ai_model", "ai_base_url")

_ENV_AI_DEFAULTS: dict[str, str | None] = {
    "ai_provider": settings.ai_provider,
    "ai_api_key": settings.ai_api_key,
    "ai_model": settings.ai_model,
    "ai_base_url": settings.ai_base_url,
}


@dataclass(frozen=True)
class Provider:
    code: str
    label: str
    base_url: str
    default_model: str
    dialect: str  # "openai" | "anthropic"


PROVIDERS: tuple[Provider, ...] = (
    Provider("openai", "ChatGPT (OpenAI)", "https://api.openai.com/v1", "gpt-4o-mini", "openai"),
    Provider("deepseek", "DeepSeek", "https://api.deepseek.com/v1", "deepseek-chat", "openai"),
    Provider(
        "anthropic",
        "Claude (Anthropic)",
        "https://api.anthropic.com/v1",
        "claude-3-5-sonnet-latest",
        "anthropic",
    ),
)

_PROVIDER_BY_CODE = {provider.code: provider for provider in PROVIDERS}


class AIError(Exception):
    """The AI provider was reachable-but-failed, or could not be reached."""


class AINotConfiguredError(AIError):
    """No provider or API key is configured. A user-fixable setup problem."""


def provider_catalog() -> list[dict[str, str]]:
    return [
        {
            "code": provider.code,
            "label": provider.label,
            "default_model": provider.default_model,
            "base_url": provider.base_url,
        }
        for provider in PROVIDERS
    ]


def load_ai_settings(workspace: Workspace) -> dict[str, str | None]:
    """Effective AI settings: workspace overrides, else env defaults."""
    stored = workspace.settings or {}
    effective = dict(_ENV_AI_DEFAULTS)
    for key in AI_SETTING_KEYS:
        value = stored.get(key)
        if value not in (None, ""):
            effective[key] = value
    return effective


def resolve_provider(settings_map: dict[str, str | None]) -> tuple[Provider | None, str]:
    """Return the configured provider and the model that will be used."""
    code = (settings_map.get("ai_provider") or "").strip().lower()
    provider = _PROVIDER_BY_CODE.get(code)
    model = (settings_map.get("ai_model") or "").strip() or (provider.default_model if provider else "")
    return provider, model


def _extract_usage(provider: Provider, data: dict) -> dict[str, int]:
    """Normalize a provider's token usage to prompt/completion counts."""
    usage = data.get("usage") or {}
    if provider.dialect == "anthropic":
        return {
            "prompt_tokens": int(usage.get("input_tokens") or 0),
            "completion_tokens": int(usage.get("output_tokens") or 0),
        }
    return {
        "prompt_tokens": int(usage.get("prompt_tokens") or 0),
        "completion_tokens": int(usage.get("completion_tokens") or 0),
    }


def _resolve(workspace: Workspace) -> tuple[Provider, str, str, str]:
    configured = load_ai_settings(workspace)
    provider, model = resolve_provider(configured)
    api_key = (configured.get("ai_api_key") or "").strip()
    if provider is None:
        raise AINotConfiguredError("No AI provider is configured for this workspace yet.")
    if not api_key:
        raise AINotConfiguredError("No AI API key is stored for this workspace yet.")
    base_url = (configured.get("ai_base_url") or "").strip() or provider.base_url
    return provider, model, api_key, base_url


async def _post_chat(
    provider: Provider,
    model: str,
    api_key: str,
    base_url: str,
    system: str,
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.7,
    max_tokens: int = 1200,
) -> tuple[str, dict[str, int]]:
    """POST a system + messages conversation. Returns ``(content, usage)``."""
    url = f"{base_url.rstrip('/')}" + ("/messages" if provider.dialect == "anthropic" else "/chat/completions")
    if provider.dialect == "anthropic":
        headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
        payload = {"model": model, "max_tokens": max_tokens, "system": system, "messages": messages}
    else:
        headers = {"Authorization": f"Bearer {api_key}", "content-type": "application/json"}
        payload = {
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "messages": [{"role": "system", "content": system}, *messages],
        }
    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(url, headers=headers, json=payload)
    except httpx.TimeoutException as exc:
        raise AIError(f"The AI provider timed out after 45s: {exc}") from exc
    except httpx.HTTPError as exc:
        raise AIError(f"Could not reach the AI provider: {exc}") from exc
    if response.status_code >= 400:
        raise AIError(f"The AI provider rejected the request ({response.status_code}): {response.text[:300]}")
    try:
        data = response.json()
    except ValueError as exc:
        raise AIError("The AI provider returned a non-JSON response") from exc
    if provider.dialect == "anthropic":
        blocks = data.get("content") or []
        content = "".join(block.get("text", "") for block in blocks if isinstance(block, dict))
        return content, _extract_usage(provider, data)
    choices = data.get("choices") or []
    if not choices:
        raise AIError("The AI provider returned no content")
    return (choices[0].get("message") or {}).get("content") or "", _extract_usage(provider, data)


async def complete_chat(
    workspace: Workspace,
    *,
    system: str,
    messages: list[dict[str, str]],
    temperature: float = 0.3,
    max_tokens: int = 900,
) -> dict:
    """Run a multi-turn chat. Raises ``AINotConfiguredError`` / ``AIError``."""
    provider, model, api_key, base_url = _resolve(workspace)
    content, usage = await _post_chat(
        provider, model, api_key, base_url, system, messages,
        temperature=temperature, max_tokens=max_tokens,
    )
    return {"content": content, "provider": provider.code, "model": model, "usage": usage}


def require_chat_config(workspace: Workspace) -> None:
    """Raise ``AINotConfiguredError`` before a stream sends response headers."""
    _resolve(workspace)


def _extract_delta(provider: Provider, parsed: dict) -> str:
    if provider.dialect == "anthropic":
        if parsed.get("type") == "content_block_delta":
            return (parsed.get("delta") or {}).get("text") or ""
        return ""
    choices = parsed.get("choices") or []
    if not choices:
        return ""
    return (choices[0].get("delta") or {}).get("content") or ""


def _accumulate_stream_usage(provider: Provider, parsed: dict, usage_out: dict) -> None:
    if provider.dialect == "anthropic":
        if parsed.get("type") == "message_start":
            usage = (parsed.get("message") or {}).get("usage") or {}
            if usage.get("input_tokens") is not None:
                usage_out["prompt_tokens"] = int(usage.get("input_tokens") or 0)
        elif parsed.get("type") == "message_delta":
            usage = parsed.get("usage") or {}
            if usage.get("output_tokens") is not None:
                usage_out["completion_tokens"] = int(usage.get("output_tokens") or 0)
        return
    if parsed.get("usage"):
        usage_out.update(_extract_usage(provider, parsed))


async def stream_chat(
    workspace: Workspace,
    *,
    system: str,
    messages: list[dict[str, str]],
    temperature: float = 0.3,
    max_tokens: int = 900,
    usage_out: dict | None = None,
) -> AsyncIterator[str]:
    """Yield text deltas from the configured provider (OpenAI + Anthropic formats)."""
    import json

    provider, model, api_key, base_url = _resolve(workspace)
    if usage_out is not None:
        usage_out["provider"] = provider.code
        usage_out["model"] = model
    url = f"{base_url.rstrip('/')}" + ("/messages" if provider.dialect == "anthropic" else "/chat/completions")
    if provider.dialect == "anthropic":
        headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
        payload = {"model": model, "max_tokens": max_tokens, "system": system, "messages": messages, "stream": True}
    else:
        headers = {"Authorization": f"Bearer {api_key}", "content-type": "application/json"}
        payload = {
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
            "stream_options": {"include_usage": True},
            "messages": [{"role": "system", "content": system}, *messages],
        }
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                if response.status_code >= 400:
                    body = await response.aread()
                    raise AIError(
                        f"The AI provider rejected the request ({response.status_code}): "
                        f"{body[:300].decode(errors='ignore')}"
                    )
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    if not data:
                        continue
                    try:
                        parsed = json.loads(data)
                    except ValueError:
                        continue
                    if usage_out is not None:
                        _accumulate_stream_usage(provider, parsed, usage_out)
                    text = _extract_delta(provider, parsed)
                    if text:
                        yield text
    except httpx.TimeoutException as exc:
        raise AIError(f"The AI provider timed out: {exc}") from exc
    except httpx.HTTPError as exc:
        raise AIError(f"Could not reach the AI provider: {exc}") from exc
