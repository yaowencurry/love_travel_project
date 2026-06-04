from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from travel_agent.agent_models import AgentStage, ModelDecision
from travel_agent.prompts import STAGE_PROMPTS, SYSTEM_PROMPT


class MissingLLMConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class LLMConfig:
    api_key: str
    base_url: str = "https://airouter.bytedance.net/v1"
    model: str = "gpt-5.5"

    @classmethod
    def from_env(cls) -> "LLMConfig":
        api_key = os.getenv("AIROUTER_API_KEY", "").strip()
        if not api_key:
            raise MissingLLMConfigError("缺少 AIROUTER_API_KEY，无法调用模型。")
        return cls(
            api_key=api_key,
            base_url=os.getenv("AIROUTER_BASE_URL", cls.base_url).strip() or cls.base_url,
            model=os.getenv("TRAVEL_AGENT_MODEL", cls.model).strip() or cls.model,
        )


class OpenAIChatClient:
    def __init__(self, config: LLMConfig | None = None) -> None:
        self.config = config
        self._client: Any | None = None

    @property
    def client(self) -> Any:
        if self._client is None:
            try:
                from openai import AsyncOpenAI
                import httpx
            except ImportError as exc:  # pragma: no cover - depends on environment packaging
                raise RuntimeError("缺少 openai 依赖，请先安装项目依赖。") from exc
            config = self.config or LLMConfig.from_env()
            self._client = AsyncOpenAI(
                api_key=config.api_key,
                base_url=config.base_url,
                http_client=httpx.AsyncClient(trust_env=False),
            )
        return self._client

    @property
    def resolved_config(self) -> LLMConfig:
        return self.config or LLMConfig.from_env()

    def build_chat_request(self, *, stage: AgentStage, payload: dict) -> dict[str, Any]:
        schema = ModelDecision.model_json_schema()
        content = {
            "stage": stage,
            "stage_instruction": STAGE_PROMPTS.get(stage, ""),
            "payload": payload,
        }
        return {
            "model": self.resolved_config.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(content, ensure_ascii=False)},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "travel_agent_decision",
                    "schema": schema,
                    "strict": False,
                },
            },
        }

    async def decide(self, *, stage: AgentStage, payload: dict) -> ModelDecision:
        request = self.build_chat_request(stage=stage, payload=payload)
        completion = await self.client.chat.completions.create(**request)
        content = completion.choices[0].message.content
        if not content:
            raise RuntimeError("模型返回为空。")
        return ModelDecision.model_validate_json(content)
