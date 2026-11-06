# Arquitectura de Lumora

## Decision principal

Lumora es un monolito modular FastAPI: existe un proceso desplegable y una base de datos, mientras cada dominio conserva responsabilidades y rutas propias bajo `app/modules`. El frontend React vive en `frontend` y consume la API mediante JSON y SSE.

## Modulos

| Modulo | Responsabilidad |
| --- | --- |
| Users | Perfil, acceso local por correo, Supabase Auth, soporte y comentarios |
| Personas | Identidades jugables creadas por el usuario |
| Characters | Bots, autoria, visibilidad, favoritos, asistencia IA, avatar y memorias canonicas |
| Conversations | Historial, mensajes, memorias fijadas, autorizacion, alternativas y SSE |
| AI | Contrato intercambiable y adaptadores Ollama, OpenAI y mock |
| Memory | Embeddings, memoria canonica/personal y busqueda pgvector |
| Moderation | Politicas de entrada y registro de incidentes |
| Usage | Tokens, proveedor, modelo y coste estimado |
| Subscriptions | Plan y estado de suscripcion |
| Administration | Resumen protegido y auditoria administrativa |

`Characters` mantiene su nombre interno para no romper imports existentes, pero su tabla y API canonicas son `bots` y `/api/v1/bots`.

## Modelo de datos principal

- `usuarios`: cuenta principal y confirmacion explicita de mayoria de edad.
- `personas_usuario`: identidades que el usuario puede interpretar. `id_usuario` referencia al creador.
- `bots`: personajes IA. `id_creador` referencia al autor.
- `memorias_bot`: pares clave/valor y embedding `vector(1024)`, vinculados a bot y opcionalmente a usuario/conversacion.
- `conversaciones`: une usuario, bot e identidad jugable opcional; conserva creatividad, control automatico del usuario, preferencias, minimo de parrafos y activacion +18 independiente.
- `mensajes`: historial ordenado, conteos de tokens, respuesta padre, indice de alternativa y seleccion vigente.
- `favoritos_bot`: relacion usuario-bot; permite guardar un personaje antes de iniciar un chat.
- `comentarios_usuario`: mejoras y reportes de error enviados desde Ajustes.
- `registros_consumo`, `eventos_moderacion`, `suscripciones` y `registros_auditoria_admin`: dominios auxiliares.

## Flujo de un mensaje

1. La API verifica propiedad de la conversacion.
2. Redis adquiere un bloqueo exclusivo por conversacion; en desarrollo existe un bloqueo local de respaldo.
3. Moderation valida la entrada.
4. `RoleplayOrchestrator` combina bot, identidad seleccionada, referencia canonica, memorias de la conversacion e historial seleccionado dentro de un presupuesto de caracteres.
5. El prompt da prioridad a la escena actual y fija sujeto, destinatario, objetos existentes y frontera de control de la identidad del usuario.
6. Para Ollama, el orquestador entrega el turno como una escena a continuar: conserva los hechos y reacciona al ultimo cambio sin resumir ni reescribir el mensaje de la persona usuaria.
7. `AIProvider` envia una generacion directa a `/api/chat`, con temperatura, penalizacion de repeticion y longitud ajustadas al modo creativo del chat. El sistema solo solicita una continuacion si faltan parrafos para el minimo configurado.
8. La respuesta se transmite como SSE `chunk`; la normalizacion final elimina oraciones duplicadas. Si hace falta regenerar, el reintento recibe solo los problemas detectados y no una plantilla por etapas.
9. Al terminar se guardan actividad, consumo, memoria y la alternativa seleccionada.
10. La API emite `done`; los bloqueos o fallos producen `error`.

El flujo JSON usa el mismo orquestador. Otros proveedores conservan el contrato narrativo tradicional, por lo que Ollama puede sustituirse sin cambiar Conversations.

## Control narrativo del chat

