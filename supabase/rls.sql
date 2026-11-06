-- Ejecutar despues de `alembic upgrade head` si PostgreSQL esta alojado en Supabase.
-- El backend usa service_role; esa clave nunca debe llegar al frontend React.

create extension if not exists vector;

alter table public.usuarios enable row level security;
alter table public.personas_usuario enable row level security;
alter table public.bots enable row level security;
alter table public.conversaciones enable row level security;
alter table public.mensajes enable row level security;
alter table public.memorias_bot enable row level security;
alter table public.moderation_events enable row level security;
alter table public.usage_records enable row level security;
alter table public.subscriptions enable row level security;
alter table public.admin_audit_logs enable row level security;
alter table public.favoritos_bot enable row level security;
alter table public.comentarios_usuario enable row level security;

create policy "usuarios_select_self" on public.usuarios
for select using (supabase_user_id = auth.uid()::text);

create policy "usuarios_update_self" on public.usuarios
for update using (supabase_user_id = auth.uid()::text)
with check (supabase_user_id = auth.uid()::text and is_admin = false);

create policy "personas_usuario_owned" on public.personas_usuario
for all using (
    id_usuario in (
        select id_usuario from public.usuarios where supabase_user_id = auth.uid()::text
    )
) with check (
    id_usuario in (
        select id_usuario from public.usuarios where supabase_user_id = auth.uid()::text
    )
);

create policy "bots_select_visible" on public.bots
for select using (
    visibilidad = 'public'
    or id_creador in (
        select id_usuario from public.usuarios where supabase_user_id = auth.uid()::text
    )
);

create policy "bots_insert_owned" on public.bots
for insert with check (
    id_creador in (
        select id_usuario from public.usuarios where supabase_user_id = auth.uid()::text
    )
);

create policy "bots_update_owned" on public.bots
for update using (
    id_creador in (
        select id_usuario from public.usuarios where supabase_user_id = auth.uid()::text
    )
) with check (
    id_creador in (
        select id_usuario from public.usuarios where supabase_user_id = auth.uid()::text
    )
);

create policy "bots_delete_owned" on public.bots
for delete using (
    id_creador in (
        select id_usuario from public.usuarios where supabase_user_id = auth.uid()::text
    )
);

create policy "conversaciones_select_owned" on public.conversaciones
for select using (
    id_usuario in (
        select id_usuario from public.usuarios where supabase_user_id = auth.uid()::text
    )
);

create policy "conversaciones_insert_owned_visible_bot" on public.conversaciones
for insert with check (
    id_usuario in (
        select id_usuario from public.usuarios where supabase_user_id = auth.uid()::text
    )
    and id_bot in (
        select b.id_bot
        from public.bots b
        left join public.usuarios creator on creator.id_usuario = b.id_creador
        where b.visibilidad = 'public' or creator.supabase_user_id = auth.uid()::text
    )
    and (
        id_persona_usuario is null
        or id_persona_usuario in (
            select p.id_persona
            from public.personas_usuario p
            join public.usuarios u on u.id_usuario = p.id_usuario
            where u.supabase_user_id = auth.uid()::text
        )
    )
);

create policy "conversaciones_update_owned" on public.conversaciones
for update using (
    id_usuario in (
        select id_usuario from public.usuarios where supabase_user_id = auth.uid()::text
    )
) with check (
    id_usuario in (
        select id_usuario from public.usuarios where supabase_user_id = auth.uid()::text
    )
);

create policy "conversaciones_delete_owned" on public.conversaciones
for delete using (
    id_usuario in (
        select id_usuario from public.usuarios where supabase_user_id = auth.uid()::text
    )
);

create policy "mensajes_select_owned_conversation" on public.mensajes
for select using (
    id_conversacion in (
        select c.id_conversacion
        from public.conversaciones c
        join public.usuarios u on u.id_usuario = c.id_usuario
        where u.supabase_user_id = auth.uid()::text
    )
);

