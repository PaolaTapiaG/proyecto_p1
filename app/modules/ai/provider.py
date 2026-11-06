import json
from dataclasses import dataclass
from collections.abc import Generator
from typing import Protocol

import httpx

from app.core.config import settings
from app.modules.ai.profiles import narrative_model_profile


@dataclass(frozen=True)
class AIMessage:
    role: str
    content: str


@dataclass(frozen=True)
class AIResponse:
    content: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0


@dataclass(frozen=True)
class AIStreamChunk:
    delta: str = ""
    model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    done: bool = False


@dataclass(frozen=True)
class GenerationOptions:
    temperature: float = 0.7
    top_p: float = 0.8
    top_k: int = 20
    repeat_penalty: float = 1.08
    repeat_last_n: int = 512
    max_tokens: int | None = None
    think: bool | None = None
    context_window: int | None = None
    response_schema: dict | None = None


class AIProvider(Protocol):
    name: str

    def complete(
        self,
        messages: list[AIMessage],
        model: str | None = None,
        options: GenerationOptions | None = None,
    ) -> AIResponse:
        """Genera una respuesta independiente de un proveedor concreto."""

    def stream(
        self,
        messages: list[AIMessage],
        model: str | None = None,
        options: GenerationOptions | None = None,
    ) -> Generator[AIStreamChunk, None, None]:
        """Transmite fragmentos de una respuesta."""


class EmbeddingProvider(Protocol):
    name: str

    def embed(self, text: str) -> list[float]:
        """Convierte texto en un vector normalizado."""


class MockAIProvider:
    name = "mock"

    def complete(
        self,
        messages: list[AIMessage],
        model: str | None = None,
        options: GenerationOptions | None = None,
    ) -> AIResponse:
        last_user_message = next(
            (message.content for message in reversed(messages) if message.role == "user"), ""
        )
        if "REESCRITURA OBLIGATORIA" in last_user_message or "VERSIÓN DESCARTADA" in last_user_message:
            paragraphs = [
                "El personaje cambia de estrategia y actua desde un impulso distinto.",
                "La escena avanza por una consecuencia nueva sin alterar los hechos establecidos.",
                'Su voz rompe el silencio: "Esta vez elegire otro camino".',
                "El entorno responde a esa decision con un detalle concreto y relevante.",
                "La reaccion nace del conflicto presente, no de la respuesta descartada.",
                "Cada gesto sostiene una progresion emocional diferente.",
                "La nueva direccion abre una posibilidad que antes no existia.",
                "El turno termina en movimiento, listo para la siguiente intervencion.",
            ]
        else:
            paragraphs = [
                f"La escena recoge lo que acabas de proponer: {last_user_message}",
                "El personaje observa el entorno y conserva cada detalle establecido anteriormente.",
                'Con una expresion serena, responde: "Te escucho y seguire el curso de esta historia".',
                "Nada cambia de lugar sin una causa dentro de la narracion.",
                "Los gestos y silencios mantienen la personalidad definida para el personaje.",
                "La atmosfera avanza con claridad, sin contradecir lo que el usuario ya escribio.",
                "Una nueva posibilidad aparece en el escenario, preparada para la siguiente decision.",
                "El personaje espera la reaccion del usuario antes de continuar sus acciones.",
            ]
        content = "\n\n".join(paragraphs)
        return AIResponse(
            content=content,
            model=model or "mock-roleplay-v1",
            prompt_tokens=sum(len(message.content.split()) for message in messages),
            completion_tokens=len(content.split()),
        )

    def stream(
        self,
        messages: list[AIMessage],
        model: str | None = None,
        options: GenerationOptions | None = None,
    ) -> Generator[AIStreamChunk, None, None]:
        response = self.complete(messages, model, options)
        words = response.content.split(" ")
        for index, word in enumerate(words):
            yield AIStreamChunk(delta=word + (" " if index < len(words) - 1 else ""))
        yield AIStreamChunk(
            model=response.model,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            done=True,
        )


