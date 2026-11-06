# Lumora

Aplicacion de bots de roleplay construida como monolito modular con FastAPI y React. El backend usa PostgreSQL como base principal, pgvector para memoria semantica y Ollama con Qwen3 8B para generar respuestas localmente.

## Tecnologias

| Capa | Implementacion |
| --- | --- |
| Frontend | React 19, Vite y Lucide |
| API | Python, FastAPI, SQLAlchemy y Alembic |
| IA local | Ollama `qwen3:8b` |
| Embeddings | Ollama `qwen3-embedding:0.6b`, 1024 dimensiones |
| Datos | PostgreSQL 17 y pgvector |
| Infraestructura | Redis para cache, colas y bloqueo por conversacion |
| Integraciones preparadas | Supabase Auth, Storage, PostgreSQL y RLS |

## Vista previa local

Los modelos de Ollama deben estar disponibles antes de iniciar el backend:

```powershell
ollama pull qwen3:8b
ollama pull qwen3-embedding:0.6b
```

Para bots con narrativa mas extensa, instala solo los perfiles que pueda ejecutar tu equipo:

```bash
ollama pull gemma4:12b
ollama pull gemma4:26b
```

Al crear un personaje puedes elegir Qwen3 8B para velocidad, Gemma 4 12B para narrativa o Gemma 4 26B para historias largas. El roleplay usa modo rapido; la asistencia de creacion puede usar razonamiento.

En una terminal inicia la API de vista previa. Esta usa una base SQLite aislada, pero mantiene Ollama real:

```powershell
cd C:\Lumora
python scripts\run_preview.py
```

Si `8011` ya contiene otra instancia sana de Lumora, el comando lo informa y termina sin lanzar el error `WinError 10048`. Puedes elegir otro puerto con `LUMORA_PREVIEW_PORT`.

En otra terminal inicia React:

```powershell
cd C:\Lumora
python scripts\run_frontend.py
```

- Aplicacion React: `http://127.0.0.1:5173`
- API de vista previa: `http://127.0.0.1:8011`
- Documentacion OpenAPI: `http://127.0.0.1:8011/docs`

`index.py` es el punto de entrada normal y escucha en `http://127.0.0.1:8000`.

## PostgreSQL y pgvector

PostgreSQL 17 esta instalado localmente y la base esperada se llama `Lumora`. Antes de migrar, instala pgvector en el servidor: debe existir `C:\Program Files\PostgreSQL\17\share\extension\vector.control`.

1. Desde pgAdmin 4, abre Query Tool sobre `Lumora` y ejecuta [postgres/pgadmin_setup.sql](postgres/pgadmin_setup.sql), o usa el asistente seguro:

```powershell
python scripts\setup_postgres.py
```

El asistente solicita la contrasena de `postgres` de forma oculta, no la guarda y aplica Alembic. Tambien comprueba pgvector antes de intentar la conexion.

Cuando la migracion termine, configura la conexion local de FastAPI. Este segundo asistente valida la base y guarda la URL solamente en `.env`, archivo excluido del control de versiones:

```powershell
python scripts\configure_postgres.py
```

2. La operacion equivalente en Query Tool es:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

3. Copia `.env.example` a `.env` y define una URL valida:

```dotenv
DATABASE_URL=postgresql+psycopg://postgres:TU_PASSWORD@127.0.0.1:5432/Lumora
```

4. Si no usaste el asistente, aplica la migracion:

```powershell
alembic upgrade head
python index.py
```

Con `.env` presente, `python index.py` usa PostgreSQL en el puerto `8000` y `python scripts\run_frontend.py` dirige React automaticamente a ese backend. Sin `.env`, el frontend conserva la vista previa SQLite del puerto `8011`.

La migracion crea las tablas en espanol, una columna `vector(1024)` y un indice HNSW con distancia coseno. En PostgreSQL se recomienda `AUTO_CREATE_TABLES=false`; Alembic es la fuente del esquema.

## API principal

