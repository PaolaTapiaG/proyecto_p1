-- Ejecutar en el Query Tool conectado a la base Lumora.
-- La extension debe estar instalada en el servidor PostgreSQL antes de este paso.

CREATE EXTENSION IF NOT EXISTS vector;

SELECT current_database() AS base_activa,
       current_user AS usuario_activo,
       extversion AS version_pgvector
FROM pg_extension
WHERE extname = 'vector';

-- Las tablas y los indices se crean despues con:
--   python scripts\setup_postgres.py
-- Alembic conserva el historial y evita duplicar cambios manualmente.