class OllamaAIProvider:
    name = "ollama"

    def complete(
        self,
        messages: list[AIMessage],
        model: str | None = None,
        options: GenerationOptions | None = None,
    ) -> AIResponse:
        selected_model = model or settings.ollama_chat_model
        generation = options or GenerationOptions()
        payload = {
            "model": selected_model,
            "messages": [
                {"role": message.role, "content": message.content} for message in messages
            ],
            "stream": False,
            "think": settings.ollama_think if generation.think is None else generation.think,
            "keep_alive": settings.ollama_keep_alive,
            "options": {
                "temperature": generation.temperature,
                "top_p": generation.top_p,
                "top_k": generation.top_k,
                "repeat_penalty": generation.repeat_penalty,
                "repeat_last_n": generation.repeat_last_n,
                "num_ctx": self._context_window(selected_model, generation),
                "num_predict": generation.max_tokens or settings.ollama_max_output_tokens,
            },
        }
        if generation.response_schema:
            payload["format"] = generation.response_schema
        response = httpx.post(
            f"{settings.ollama_base_url.rstrip('/')}/api/chat",
            json=payload,
            timeout=300,
        )
        self._raise_for_status(response, selected_model)
        data = response.json()
        content = (data.get("message") or {}).get("content", "").strip()
        if not content:
            raise RuntimeError("Ollama returned an empty response")
        return AIResponse(
            content=content,
            model=data.get("model", selected_model),
            prompt_tokens=data.get("prompt_eval_count", 0),
            completion_tokens=data.get("eval_count", 0),
        )

    def stream(
        self,
        messages: list[AIMessage],
        model: str | None = None,
        options: GenerationOptions | None = None,
    ) -> Generator[AIStreamChunk, None, None]:
        selected_model = model or settings.ollama_chat_model
        generation = options or GenerationOptions()
        payload = {
            "model": selected_model,
            "messages": [
                {"role": message.role, "content": message.content} for message in messages
            ],
            "stream": True,
            "think": settings.ollama_think if generation.think is None else generation.think,
            "keep_alive": settings.ollama_keep_alive,
            "options": {
                "temperature": generation.temperature,
                "top_p": generation.top_p,
                "top_k": generation.top_k,
                "repeat_penalty": generation.repeat_penalty,
                "repeat_last_n": generation.repeat_last_n,
                "num_ctx": self._context_window(selected_model, generation),
                "num_predict": generation.max_tokens or settings.ollama_max_output_tokens,
            },
        }
        if generation.response_schema:
            payload["format"] = generation.response_schema
        with httpx.stream(
            "POST",
            f"{settings.ollama_base_url.rstrip('/')}/api/chat",
            json=payload,
            timeout=300,
        ) as response:
            self._raise_for_status(response, selected_model)
            for line in response.iter_lines():
                if not line:
                    continue
                data = json.loads(line)
                if data.get("done"):
                    yield AIStreamChunk(
                        model=data.get("model", selected_model),
                        prompt_tokens=data.get("prompt_eval_count", 0),
                        completion_tokens=data.get("eval_count", 0),
                        done=True,
                    )
                    continue
                delta = (data.get("message") or {}).get("content", "")
                if delta:
                    yield AIStreamChunk(delta=delta)

    @staticmethod
    def _context_window(model: str, generation: GenerationOptions) -> int:
        if generation.context_window:
            return generation.context_window
        profile = narrative_model_profile(model)
        return profile.context_window if profile else settings.ollama_context_window

    @staticmethod
    def _raise_for_status(response: httpx.Response, model: str) -> None:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                raise RuntimeError(
                    f"El modelo local '{model}' no esta instalado. Ejecuta: ollama pull {model}"
                ) from exc
            raise


class OllamaEmbeddingProvider:
    name = "ollama"

    def embed(self, text: str) -> list[float]:
        response = httpx.post(
            f"{settings.ollama_base_url.rstrip('/')}/api/embed",
            json={
                "model": settings.ollama_embedding_model,
                "input": text,
                "dimensions": settings.ollama_embedding_dimensions,
                "truncate": True,
                "keep_alive": settings.ollama_keep_alive,
            },
            timeout=120,
        )
        response.raise_for_status()
        embeddings = response.json().get("embeddings") or []
        if not embeddings:
            raise RuntimeError("Ollama returned no embedding")
        vector = embeddings[0]
        if len(vector) != settings.ollama_embedding_dimensions:
            raise RuntimeError(
                f"Expected {settings.ollama_embedding_dimensions} embedding dimensions, "
                f"received {len(vector)}"
            )
        return vector


class OpenAIResponsesProvider:
    name = "openai"

    def complete(
        self,
        messages: list[AIMessage],
        model: str | None = None,
        options: GenerationOptions | None = None,
    ) -> AIResponse:
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required when AI_PROVIDER=openai")

        selected_model = model or settings.openai_model
        system_messages = [message.content for message in messages if message.role == "system"]
        input_messages = [
            {"role": message.role, "content": message.content}
            for message in messages
            if message.role != "system"
        ]
        response = httpx.post(
            "https://api.openai.com/v1/responses",
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": selected_model,
                "instructions": "\n\n".join(system_messages),
                "input": input_messages,
                "store": False,
            },
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        usage = data.get("usage") or {}
        return AIResponse(
            content=self._output_text(data),
            model=data.get("model", selected_model),
            prompt_tokens=usage.get("input_tokens", 0),
            completion_tokens=usage.get("output_tokens", 0),
        )

    def stream(
        self,
        messages: list[AIMessage],
        model: str | None = None,
        options: GenerationOptions | None = None,
    ) -> Generator[AIStreamChunk, None, None]:
        response = self.complete(messages, model, options)
        yield AIStreamChunk(delta=response.content)
        yield AIStreamChunk(
            model=response.model,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            done=True,
        )

    @staticmethod
    def _output_text(data: dict) -> str:
        if data.get("output_text"):
            return data["output_text"]
        chunks: list[str] = []
        for item in data.get("output", []):
            if item.get("type") != "message":
                continue
            for content in item.get("content", []):
                if content.get("type") == "output_text" and content.get("text"):
                    chunks.append(content["text"])
        if not chunks:
            raise RuntimeError("The AI provider returned no text")
        return "".join(chunks)


def get_ai_provider() -> AIProvider:
    providers: dict[str, AIProvider] = {
        "mock": MockAIProvider(),
        "ollama": OllamaAIProvider(),
        "openai": OpenAIResponsesProvider(),
    }
    try:
        return providers[settings.ai_provider.lower()]
    except KeyError as exc:
        raise RuntimeError(f"Unsupported AI provider: {settings.ai_provider}") from exc


def get_embedding_provider() -> EmbeddingProvider | None:
    if settings.ai_provider.lower() == "ollama":
        return OllamaEmbeddingProvider()
    return None
