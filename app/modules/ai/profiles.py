"""Perfiles locales que equilibran calidad narrativa, contexto y latencia."""

from dataclasses import dataclass


@dataclass(frozen=True)
class NarrativeModelProfile:
    model_id: str
    label: str
    description: str
    context_window: int


NARRATIVE_MODEL_PROFILES = {
    "qwen3:8b": NarrativeModelProfile(
        model_id="qwen3:8b",
        label="Rapido local",
        description="Para conversaciones agiles y pruebas.",
        context_window=8192,
    ),
    "gemma4:12b": NarrativeModelProfile(
        model_id="gemma4:12b",
        label="Narrativa",
        description="Equilibrio recomendado para historias sostenidas.",
        context_window=16384,
    ),
    "gemma4:26b": NarrativeModelProfile(
        model_id="gemma4:26b",
        label="Narrativa extensa",
        description="Mayor fidelidad de contexto; requiere mas recursos.",
        context_window=24576,
    ),
}


def narrative_model_profile(model_id: str) -> NarrativeModelProfile | None:
    return NARRATIVE_MODEL_PROFILES.get(model_id.casefold())
