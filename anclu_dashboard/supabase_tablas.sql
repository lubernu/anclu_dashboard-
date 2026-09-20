-- Tablas adicionales que la app espera en Supabase (ademas de public.ventas_anclu ya subida).
-- Las sube via: Table Editor > Import data into table, usando los CSV/parquet locales.

-- Rp / actividades Claro (desde C:\Users\lubernu\Practicas\SIG\ventas_anclu_rp.csv)
create table if not exists public.ventas_anclu_rp (
  id bigint generated always as identity primary key,
  "DISTRIBUIDOR" text,
  "PRODUCTO" text,
  "CO_ID" text,
  "ACTIVACION" timestamp,
  "DESCRIPCION" text
);
create index if not exists idx_rp_activacion on public.ventas_anclu_rp ("ACTIVACION");

-- Metas Claro (forma "achatada": FECHA, CODIGO, META_DE, Valor — igual a como la usa la app)
create table if not exists public.metas_claro (
  id bigint generated always as identity primary key,
  "FECHA" timestamp,
  "CODIGO" text,
  "META_DE" text,
  "Valor" numeric
);
create index if not exists idx_metas_fec on public.metas_claro ("FECHA");

-- Puntos (CODIGO con nombre limpio para mostrar en la pestana Claro)
create table if not exists public.puntos (
  id bigint generated always as identity primary key,
  "CODIGO" text,
  "NOMBREPUNTO" text
);

-- Calendario con dias laborales (Date + "Dia Laboral"; desde Calendario.parquet)
create table if not exists public.calendario (
  id bigint generated always as identity primary key,
  "Date" timestamp,
  "Dia Laboral" numeric
);
create index if not exists idx_cal_date on public.calendario ("Date");