- `Regenerar` crea otra reaccion para el mismo turno y mantiene una sola alternativa seleccionada como canonica.
- `Continuar` parte de la ultima respuesta del asistente, no repite lo escrito y agrega 2 o 3 parrafos breves. Cuando la IA no controla a la identidad del usuario, solo mueve al bot y deja su reaccion pendiente.
- `Respuesta sugerida` redacta una posible intervencion de la identidad del usuario, pero solo la coloca en el editor para que la persona pueda modificarla o descartarla.
- `Rebobinar` conserva el mensaje elegido, elimina todos los posteriores y limpia memorias automaticas que podrian contener hechos descartados. Las memorias fijadas manualmente se conservan.
- Con `auto_roleplay_user` activo, Qwen tiene permiso explicito para narrar acciones y dialogos de ambos protagonistas. Desactivarlo restaura la frontera estricta donde el modelo solo controla al bot y personajes secundarios.
- Cada reintento recibe los fallos concretos de la version descartada y el guion original. Las alternativas anteriores se usan solo para impedir copias; nunca vuelven a entrar como continuidad seleccionada.
- El contenido +18 usa dos controles: confirmacion adulta en la cuenta y activacion por conversacion. Aun con ambos activos, solo el mensaje actual puede solicitar iniciativa sexual explicita o violencia grafica; las referencias sexuales a menores se bloquean sin excepcion.

## Investigacion y alternativas

Al crear un bot basado en una obra, `Research` consulta primero Wikipedia en espanol y luego en ingles mediante endpoints fijos de MediaWiki. Solo persiste resumen, URL, origen y fecha; la escena del usuario siempre tiene prioridad sobre esa referencia. No se aceptan URL arbitrarias.

Cada mensaje del usuario puede tener hasta 30 respuestas asistentes. Solo una queda `is_selected=true` y entra en el contexto futuro; regenerar cambia la seleccion y elegir una respuesta anterior restaura esa rama sin duplicar el mensaje del usuario. Las continuaciones se guardan con `kind=continuation` para distinguirlas de una respuesta alternativa.

## Memoria vectorial

`OllamaEmbeddingProvider` usa `/api/embed` con `qwen3-embedding:0.6b`. En PostgreSQL, Memory filtra por bot/usuario y ordena por distancia coseno. La migracion agrega un indice HNSW `vector_cosine_ops`. SQLite solo ofrece un respaldo por importancia/fecha para pruebas y vista previa.

La memoria se organiza en cinco capas: canon del personaje, hechos fijados, relaciones, linea temporal y resumen acumulado. Canon, hechos, relaciones y resumen son anclas: se reenvian en cada turno y no compiten con la similitud vectorial. La linea temporal automatica guarda una situacion planteada y la consecuencia de cierre bajo una clave estable por turno; pgvector recupera solo los hitos pertinentes al mensaje actual. Nunca reinyecta una respuesta completa ni crea una memoria nueva al regenerar. Las memorias automaticas antiguas con prosa completa quedan excluidas del prompt.

## Perfiles de modelo

Cada bot conserva su modelo local: `qwen3:8b` para respuesta rapida, `gemma4:12b` para narrativa equilibrada y `gemma4:26b` para historias extensas en equipos con recursos suficientes. Roleplay, regeneracion y continuacion fuerzan `think=false`; el razonamiento se reserva para asistencia de creacion e investigacion. Los perfiles ajustan la ventana de contexto sin alterar el contrato comun de `AIProvider`.

`scripts/evaluate_narrative_models.py` ejecuta las mismas veinte escenas sobre los modelos indicados y escribe el informe para seleccionar el predeterminado basandose en continuidad, voz, iniciativa, naturalidad y latencia.

## Infraestructura

- PostgreSQL es la base predeterminada; Alembic versiona el esquema.
- Redis cubre cache, cola basica y bloqueo de concurrencia por conversacion.
- Supabase Auth emite JWT; FastAPI conserva la autorizacion del dominio.
- Supabase Storage usa el bucket privado `bot-assets`; la vista previa acepta archivos locales bajo `storage/uploads`.
- Las politicas RLS estan en `supabase/rls.sql` y las de Storage en `supabase/storage.sql`.
- Los avatares locales de demostracion viven en `frontend/public/assets`.

## Limites y proximos pasos

1. Validar JWT mediante JWKS de Supabase y rotacion automatica de claves.
2. Agregar un worker durable para la cola Redis, reintentos e idempotencia.
3. Resumir memorias extensas y definir su retencion/borrado.
4. Incorporar moderacion de salida y politicas configurables por edad y region.
5. Sustituir la carga local por URL firmadas de Supabase Storage en produccion.
6. El acceso local no aplica cuotas ni planes. Si en el futuro se incorpora facturacion, debe ser opcional y no degradar las funciones narrativas actuales.
7. Ejecutar pruebas de integracion continuas contra PostgreSQL/pgvector y Redis reales.
8. Incorporar trazas, metricas y alertas de latencia de Ollama.