create policy "mensajes_insert_user_only" on public.mensajes
for insert with check (
    remitente = 'user'
    and id_conversacion in (
        select c.id_conversacion
        from public.conversaciones c
        join public.usuarios u on u.id_usuario = c.id_usuario
        where u.supabase_user_id = auth.uid()::text
    )
);

create policy "memorias_select_scoped" on public.memorias_bot
for select using (
    id_usuario in (
        select id_usuario from public.usuarios where supabase_user_id = auth.uid()::text
    )
    or (
        id_usuario is null
        and id_bot in (
            select id_bot from public.bots
            where id_creador in (
                select id_usuario from public.usuarios
                where supabase_user_id = auth.uid()::text
            )
        )
    )
);

create policy "memorias_insert_bot_author" on public.memorias_bot
for insert with check (
    id_usuario is null
    and id_bot in (
        select id_bot from public.bots
        where id_creador in (
            select id_usuario from public.usuarios
            where supabase_user_id = auth.uid()::text
        )
    )
);

create policy "memorias_insert_personal" on public.memorias_bot
for insert with check (
    id_usuario in (
        select id_usuario from public.usuarios where supabase_user_id = auth.uid()::text
    )
    and (
        id_conversacion is null
        or id_conversacion in (
            select c.id_conversacion
            from public.conversaciones c
            join public.usuarios u on u.id_usuario = c.id_usuario
            where u.supabase_user_id = auth.uid()::text
        )
    )
);

create policy "memorias_update_personal" on public.memorias_bot
for update using (
    id_usuario in (
        select id_usuario from public.usuarios where supabase_user_id = auth.uid()::text
    )
) with check (
    id_usuario in (
        select id_usuario from public.usuarios where supabase_user_id = auth.uid()::text
    )
);

create policy "memorias_delete_personal" on public.memorias_bot
for delete using (
    id_usuario in (
        select id_usuario from public.usuarios where supabase_user_id = auth.uid()::text
    )
);

create policy "favoritos_owned" on public.favoritos_bot
for select using (
    id_usuario in (
        select id_usuario from public.usuarios where supabase_user_id = auth.uid()::text
    )
);

create policy "favoritos_insert_owned_visible_bot" on public.favoritos_bot
for insert with check (
    id_usuario in (
        select id_usuario from public.usuarios where supabase_user_id = auth.uid()::text
    )
    and id_bot in (
        select b.id_bot
        from public.bots b
        left join public.usuarios creator on creator.id_usuario = b.id_creador
        where b.visibilidad = 'public' or creator.supabase_user_id = auth.uid()::text
    )
);

create policy "favoritos_delete_owned" on public.favoritos_bot
for delete using (
    id_usuario in (
        select id_usuario from public.usuarios where supabase_user_id = auth.uid()::text
    )
);

create policy "comentarios_insert_owned" on public.comentarios_usuario
for insert with check (
    id_usuario in (
        select id_usuario from public.usuarios where supabase_user_id = auth.uid()::text
    )
);

create policy "comentarios_select_owned" on public.comentarios_usuario
for select using (
    id_usuario in (
        select id_usuario from public.usuarios where supabase_user_id = auth.uid()::text
    )
);

create policy "moderation_select_self" on public.moderation_events
for select using (
    user_id in (
        select id_usuario from public.usuarios where supabase_user_id = auth.uid()::text
    )
);

create policy "usage_select_self" on public.usage_records
for select using (
    user_id in (
        select id_usuario from public.usuarios where supabase_user_id = auth.uid()::text
    )
);

create policy "subscriptions_select_self" on public.subscriptions
for select using (
    user_id in (
        select id_usuario from public.usuarios where supabase_user_id = auth.uid()::text
    )
);

create policy "admin_audit_select_admin" on public.admin_audit_logs
for select using (
    exists (
        select 1 from public.usuarios
        where supabase_user_id = auth.uid()::text and is_admin = true
    )
);
