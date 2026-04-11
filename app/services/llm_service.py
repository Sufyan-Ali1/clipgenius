"""
LLM Service - Single Responsibility: LLM provider management

Unified interface for all LLM providers (Groq, Gemini, OpenAI, Ollama, Together).
"""

from abc import ABC, abstractmethod
from typing import Optional
import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("llm_service")


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the provider name."""
        pass

    @abstractmethod
    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Generate a response from the LLM."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the provider is available."""
        pass


class GroqProvider(BaseLLMProvider):
    """Groq cloud LLM provider - Fast inference with free tier."""

    def __init__(self):
        self.api_key = settings.GROQ_API_KEY
        self.model = settings.LLM_MODEL

    @property
    def name(self) -> str:
        return "groq"

    def is_available(self) -> bool:
        return bool(self.api_key)

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        if not self.api_key:
            raise RuntimeError("Groq API key not set. Set GROQ_API_KEY in .env")

        try:
            from groq import Groq
        except ImportError:
            raise RuntimeError("groq package not installed. Run: pip install groq")

        client = Groq(api_key=self.api_key)

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.7,
            max_tokens=4096,
        )
        return response.choices[0].message.content


class GeminiProvider(BaseLLMProvider):
    """Google Gemini LLM provider - Free tier available."""

    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        # Map to valid model names
        model_map = {
            "gemini": "gemini-2.0-flash",
            "gemini-flash": "gemini-2.0-flash",
            "gemini-1.5-flash": "gemini-2.0-flash",
            "gemini-pro": "gemini-1.5-pro-latest",
        }
        self.model = model_map.get(settings.LLM_MODEL, settings.LLM_MODEL)
        if "gemini" not in self.model.lower():
            self.model = "gemini-2.0-flash"

    @property
    def name(self) -> str:
        return "gemini"

    def is_available(self) -> bool:
        return bool(self.api_key)

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        if not self.api_key:
            raise RuntimeError("Gemini API key not set. Get one at https://aistudio.google.com/apikey")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"

        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt

        payload = {
            "contents": [{"parts": [{"text": full_prompt}]}],
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 4096}
        }

        response = httpx.post(
            url,
            params={"key": self.api_key},
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=120.0
        )
        response.raise_for_status()

        result = response.json()
        candidates = result.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            if parts:
                return parts[0].get("text", "")
        return ""


class OpenAIProvider(BaseLLMProvider):
    """OpenAI GPT LLM provider."""

    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        model_map = {
            "gpt4": "gpt-4o",
            "gpt-4": "gpt-4o",
            "gpt4o": "gpt-4o",
            "gpt4-mini": "gpt-4o-mini",
            "openai": "gpt-4o-mini",
        }
        self.model = model_map.get(settings.LLM_MODEL, settings.LLM_MODEL)
        if "gpt" not in self.model.lower():
            self.model = "gpt-4o-mini"

    @property
    def name(self) -> str:
        return "openai"

    def is_available(self) -> bool:
        return bool(self.api_key)

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        if not self.api_key:
            raise RuntimeError("OpenAI API key not set. Set OPENAI_API_KEY in .env")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            json={"model": self.model, "messages": messages, "temperature": 0.7, "max_tokens": 4096},
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"},
            timeout=120.0
        )
        response.raise_for_status()

        result = response.json()
        choices = result.get("choices", [])
        if choices:
            return choices[0].get("message", {}).get("content", "")
        return ""


class OllamaProvider(BaseLLMProvider):
    """Ollama local LLM provider - Free, runs locally."""

    def __init__(self):
        self.host = "http://localhost:11434"
        self.model = settings.LLM_MODEL
        self.timeout = 120.0

    @property
    def name(self) -> str:
        return "ollama"

    def is_available(self) -> bool:
        try:
            response = httpx.get(f"{self.host}/api/tags", timeout=5.0)
            if response.status_code == 200:
                models = response.json().get("models", [])
                model_names = [m.get("name", "").split(":")[0] for m in models]
                return self.model in model_names or any(self.model in name for name in model_names)
            return False
        except Exception:
            return False

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = httpx.post(
            f"{self.host}/api/chat",
            json={
                "model": self.model,
                "messages": messages,
                "stream": False,
                "options": {"temperature": 0.7, "num_predict": 4096}
            },
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.json().get("message", {}).get("content", "")


class TogetherProvider(BaseLLMProvider):
    """Together AI cloud LLM provider - Free credits for new users."""

    def __init__(self):
        self.api_key = settings.TOGETHER_API_KEY
        model_map = {
            "llama3": "meta-llama/Llama-3-70b-chat-hf",
            "llama3-8b": "meta-llama/Llama-3-8b-chat-hf",
            "mixtral": "mistralai/Mixtral-8x7B-Instruct-v0.1",
            "mistral": "mistralai/Mistral-7B-Instruct-v0.2",
        }
        self.model = model_map.get(settings.LLM_MODEL, settings.LLM_MODEL)

    @property
    def name(self) -> str:
        return "together"

    def is_available(self) -> bool:
        return bool(self.api_key)

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        if not self.api_key:
            raise RuntimeError("Together API key not set. Set TOGETHER_API_KEY in .env")

        try:
            from together import Together
        except ImportError:
            raise RuntimeError("together package not installed. Run: pip install together")

        client = Together(api_key=self.api_key)

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.7,
            max_tokens=4096,
        )
        return response.choices[0].message.content


class LLMService:
    """
    Single Responsibility: Manage LLM provider selection and generation.
    """

    PROVIDERS = {
        "groq": GroqProvider,
        "gemini": GeminiProvider,
        "openai": OpenAIProvider,
        "ollama": OllamaProvider,
        "together": TogetherProvider,
    }

    def __init__(self, provider: Optional[str] = None):
        self.provider_name = (provider or settings.LLM_PROVIDER).lower()
        self._provider = None

    def _get_provider(self) -> BaseLLMProvider:
        """Get the configured LLM provider instance."""
        if self._provider is None:
            if self.provider_name not in self.PROVIDERS:
                available = ", ".join(self.PROVIDERS.keys())
                raise ValueError(f"Unknown provider: {self.provider_name}. Available: {available}")
            self._provider = self.PROVIDERS[self.provider_name]()
        return self._provider

    @property
    def name(self) -> str:
        """Get provider name."""
        return self._get_provider().name

    def is_available(self) -> bool:
        """Check if provider is available."""
        return self._get_provider().is_available()

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Generate response from LLM."""
        provider = self._get_provider()
        logger.info(f"Generating with {provider.name}...")
        return provider.generate(prompt, system_prompt)


def get_llm_provider(provider_name: Optional[str] = None) -> LLMService:
    """Factory function to get LLM service instance."""
    return LLMService(provider_name)
