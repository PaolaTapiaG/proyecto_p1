# Evaluacion narrativa local

Lumora incluye veinte escenas fijas para comparar Qwen3 y Gemma 4 sin cambiar las
condiciones entre modelos. Evalua continuidad, voz del personaje, iniciativa,
naturalidad, repeticion y latencia.

## Preparacion

El equipo actual tiene Qwen3. Para comparar Gemma, instala solo los modelos que su
hardware pueda ejecutar:

```powershell
ollama pull gemma4:12b
ollama pull gemma4:26b
```

## Ejecucion

```powershell
python scripts/evaluate_narrative_models.py --models qwen3:8b gemma4:12b gemma4:26b
```

El informe se guarda en `results/narrative-evaluation.json`. Cada resultado conserva
la respuesta original, latencia, tokens, cantidad de parrafos y deteccion de parrafos
duplicados. Completa los cuatro campos `manual_scores` con valores de 1 a 5 antes de
decidir el modelo predeterminado.

No elijas solo por velocidad: para Lumora la continuidad y la voz estable del
personaje valen mas que una respuesta unos segundos mas rapida.
