-- Crear primero un bucket privado llamado `bot-assets` desde Supabase.
-- Ruta esperada: <auth.uid()>/<nombre-del-archivo>.

create policy "bot_assets_select_own"
on storage.objects for select
using (
    bucket_id = 'bot-assets'
    and (storage.foldername(name))[1] = auth.uid()::text
);

create policy "bot_assets_insert_own"
on storage.objects for insert
with check (
    bucket_id = 'bot-assets'
    and (storage.foldername(name))[1] = auth.uid()::text
);

create policy "bot_assets_update_own"
on storage.objects for update
using (
    bucket_id = 'bot-assets'
    and (storage.foldername(name))[1] = auth.uid()::text
) with check (
    bucket_id = 'bot-assets'
    and (storage.foldername(name))[1] = auth.uid()::text
);

create policy "bot_assets_delete_own"
on storage.objects for delete
using (
    bucket_id = 'bot-assets'
    and (storage.foldername(name))[1] = auth.uid()::text
);
