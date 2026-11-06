Son cuatro comandos que preparan los datos y la base. Se ejecutan en este orden, y el orden importa porque cada uno usa lo que dejó el anterior.

## 1. `.venv/bin/python scripts/generate_dataset.py`
Es la parte `.venv/bin/python` (el Python del entorno virtual del proyecto, con las dependencias instaladas) más el script que genera los **datos sintéticos**. Es determinista (semilla 42), así que siempre produce lo mismo.

Escribe estos archivos:
- `data/equipment/` con `equipment.json`, `plants.json` y `profiles.json` (Ana, Luis y Root).
- `data/history/failures.json`, el historial de fallas.
- `data/manuals/` y `data/procedures/`, con manuales y procedimientos.
- `data/sensors/readings.json`, las lecturas de sensores.
- `supabase/seed.sql`, el mismo contenido en SQL para cargarlo en la base.

Todo es ficticio y no hay datos reales de ningún cliente.

## 2. `&& .venv/bin/python scripts/generate_eval_cases.py`
El `&&` significa "ejecuta el segundo solo si el primero terminó bien". Este script genera `data/evaluations/golden.json`: los **25 casos golden** de la evaluación de V12. Va después porque se apoya en los datos del paso 1.

Los 10 casos adversariales ya están en `data/attacks/atk-*.json`.

## 3. `.venv/bin/python scripts/ingest.py`
Es la **ingesta para RAG**. Toma las fallas, manuales y procedimientos, los parte en fragmentos (*chunks*, conservando el `source_id`) y calcula un **embedding** (un vector de 1536 números) de cada uno. Luego los guarda en el almacén configurado en `.env`.

- Con `STORE_MODE=supabase` los guarda en Postgres con **pgvector**.
- Con `EMBEDDING_MODE=openai` el embedding se pide a la API de OpenAI y gasta crédito. Con `mock` se calcula localmente y no cuesta nada.
- Al final imprime algo como `ingested N chunks (store=…, embeddings=…)`.

Importante: la consulta debe usar el mismo modo de embeddings que la ingesta, o la búsqueda devuelve resultados sin sentido.

## 4. `DATABASE_URL=... .venv/bin/python scripts/apply_migrations.py --seed`
Este es el único que escribe el **esquema** de la base.
- `DATABASE_URL=...` antes del comando define esa variable solo para esa ejecución. Es la cadena de conexión a tu Postgres de Supabase.
- Ejecuta en orden los archivos de `supabase/migrations/`:
  - `0001`: plantas y equipos, y activa pgvector.
  - `0002`: las tablas de historial de fallas con vectores.
  - `0003`: incidentes y ejecuciones.
  - `0004`: acciones, aprobaciones y auditoría.
  - `0005`: seguridad a nivel de fila (RLS).
- `--seed` además carga `supabase/seed.sql`, o sea los datos del paso 1.
- Usa la conexión directa o el *session pooler* (puerto 5432), no el pooler transaccional (6543).

## El orden correcto
Los pasos 1 y 2 generan archivos locales y no tocan la nube. El paso 4 (migraciones) tiene que ir **antes** del 3, porque la ingesta guarda en tablas que las migraciones crean. Como tu mensaje los lista con la ingesta antes, la forma segura es 1 → 2 → 4 → 3. Ya hiciste la migración y la ingesta, así que lo único que podrías repetir es el paso 1 si quieres regenerar los datos, y tendrías que volver a ingestar.