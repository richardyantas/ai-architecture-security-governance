# Preparar AWS y Supabase: paso a paso

Guía armada leyendo Terraform, los workflows y los scripts del repo. **No fue ejecutada ni probada en una cuenta real.** Los pasos marcados con ⚠️ crean recursos o cuestan dinero: confirma cada uno antes de ejecutarlo.

## Antes de empezar

- **Herramientas:** AWS CLI v2, Terraform ≥ 1.10 (el workflow usa 1.10.5), Docker, Python 3.12 y `gh` (opcional).
- **Cuentas:** AWS (con un usuario de administración **solo para el bootstrap**), Supabase, GitHub y, si lo usas, OpenAI.
- **Modo mock:** el taller entero funciona en mock sin AWS ni Supabase. Esto solo hace falta para las partes reales (V02 con pgvector, V05 y V14).

## Parte A · Supabase

1. **Crear el proyecto** en supabase.com. Guarda la contraseña de la base de datos y el **project ref** (el `<ref>` de `https://<ref>.supabase.co`).
2. **Obtener la cadena de conexión** en *Project Settings → Database → Connection string*:
   - **Migraciones y scripts:** session pooler o conexión directa, puerto **5432**.
   - **Lambda:** transaction pooler, puerto **6543**.
3. **Aplicar migraciones y datos** (usa 5432):
   ```bash
   export DATABASE_URL='postgresql://...:5432/postgres'
   .venv/bin/python scripts/apply_migrations.py --seed
   ```
   Ejecuta las 5 migraciones de `supabase/migrations/` (equipos, historial con pgvector, incidentes, acciones/auditoría y RLS) más `supabase/seed.sql`.
4. **Ingerir los embeddings** con el mismo `DATABASE_URL`, en el modo que vayas a usar:
   ```bash
   STORE_MODE=supabase EMBEDDING_MODE=mock .venv/bin/python scripts/ingest.py
   ```
   `EMBEDDING_MODE` debe coincidir con el de Terraform más adelante.
5. **Crear los 3 usuarios demo** desde tu máquina:
   ```bash
   SUPABASE_URL=https://<ref>.supabase.co SUPABASE_SERVICE_ROLE_KEY=... DEMO_PASSWORD='...' \
     .venv/bin/python scripts/create_demo_users.py
   ```
   La `service_role` key es una credencial raíz. No la subas al repo, a CI ni a la app.
6. **Anotar los datos de JWT** para la app:
   - `JWT_ISSUER = https://<ref>.supabase.co/auth/v1`
   - Si tu proyecto usa llaves asimétricas: `JWT_JWKS_URL = https://<ref>.supabase.co/auth/v1/.well-known/jwks.json`. Si usa el *JWT Secret* legacy (HS256), copia ese secreto.

## Parte B · AWS

### B1. Credenciales locales
```bash
aws configure          # o aws sso login
aws sts get-caller-identity   # confirma que es la cuenta correcta
```

### B2. Bootstrap (se aplica una sola vez, a mano) ⚠️
```bash
cd infrastructure/terraform/bootstrap
cp terraform.tfvars.example terraform.tfvars   # pon tu usuario/repo de GitHub en github_repo
terraform init && terraform plan
terraform apply                                # solo tras revisar el plan
```
Crea el bucket S3 para el estado de Terraform y la confianza OIDC de GitHub con 4 roles: `plan`, `apply`, `build` y `deploy`. Si tu cuenta ya tiene el proveedor OIDC de GitHub, descomenta `create_github_oidc_provider = false`. Anota los *outputs*, en especial `state_bucket` y `account_id`.

### B3. Variables y entornos en GitHub
En *Settings → Secrets and variables → Actions → Variables* añade: `AWS_REGION`, `AWS_ACCOUNT_ID`, `TF_STATE_BUCKET`, `JWT_ISSUER` y, si aplica, `JWT_JWKS_URL`.

En *Settings → Environments* crea `workshop-infra` y `workshop-deploy`, y en ambos activa **Required reviewers**. Ese es el control humano del repo; sin ellos el apply y el deploy no quedan protegidos.

### B4. Estado remoto del entorno
```bash
cd ../environments/workshop
cp backend.hcl.example backend.hcl       # pon bucket = maintenance-ai-tfstate-<ACCOUNT_ID>
cp terraform.tfvars.example terraform.tfvars
terraform init -backend-config=backend.hcl
```

### B5. Imagen inicial y primer apply ⚠️
`lambda_image_uri` exige una imagen que ya exista en ECR, pero ECR lo crea esta misma pila. El código no documenta cómo se resuelve; este es un camino **sin probar**:
1. `terraform apply -target=module.ecr` para crear solo el repositorio.
2. `docker build -f Dockerfile.lambda ...`, `docker push` y copiar el *digest* (`sha256:...`) a `lambda_image_uri` en `terraform.tfvars`.
3. `terraform plan` y, tras revisarlo, `terraform apply` completo.

En `terraform.tfvars` deja `llm_mode = "mock"` y `embedding_mode = "mock"` hasta tener la llave de OpenAI. `enable_ec2 = true` crea una instancia `t3.small` que cuesta dinero mientras exista; ponlo en `false` para evitarlo.

### B6. Guardar los secretos en Secrets Manager
Terraform solo crea el contenedor vacío; los valores los pones tú, sin teclearlos en el historial del shell:
```bash
export DATABASE_URL='postgresql://...:6543/postgres'   # transaction pooler para la app
export JWT_SECRET='...'
# export OPENAI_API_KEY='...'   # opcional
.venv/bin/python scripts/seed_app_secret.py --secret-id maintenance-ai/workshop/app --region us-east-1
```
`MCP_SHARED_SECRET` se genera solo si no lo defines.

### B7. Variables finales en GitHub y despliegue
Con los *outputs* de Terraform añade en GitHub: `EC2_INSTANCE_ID`, `API_URL` y el secreto `API_KEY` (la clave del usage plan de API Gateway). Luego ejecuta el workflow **Deploy** a mano (`workflow_dispatch`, entorno `workshop`). Construye la imagen, la escanea, espera a un revisor, la despliega por digest y hace *rollback* si el smoke test falla.

### B8. Verificar
```bash
.venv/bin/python scripts/smoke_test.py --base-url <API_URL> --api-key <KEY> \
  --secret-id maintenance-ai/workshop/app --route /diagnose/quick
```
Comprueba `/health`, que sin token dé 401, un diagnóstico de P-204 con citas y que el acceso entre plantas dé 403.

## Al terminar el taller ⚠️

Si no quieres seguir pagando, destruye lo creado: `terraform destroy` en `environments/workshop` y luego, si ya no lo necesitas, en `bootstrap`. Vacía antes el bucket de estado y confirma siempre el plan de destrucción.
