-- Ejecutar una sola vez en el SQL Editor de Supabase (mismo proyecto del dashboard).
-- Guarda quien genero cada CSV de factura, para trazabilidad.

create table if not exists public.facturas_generadas (
    id bigint generated always as identity primary key,
    usuario_email text not null,
    proveedor text,
    numero_factura text,
    fecha_factura text,
    sede text,
    total_lineas integer,
    lineas_sin_match integer,
    created_at timestamptz not null default now()
);

alter table public.facturas_generadas enable row level security;

-- La app escribe con la service_role key (que salta RLS), estas policies son
-- por si en el futuro se consulta esta tabla directo desde el navegador.
create policy "usuarios autenticados pueden insertar su propio registro"
on public.facturas_generadas for insert
to authenticated
with check (auth.email() = usuario_email);

create policy "usuarios autenticados pueden leer el historial"
on public.facturas_generadas for select
to authenticated
using (true);
