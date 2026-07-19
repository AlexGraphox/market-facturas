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

-- inventario_stock (la que ya sincroniza OficinaPro) solo trae stock, no
-- precio/iva/costo. Esta tabla propia guarda esos 3 campos, poblada por
-- upload manual del mismo CSV que ya exportas de OficinaPro.
create table if not exists public.inventario_precios (
    codigo text primary key,
    nombre text not null,
    precio numeric not null default 0,
    iva numeric not null default 0,
    costo numeric not null default 0,
    codigo_barra text,
    updated_at timestamptz not null default now()
);

create index if not exists idx_inventario_precios_barra on public.inventario_precios (codigo_barra);

alter table public.inventario_precios enable row level security;

create policy "usuarios autenticados pueden leer precios"
on public.inventario_precios for select
to authenticated
using (true);

-- Cada vez que un cajero corrige a mano el producto que sugirio la IA, se
-- guarda aqui (proveedor + su codigo de producto -> nuestro codigo interno).
-- La proxima factura del mismo proveedor usa esto primero, antes de adivinar
-- de nuevo por parecido de texto.
create table if not exists public.aprendizaje_matches (
    proveedor text not null,
    codigo_proveedor text not null,
    codigo_producto text not null,
    usuario_email text,
    updated_at timestamptz not null default now(),
    primary key (proveedor, codigo_proveedor)
);

alter table public.aprendizaje_matches enable row level security;

create policy "usuarios autenticados pueden usar el aprendizaje"
on public.aprendizaje_matches for all
to authenticated
using (true)
with check (true);

-- Lista de correos con permiso para crearse su propia clave la primera vez
-- que entren. Sin policies (RLS activo, cero policies) = solo la app con la
-- service_role key puede leerla; nadie puede verla desde el navegador.
-- Para agregar a alguien: insertar una fila aqui (Table Editor de Supabase).
-- Para quitarle el acceso a alguien que YA tiene cuenta creada, esto no
-- alcanza -- hay que eliminarlo en Authentication > Users.
create table if not exists public.usuarios_autorizados (
    email text primary key,
    created_at timestamptz not null default now()
);

alter table public.usuarios_autorizados enable row level security;

insert into public.usuarios_autorizados (email) values
    ('mafestevez@gmail.com'),
    ('deicymerino146@gmail.com'),
    ('mutto30mutto@gmail.com'),
    ('market2towers@gmail.com'),
    ('maca.jaimes@gmail.com'),  -- REVISAR: llegó como "maca.jaim,es@gmail.com", corregido asumiendo typo
    ('ana.troncoso.bastidas@gmail.com'),
    ('amosquera2409@gmail.com'),
    ('luismariovilladiegosandoval@gmail.com'),
    ('alejandromartinezrizo2704@gmail.com'),
    ('andrespipepes@gmail.com')
on conflict (email) do nothing;
