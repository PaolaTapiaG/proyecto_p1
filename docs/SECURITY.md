# Seguridad, Supabase y RLS

## Secretos y autenticacion

- La clave publicable de Supabase puede exponerse al cliente solo cuando RLS esta activo; `service_role` nunca puede incluirse en Vite.
- `SUPABASE_SERVICE_ROLE_KEY` y `SUPABASE_JWT_SECRET` pertenecen exclusivamente al backend.
- `ALLOW_DEV_AUTH=true` habilita cabeceras de desarrollo y debe ser `false` fuera del entorno local.
- `ALLOW_LOCAL_AUTH` habilita registro por correo propio. `LOCAL_JWT_SECRET` debe ser largo, aleatorio y distinto en cada entorno; las contrasenas se guardan con PBKDF2-SHA256 y sal aleatoria.
- Google OAuth se inicia desde Supabase. Configura `VITE_SUPABASE_URL`, `VITE_SUPABASE_PUBLISHABLE_KEY`, el proveedor Google y las URL de redireccion autorizadas.
- La implementacion valida JWT HS256. Si Supabase usa claves asimetricas, se debe validar contra JWKS con cache y rotacion.
- Ollama se configura para `127.0.0.1`; no debe publicarse sin autenticacion y una red protegida.

## Autorizacion por capas

FastAPI comprueba propiedad, autoria y visibilidad antes de leer o modificar recursos. RLS replica esos limites para accesos directos a Supabase. El backend no debe depender solo de RLS porque `service_role` la omite.

`supabase/rls.sql` documenta y aplica estas reglas:

- Cada usuario solo lee o actualiza `usuarios` con su propio UUID.
- Cada usuario administra sus filas de `personas_usuario`.
- `bots` publicos son visibles; bots privados y sus memorias canonicas solo para su autor.
- `conversaciones`, `mensajes` y memorias personales se restringen al propietario.
- Los favoritos solo pueden crearse o eliminarse por su usuario y solo apuntan a bots visibles.
- Los comentarios de mejora y errores son privados para el usuario; el backend administrativo cambia su estado.
- Desde el cliente solo se insertan mensajes con emisor `user`.
- Consumo, suscripciones y moderacion solo son visibles para el usuario afectado.
- La auditoria administrativa requiere `is_admin=true`.

Antes de aplicar RLS, `usuarios.supabase_user_id` debe contener `auth.users.id` como texto; el UUID interno `id_usuario` puede ser distinto. Ejecuta las sentencias despues de la migracion Alembic y pruebalo con al menos dos usuarios.

## Storage

`supabase/storage.sql` crea el bucket privado `bot-assets`. Cada objeto debe guardarse bajo `<auth.uid()>/<archivo>`; las politicas comparan el primer segmento con `auth.uid()`. Para mostrar archivos privados, el backend debe emitir URL firmadas de corta duracion.

La ruta local `/media` existe solo para desarrollo. Valida firma PNG/JPEG/WebP, limita cada archivo a 6 MB, genera nombres aleatorios y separa carpetas por usuario, pero no ofrece control de lectura privado. No debe exponerse como almacenamiento de produccion.

La investigacion externa usa endpoints fijos de Wikipedia/MediaWiki y nunca descarga una URL proporcionada por el usuario; esto reduce el riesgo SSRF. Los resultados siguen siendo referencia no confiable y no pueden modificar instrucciones del sistema.

## Datos y memoria

- PostgreSQL debe exigir TLS fuera de la red local.
- No se deben registrar contrasenas, JWT, prompts sensibles ni memoria completa en logs.
- Los embeddings pueden filtrar informacion del texto original y requieren las mismas reglas de acceso y borrado.
- Copias de seguridad, conversaciones y memorias necesitan politicas de retencion y eliminacion por usuario.
- Los indices vectoriales no reemplazan filtros de propiedad; la consulta aplica primero bot y usuario.

## Contenido adulto

- La cuenta debe confirmar mayoria de edad antes de poder habilitar el modo +18.
- Cada conversacion mantiene su propio interruptor y comienza desactivada; confirmar la edad no lo enciende automaticamente.
- Desactivar la confirmacion adulta apaga el modo +18 en todas las conversaciones del usuario.
- Una conversacion habilitada no concede iniciativa permanente: el mensaje actual debe solicitar expresamente contenido sexual adulto o violencia grafica.
- La moderacion bloquea siempre contenido sexual que mencione menores o edades inferiores a 18 anos.
- Estas comprobaciones ocurren en FastAPI y no se delegan al frontend ni a RLS.

## Antes de produccion

1. Desactiva autenticacion de desarrollo y `AUTO_CREATE_TABLES`; decide si el acceso por correo sera local o exclusivamente Supabase.
2. Rota secretos y usa el gestor de secretos del entorno.
3. Agrega limites por usuario, IP y conversacion.
4. Prueba RLS con lecturas y escrituras negativas.
5. Audita acciones administrativas y accesos a contenido privado.
6. Protege Redis y Ollama en una red privada.