- `GET /health`: estado de API, PostgreSQL y del modelo de IA configurado. Devuelve `503` con estado `degraded` si la base o el modelo local no estan disponibles.
- `GET /api/v1/users/me`: perfil del usuario.
- `PATCH /api/v1/users/me`: cambia nombre, avatar y confirmacion de mayoria de edad.
- `POST /api/v1/auth/register` y `/login`: acceso local por correo.
- `POST /api/v1/users/feedback`: envia una mejora o reporte de error.
- `POST /api/v1/personas`: crea una identidad jugable del usuario.
- `POST /api/v1/bots`: crea un bot.
- `POST /api/v1/bots/assist`: propone personalidad, descripcion, escenario o saludo con Qwen.
- `GET /api/v1/bots/favorites`: lista personajes guardados sin exigir un chat.
- `POST`/`DELETE /api/v1/bots/{id}/favorite`: guarda o quita un favorito.
- `POST /api/v1/bots/{id}/research`: actualiza su referencia publica de personaje.
- `GET /api/v1/bots`: lista bots propios y publicos.
- `POST /api/v1/bots/{id}/memories`: crea memoria canonica del bot.
- `POST /api/v1/uploads/images`: carga un avatar PNG, JPEG o WebP de hasta 6 MB.
- `POST /api/v1/conversations`: inicia una conversacion con bot e identidad opcional.
- `PATCH /api/v1/conversations/{id}`: cambia modo creativo, control de identidad, preferencias y modo +18 por chat.
- `GET`/`POST /api/v1/conversations/{id}/memories`: consulta o fija detalles que Qwen debe recordar.
- `POST /api/v1/conversations/{id}/messages`: envia un mensaje en JSON o SSE.
- `GET /api/v1/conversations/{id}/messages`: recupera el historial.
- `POST /api/v1/conversations/{id}/messages/{message_id}/regenerate`: crea hasta 30 alternativas.
- `POST /api/v1/conversations/{id}/messages/{message_id}/continue`: continua la ultima escena sin repetirla, en JSON o SSE.
- `POST /api/v1/conversations/{id}/suggested-reply`: propone una respuesta para la identidad del usuario sin enviarla.
- `DELETE /api/v1/conversations/{id}/messages/{message_id}/rewind`: conserva el mensaje elegido y elimina los posteriores.
- `PUT /api/v1/conversations/{id}/messages/{message_id}/select`: selecciona la respuesta canonica.

Para SSE envia `{"content":"Hola","stream":true}`. La respuesta emite `chunk`, `replace`, `done` o `error`. El roleplay usa Qwen 3 con una ventana de historial y memorias compactas, y genera una sola escena completa a partir del ultimo cambio de la persona usuaria. El orquestador elimina repeticiones internas y evita frases formularias antes de guardar el resultado. Regenerar incorpora huellas breves de las alternativas previas para producir una version distinta sin convertir el turno en un resumen. Cuando esta activo `auto_roleplay_user`, Qwen interpreta tanto al bot como a la identidad del usuario y desarrolla una escena incluso a partir de una entrada breve. Las rutas antiguas `/api/v1/characters` siguen activas para conservar compatibilidad.

El contenido sexual explicito o la violencia grafica requieren mayoria de edad confirmada y activacion independiente del modo +18 en esa conversacion. Incluso activado, el bot solo eleva el contenido cuando el mensaje actual lo solicita; cualquier sexualizacion de menores se bloquea siempre.

En desarrollo se aceptan `X-User-Id`, `X-User-Email` y `X-User-Name`. En produccion configura Supabase JWT y desactiva `ALLOW_DEV_AUTH`.

El acceso por Google queda disponible al crear `frontend/.env.local` con `VITE_SUPABASE_URL` y `VITE_SUPABASE_PUBLISHABLE_KEY`, habilitar Google en Supabase Auth y registrar las URL de redireccion. El acceso local por correo funciona con `ALLOW_LOCAL_AUTH=true`; cambia `LOCAL_JWT_SECRET` antes de cualquier despliegue.

## Documentacion

- [Arquitectura](docs/ARCHITECTURE.md)
- [Seguridad, Supabase y RLS](docs/SECURITY.md)
- [Mapa exacto de cambios](docs/CHANGES.md)
