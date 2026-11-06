"""Compara modelos locales con las mismas veinte escenas narrativas de Lumora."""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.modules.ai.profiles import narrative_model_profile
from app.modules.ai.provider import AIMessage, GenerationOptions, OllamaAIProvider


SCENES = [
    ("01-last-action", "Noah deja una carta sellada sobre la mesa. Arthur reconoce el sello de su hermano."),
    ("02-object-continuity", "La unica llave roja sigue dentro del bolsillo de Mara. La puerta del sotano esta cerrada."),
    ("03-voice", "Price recibe una orden apresurada por radio, pero sabe que el equipo esta agotado."),
    ("04-user-agency", "Lia observa a Arthur desde el umbral sin decir una palabra."),
    ("05-relationship", "Tras una discusion, Elena entrega a Tomas el anillo que habia guardado durante anos."),
    ("06-timeline", "Es de madrugada; la tormenta que empezo hace una hora aun golpea los postigos."),
    ("07-small-premise", "Un farol se apaga en la biblioteca vacia."),
    ("08-no-random-threat", "En la cocina, Iris prueba una receta que preparo para su hermana."),
    ("09-dialogue-response", "'No voy a volver a mentirte', dice Dario mientras evita mirar a Vera."),
    ("10-consequence", "El puente de madera cede despues de que Noel cruza con el caballo."),
    ("11-canon", "La detective Vega jamas usa armas; encuentra una pistola abandonada en el muelle."),
    ("12-secret", "Samira descubre que la nota en su bolsillo esta escrita con su propia letra."),
    ("13-slow-romance", "Kai ofrece su abrigo a Ren bajo una lluvia fina, sin invadir su espacio."),
    ("14-investigation", "El mapa marca una habitacion que no existe en los planos del museo."),
    ("15-physical-limits", "Omar tiene la pierna herida y permanece sentado junto a la ventana rota."),
    ("16-emotion", "Clara escucha la cancion que sonaba el dia que perdio a su padre."),
    ("17-mystery-restraint", "La habitacion esta ordenada, salvo por una taza de cafe todavia caliente."),
    ("18-group-dialogue", "Nora, Ivo y Celeste discuten quien debe llevar el mensaje al pueblo vecino."),
    ("19-repair", "Despues de una pelea, Jun coloca las piezas del jarron roto sobre la mesa."),
    ("20-open-ending", "El tren empieza a moverse mientras Ada ve a Leo correr por el anden."),
]

SYSTEM_PROMPT = """Eres el narrador de roleplay de Lumora. Escribe una continuacion en espanol natural.
Respeta literalmente los hechos de la escena, la voz de los personajes, los objetos, capacidades y orden temporal.
No resumas ni repitas la entrada. No inventes un villano, peligro, romance o giro ajeno a ella.
Controla solo al personaje narrado, deja cualquier decision nueva del usuario abierta y termina en una consecuencia inmediata.
Escribe ocho parrafos breves, sin encabezados ni explicaciones."""


def evaluate(model: str, scene_id: str, scene: str) -> dict:
    profile = narrative_model_profile(model)
    started = time.perf_counter()
    response = OllamaAIProvider().complete(
        [
            AIMessage(role="system", content=SYSTEM_PROMPT),
            AIMessage(role="user", content=scene),
        ],
        model=model,
        options=GenerationOptions(
            temperature=0.7,
            top_p=0.86,
            top_k=30,
            repeat_penalty=1.12,
            max_tokens=1100,
            think=False,
            context_window=profile.context_window if profile else None,
        ),
    )
    paragraphs = [part.strip() for part in response.content.split("\n\n") if part.strip()]
    normalized = [" ".join(part.casefold().split()) for part in paragraphs]
    return {
        "scene_id": scene_id,
        "model": response.model,
        "latency_seconds": round(time.perf_counter() - started, 2),
        "prompt_tokens": response.prompt_tokens,
        "completion_tokens": response.completion_tokens,
        "paragraphs": len(paragraphs),
        "duplicate_paragraphs": len(normalized) - len(set(normalized)),
        "response": response.content,
        "manual_scores": {
            "continuity": None,
            "character_voice": None,
            "initiative": None,
            "naturalness": None,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", default=["qwen3:8b", "gemma4:12b"])
    parser.add_argument("--output", type=Path, default=Path("results/narrative-evaluation.json"))
    args = parser.parse_args()

    results = []
    failures = []
    for model in args.models:
        for scene_id, scene in SCENES:
            try:
                result = evaluate(model, scene_id, scene)
                results.append(result)
                print(f"{model} {scene_id}: {result['latency_seconds']}s")
            except Exception as exc:
                failures.append({"model": model, "scene_id": scene_id, "error": str(exc)})
                print(f"{model} {scene_id}: ERROR {exc}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            {
                "created_at": datetime.now().astimezone().isoformat(),
                "scenes": len(SCENES),
                "results": results,
                "failures": failures,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Informe: {args.output}")


if __name__ == "__main__":
    main()
