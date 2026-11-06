# Despliegue de produccion

Lumora arranca en modo de produccion solo cuando se desactiva la identidad de
desarrollo, se define un secreto JWT propio, Redis esta disponible y se declaran los
dominios permitidos. Si falta una de esas condiciones, la API se detiene al iniciar.

## Variables obligatorias

Crea `.env.production` fuera del control de versiones con, como minimo:

```env
POSTGRES_PASSWORD=una-contrasena-larga-y-unica
LOCAL_JWT_SECRET=un-secreto-aleatorio-largo-y-unico
ALLOW_LOCAL_AUTH=true
ALLOW_DEV_AUTH=false
TRUSTED_HOSTS=lumora.example.com
CORS_ORIGINS=https://lumora.example.com
OLLAMA_CHAT_MODEL=gemma4:12b
OLLAMA_EMBEDDING_MODEL=qwen3-embedding:0.6b
```

Para acceso con Google, configura `SUPABASE_URL`, `SUPABASE_ANON_KEY` y
`SUPABASE_JWT_SECRET`, y registra `https://lumora.example.com` como URL de redireccion
en Supabase Auth.

## Inicio

1. Instala los modelos de Ollama en el equipo que ejecuta la inferencia.
2. Inicia PostgreSQL, Redis, API y web: `docker compose -f docker-compose.production.yml --env-file .env.production up -d --build`.
3. Ejecuta las migraciones dentro de la API: `docker compose -f docker-compose.production.yml exec api alembic upgrade head`.
4. Coloca HTTPS delante del puerto 80 mediante el proveedor de alojamiento o un proxy TLS.
5. Verifica `https://lumora.example.com/health` y crea una cuenta nueva por correo antes de abrir el sitio al publico.

Los contenedores no descargan los modelos: Ollama se mantiene separado para controlar
la memoria, GPU y almacenamiento del host. En Windows, `host.docker.internal` permite
que la API del contenedor alcance Ollama local.
