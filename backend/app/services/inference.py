from __future__ import annotations

import json
from functools import cached_property

import httpx

from app.core.config import Settings


class InferenceGateway:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @cached_property
    def pipeline(self):
        if self.settings.inference_provider != "local_pipeline":
            return None
        from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline

        tokenizer = AutoTokenizer.from_pretrained(self.settings.local_model_name)
        model = AutoModelForCausalLM.from_pretrained(self.settings.local_model_name, device_map="auto")
        return pipeline("text-generation", model=model, tokenizer=tokenizer)

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        provider = self.settings.inference_provider.lower()
        if provider == "mock":
            return self._mock_response(user_prompt)
        if provider in {"vllm", "tgi"}:
            return self._generate_via_openai_compatible(system_prompt, user_prompt)
        if provider == "ollama":
            return self._generate_via_ollama(system_prompt, user_prompt)
        if provider == "local_pipeline":
            return self._generate_locally(system_prompt, user_prompt)
        raise ValueError(f"Unsupported inference provider: {self.settings.inference_provider}")

    def _generate_via_openai_compatible(self, system_prompt: str, user_prompt: str) -> str:
        payload = {
            "model": self.settings.inference_model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.settings.temperature,
            "max_tokens": self.settings.max_generation_tokens,
        }
        timeout = httpx.Timeout(
            connect=min(5.0, self.settings.inference_timeout_seconds),
            read=self.settings.inference_timeout_seconds,
            write=self.settings.inference_timeout_seconds,
            pool=min(5.0, self.settings.inference_timeout_seconds),
        )
        with httpx.Client(timeout=timeout) as client:
            response = client.post(f"{self.settings.inference_base_url.rstrip('/')}/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()
        return data["choices"][0]["message"]["content"]

    def _generate_locally(self, system_prompt: str, user_prompt: str) -> str:
        prompt = f"System: {system_prompt}\nUser: {user_prompt}\nAssistant:"
        outputs = self.pipeline(
            prompt,
            max_new_tokens=self.settings.max_generation_tokens,
            temperature=self.settings.temperature,
            do_sample=True,
        )
        return outputs[0]["generated_text"].split("Assistant:", 1)[-1].strip()

    def _generate_via_ollama(self, system_prompt: str, user_prompt: str) -> str:
        payload = {
            "model": self.settings.ollama_model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "options": {
                "temperature": self.settings.temperature,
            },
        }
        timeout = httpx.Timeout(
            connect=min(5.0, self.settings.inference_timeout_seconds),
            read=self.settings.inference_timeout_seconds,
            write=self.settings.inference_timeout_seconds,
            pool=min(5.0, self.settings.inference_timeout_seconds),
        )
        with httpx.Client(timeout=timeout) as client:
            response = client.post(f"{self.settings.ollama_base_url.rstrip('/')}/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()
        return data["message"]["content"]

    def _mock_response(self, prompt: str) -> str:
        preview = prompt[:700]
        return json.dumps(
            {
                "answer": "Mock inference mode is active. Connect a self-hosted vLLM/TGI endpoint or switch to local_pipeline for real legal generation.",
                "reasoning": "The request was processed using repository templates and retrieved legal context, but no trained generation model is attached.",
                "preview": preview,
            }
        )
