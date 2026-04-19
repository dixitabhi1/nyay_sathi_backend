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
            if not response.is_success:
                raise RuntimeError(self._format_upstream_error(response, "text generation"))
            if "application/json" not in response.headers.get("content-type", "").lower():
                raise RuntimeError(
                    "Text generation endpoint returned non-JSON content. "
                    "Check INFERENCE_PROVIDER and INFERENCE_BASE_URL; the URL should be an OpenAI-compatible API endpoint, not a Hugging Face model page."
                )
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
            if not response.is_success:
                raise RuntimeError(self._format_upstream_error(response, "Ollama generation"))
            if "application/json" not in response.headers.get("content-type", "").lower():
                raise RuntimeError("Ollama endpoint returned non-JSON content. Check OLLAMA_BASE_URL.")
            data = response.json()
        return data["message"]["content"]

    def _format_upstream_error(self, response: httpx.Response, context: str) -> str:
        text = response.text[:500]
        if "<!doctype html" in text.lower() or "<html" in text.lower():
            text = "HTML page returned instead of API JSON."
        return f"{context} failed with HTTP {response.status_code}: {text}"

    def _mock_response(self, prompt: str) -> str:
        preview = prompt[:700]
        return json.dumps(
            {
                "answer": "Mock inference mode is active. Connect a self-hosted vLLM/TGI endpoint or switch to local_pipeline for real legal generation.",
                "reasoning": "The request was processed using repository templates and retrieved legal context, but no trained generation model is attached.",
                "preview": preview,
            }
        )
