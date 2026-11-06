# Publicacion temporal con Vercel, Render y Neon

Lumora ya tiene una base Neon preparada:

- Proyecto: `lumora`
- Region: AWS Sao Paulo
- PostgreSQL 17 con pgvector 0.8.0
- Migraciones aplicadas hasta `0006_author_follows`

No se necesita comprar un dominio. Vercel entregara una URL `*.vercel.app` y Render
otra `*.onrender.com`.

## 1. Publicar la API en Render

1. Sube este directorio a un repositorio privado de GitHub.
2. En Render, selecciona **New > Blueprint** e importa el repositorio. Render detecta
   `render.yaml` y crea `lumora-api`.
3. Completa las variables que Render solicita:
   - `DATABASE_URL`: la cadena de conexion de Neon para el proyecto `lumora`.
   - `REDIS_URL`: la URL de una instancia Render Key Value o Upstash Redis.
   - `OLLAMA_API_KEY`: una clave de Ollama Cloud creada en `https://ollama.com`.
   - `CORS_ORIGINS`: se completa despues de obtener la URL de Vercel.
4. Espera a que el despliegue termine y copia la URL `https://...onrender.com`.

Render usa `https://ollama.com` y el modelo `gemma4:cloud`. Los bots con modelos
locales previos tambien usan el modelo Cloud en este despliegue. La memoria conserva
canon, recuerdos fijados, resumen y cronologia; la busqueda vectorial queda pendiente
de un proveedor de embeddings remoto.

## 2. Publicar el frontend en Vercel

1. En Vercel, selecciona **Add New > Project** e importa el mismo repositorio.
2. Configura **Root Directory** como `frontend` y deja Vite como framework detectado.
3. Define `VITE_AI_MODE=cloud` y `VITE_API_URL` con
   `https://TU-API.onrender.com/api/v1` antes de desplegar.
4. Al terminar, Vercel entrega una URL `https://...vercel.app`.

## 3. Conectar ambas URLs

En Render, actualiza `CORS_ORIGINS` con la URL exacta de Vercel, por ejemplo:

```env
CORS_ORIGINS=https://lumora-app.vercel.app
```

Guarda y redepliega la API. `TRUSTED_HOSTS` se completa automaticamente desde Render.
Prueba primero `https://TU-API.onrender.com/health` y luego la URL de Vercel.

La base Neon queda aislada de los secretos del repositorio. No pegues la cadena de
conexion, contrasenas ni JWT en archivos versionados.
