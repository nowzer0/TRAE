from __future__ import annotations

import hashlib
import json
import os
import random
from typing import Any

from tenacity import retry, stop_after_attempt, wait_exponential

from .config import RuntimeConfig


class LLMClient:
    def __init__(self, runtime: RuntimeConfig):
        self.runtime = runtime

    @retry(reraise=True, stop=stop_after_attempt(5), wait=wait_exponential(min=1, max=30))
    def complete(self, messages: list[dict[str, str]], role: str | None = None) -> str:
        if self.runtime.dry_run:
            return self._mock(messages, role)

        agent = self.runtime.agent(role)
        provider = agent.provider.lower()
        if provider == "openai":
            return self._complete_openai(messages, agent)
        if provider == "gemini":
            return self._complete_gemini(messages, agent)
        if provider == "claude":
            return self._complete_claude(messages, agent)
        if provider == "deepseek":
            return self._complete_openai_compatible(
                messages, agent, base_url="https://api.deepseek.com"
            )
        if provider == "grok":
            return self._complete_openai_compatible(
                messages, agent, base_url="https://api.x.ai/v1"
            )
        raise ValueError(f"Unsupported provider: {agent.provider}")

    def _complete_openai(self, messages: list[dict[str, str]], agent) -> str:
        from openai import OpenAI

        client = OpenAI(api_key=agent.resolved_api_key())
        kwargs: dict[str, Any] = {"model": agent.model, "messages": messages}
        is_reasoning = any(token in agent.model.lower() for token in ("gpt-5", "o1", "o3"))

        if is_reasoning:
            kwargs["max_completion_tokens"] = self.runtime.max_tokens
            if "reasoning_effort" in agent.extra:
                kwargs["reasoning_effort"] = agent.extra["reasoning_effort"]
        else:
            kwargs.update(
                {
                    "temperature": self.runtime.temperature,
                    "top_p": self.runtime.top_p,
                    "max_tokens": self.runtime.max_tokens,
                }
            )

        response = client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""

    def _complete_openai_compatible(
        self, messages: list[dict[str, str]], agent, *, base_url: str
    ) -> str:
        from openai import OpenAI

        client = OpenAI(api_key=agent.resolved_api_key(), base_url=base_url)
        response = client.chat.completions.create(
            model=agent.model,
            messages=messages,
            temperature=self.runtime.temperature,
            top_p=self.runtime.top_p,
            max_tokens=self.runtime.max_tokens,
        )
        return response.choices[0].message.content or ""

    def _complete_gemini(self, messages: list[dict[str, str]], agent) -> str:
        from google import genai
        from google.genai import types

        api_key = agent.resolved_api_key() or os.getenv("GOOGLE_API_KEY")
        timeout_ms = agent.extra.get("timeout_ms", self.runtime.timeout_ms)
        http_options = (
            types.HttpOptions(timeout=int(timeout_ms))
            if timeout_ms and int(timeout_ms) > 0
            else None
        )
        client = genai.Client(api_key=api_key, http_options=http_options)

        system_instruction = None
        contents = []
        for message in messages:
            if message["role"] == "system":
                system_instruction = message["content"]
            else:
                contents.append(
                    types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=message["content"])],
                    )
                )

        thinking_config = None
        if "thinking_level" in agent.extra:
            thinking_config = types.ThinkingConfig(thinking_level=agent.extra["thinking_level"])
        elif "thinking_budget" in agent.extra:
            thinking_config = types.ThinkingConfig(
                thinking_budget=int(agent.extra["thinking_budget"])
            )

        response = client.models.generate_content(
            model=agent.model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                thinking_config=thinking_config,
                temperature=self.runtime.temperature,
                top_p=self.runtime.top_p,
                max_output_tokens=self.runtime.max_tokens,
            ),
        )
        return response.text or ""

    def _complete_claude(self, messages: list[dict[str, str]], agent) -> str:
        import anthropic

        client = anthropic.Anthropic(api_key=agent.resolved_api_key())
        system = ""
        user_messages = []
        for message in messages:
            if message["role"] == "system":
                system = message["content"]
            else:
                user_messages.append(message)
        response = client.messages.create(
            model=agent.model,
            max_tokens=self.runtime.max_tokens,
            temperature=self.runtime.temperature,
            system=system,
            messages=user_messages,
        )
        return response.content[0].text

    def _mock(self, messages: list[dict[str, str]], role: str | None = None) -> str:
        text = "\n".join(message.get("content", "") for message in messages)
        text_lower = text.lower()
        role = role or "A"
        seed = int(hashlib.sha1(f"{role}\n{text}".encode()).hexdigest(), 16)
        rng = random.Random(seed)

        if "judge" in text_lower or "final_label" in text_lower:
            return json.dumps(
                {
                    "final_label": rng.choice(["E", "S", "G", "I"]),
                    "rationale": f"dry-run judge decision for {role}",
                }
            )

        if "classify" in text_lower or '"label"' in text_lower or "e, s, g, i" in text_lower:
            label = rng.choice(["E", "S", "G", "I"])
            spans = {
                "E": "emissions",
                "S": "employees",
                "G": "board",
                "I": "",
            }
            return json.dumps(
                {
                    "label": label,
                    "confidence": round(rng.uniform(0.55, 0.95), 2),
                    "span": spans[label],
                    "rationale": f"dry-run label rationale for annotator {role}",
                }
            )

        if "defend" in text_lower or "debater" in text_lower:
            return json.dumps({"claim": f"dry-run debate claim from annotator {role}"})

        yes_prob = {"A": 0.75, "B": 0.65, "C": 0.55}.get(role, 0.65)
        relevant = rng.random() < yes_prob
        return json.dumps(
            {
                "relevance": "Yes" if relevant else "No",
                "confidence": round(rng.uniform(0.60, 0.95), 2),
                "keywords": ["sustainability", "policy"] if relevant else ["general"],
                "rationale": f"dry-run relevance rationale for annotator {role}",
            }
        )
