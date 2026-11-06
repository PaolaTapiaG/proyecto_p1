# Mapa de cambios

Este documento indica donde se implemento cada parte de la evolucion PostgreSQL, pgvector, Ollama y React.

## Backend

| Cambio | Ubicacion |
| --- | --- |
| Configuracion PostgreSQL, Redis, Ollama, embeddings y Supabase | `app/core/config.py`, `.env.example` |
| Entidades principales, favoritos y comentarios de usuario | `app/db/models.py` |
| Migracion pgvector, claves foraneas e indice HNSW | `alembic/versions/0001_initial.py` |
| Controles narrativos, fuente canonica y alternativas | `alembic/versions/0002_narrative_controls.py`, `app/db/models.py` |
| Favoritos y comentarios de mejora/error | `alembic/versions/0003_product_surfaces.py`, `app/db/models.py` |
| Confirmacion adulta y modo +18 por conversacion | `alembic/versions/0004_mature_content_controls.py`, `app/db/models.py`, `app/modules/users`, `app/modules/conversations` |
| API de identidades jugables | `app/modules/personas/router.py`, `schemas.py` |
| API de bots, favoritos, perfil del autor y asistencia IA | `app/modules/characters/router.py`, `app/modules/users/router.py` |
| Contrato IA y proveedores Ollama/OpenAI/mock | `app/modules/ai/provider.py` |
| Generacion directa de escenas, continuidad compacta, control causal, antirrepeticion, ambos protagonistas, 8 parrafos, 30 alternativas, continuar, sugerir, rebobinar y SSE | `app/modules/conversations/orchestrator.py`, `router.py`, `schemas.py` |
| Investigacion de personajes por MediaWiki | `app/modules/research/service.py`, `app/modules/characters/router.py` |
| Carga y servicio local de imagenes | `app/modules/uploads/router.py`, `app/main.py` |
| Embeddings y recuperacion por distancia coseno | `app/modules/memory/service.py` |
| Memorias fijadas y canon como anclas, mas estado automatico compacto y recuperacion vectorial por turno | `app/modules/memory/service.py`, `app/modules/conversations/router.py`, `app/modules/conversations/orchestrator.py` |
| Moderacion contextual para contenido adulto, violencia grafica y proteccion absoluta de menores | `app/modules/moderation/service.py` |
| Rutas `/bots`, `/characters` compatibles y `/personas` | `app/api/router.py` |
| Acceso por correo, JWT local y preparacion Supabase Google | `app/modules/auth`, `app/core/auth.py`, `frontend/src/supabaseClient.js` |
| Perfil, soporte Discord y comentarios | `app/modules/users`, `frontend/src/components/SettingsView.jsx` |

## Seguridad e infraestructura

| Cambio | Ubicacion |
| --- | --- |
| RLS de usuarios, identidades, bots, chats, memoria, favoritos y comentarios | `supabase/rls.sql` |
| Bucket privado y politicas de avatares | `supabase/storage.sql` |
| Vista previa aislada del backend | `scripts/run_preview.py` |
| Inicio reproducible de Vite | `scripts/run_frontend.py` |
| Preparacion segura de PostgreSQL y pgvector | `scripts/setup_postgres.py`, `postgres/pgadmin_setup.sql` |
| Configuracion local de credenciales PostgreSQL | `scripts/configure_postgres.py` |

## Frontend

| Cambio | Ubicacion |
| --- | --- |
| Historial, chat nuevo, alternativas, continuar, sugerir, rebobinar, memoria y boton de comillas | `frontend/src/App.jsx`, `frontend/src/components/MemoryPanel.jsx` |
| Cliente API, sesiones, favoritos, cargas y lector SSE | `frontend/src/api.js` |
| Formularios de bot/identidad, avatar y asistencia IA | `frontend/src/components/CreateForms.jsx` |
| Tarjetas de Explorar y favoritos | `frontend/src/components/DiscoverGrid.jsx` |
| Acceso por correo/Google y pantalla completa de Ajustes | `frontend/src/components/AuthModal.jsx`, `SettingsView.jsx` |
| Modal y avatar reutilizables | `frontend/src/components/Modal.jsx`, `BotAvatar.jsx` |
| Poppins, titulos degradados, paleta violeta/rosa/blanco, chat izquierda/derecha, burbuja distintiva, aura, indicador luminoso y responsive | `frontend/src/main.jsx`, `frontend/src/styles.css`, `frontend/package.json` |
| Confirmacion adulta en Ajustes y modo +18 independiente en el chat | `frontend/src/components/SettingsView.jsx`, `frontend/src/App.jsx` |
| Configuracion Vite y proxy a FastAPI | `frontend/vite.config.js` |
| Imagen de exploracion, avatar Astra y logo de Lumora | `frontend/public/assets/story-portals.png`, `astra-avatar.png`, `lumora-logo.png` |

## Pruebas

`tests/test_api.py` cubre identidad, autoria y privacidad, memoria fijada, favoritos, perfil publico, asistencia IA, acceso local, comentarios, configuracion narrativa, minimo de 8 parrafos, alternativas distintas, repeticion interna, foco causal, contenido adulto, continuar, respuesta sugerida, rebobinado, JSON/SSE y carga de imagen. La prueba usa proveedor mock y SQLite para ser determinista; Ollama `qwen3:8b` se verifica por separado contra su API local con la escena de Noah y Arthur.
