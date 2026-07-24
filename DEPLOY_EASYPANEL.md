# Deploy do FitCoach AI no Hostinger/Easypanel

O backend (FastAPI) é publicado como um **App Service** do Easypanel, buildado a
partir do `Dockerfile` na **raiz** do repositório (o Easypanel procura o
Dockerfile na raiz do contexto por padrão; o Dockerfile usa caminhos `backend/...`).
O banco é o **Supabase** (Postgres gerenciado, externo) — não é preciso volume
persistente no Easypanel para dados.

> ⚠️ **Uma única réplica.** O APScheduler roda dentro do processo FastAPI (job
> diário, relatório semanal, lembrete de métricas). Com mais de uma réplica os
> jobs rodariam duplicados. Mantenha `1 replica` até migrar o scheduler para um
> worker dedicado (Celery/Redis).

## 0. Pré-requisitos

- Uma VPS Hostinger com **Easypanel** instalado (template 1-clique da Hostinger).
- O banco Supabase com as migrations `001` e `002` já aplicadas.
- As credenciais do Supabase em mãos (URL, anon key, service_role, JWT secret,
  connection string).

## 1. Conectar o GitHub

Conecte o Easypanel ao repositório privado `jvamed-debug/FitCoach-AI`. Restrinja a
credencial ao repositório:

- Metadata: leitura;
- Contents: leitura;
- Webhooks: leitura/escrita apenas se o Auto Deploy for habilitado.

Nunca coloque chave de provedor ou segredo no repositório, no Dockerfile ou em
argumento de build.

## 2. Criar o App Service

1. Crie ou abra um projeto no Easypanel.
2. Adicione um **App Service**.
3. Fonte: repositório `jvamed-debug/FitCoach-AI`, branch `main`.
4. Builder: **Dockerfile**.
5. **Dockerfile Path:** deixe o padrão (`Dockerfile`) — ele está na raiz do repo.
6. Réplicas: **1**.

Não use Buildpacks/Nixpacks para este serviço.

## 3. Configurar o ambiente (aba Environment)

Obrigatórias — sem estas o app **não sobe**:

```env
SUPABASE_URL=https://yjyemvvkkwuelyusdgjq.supabase.co
SUPABASE_ANON_KEY=cole_a_anon_key
SUPABASE_SERVICE_KEY=cole_a_service_role_key
SUPABASE_JWT_SECRET=cole_a_legacy_jwt_secret
DATABASE_URL=postgresql+asyncpg://postgres.<proj>:<senha>@<host>.pooler.supabase.com:5432/postgres
DB_ENCRYPTION_KEY=gere_32_chars
SECRET_KEY=gere_outro_32_chars
APP_ENV=production
```

Recomendadas para a aplicação ser útil:

```env
ANTHROPIC_API_KEY=cole_sua_chave
FRONTEND_URL=https://app.seudominio.com   # define o CORS; ver passo 6
BACKEND_URL=https://api.seudominio.com
```

Opcionais (ative a integração correspondente quando quiser): `OPENAI_API_KEY`,
`RESEND_API_KEY` + `FROM_EMAIL`, `STRAVA_CLIENT_ID`/`STRAVA_CLIENT_SECRET`/
`STRAVA_WEBHOOK_VERIFY_TOKEN`, `STRIPE_SECRET_KEY`/`STRIPE_WEBHOOK_SECRET`/
`STRIPE_PRICE_*`, `VAPID_PRIVATE_KEY`/`VAPID_PUBLIC_KEY`, `SENTRY_DSN`,
`TP_CLIENT_ID`/`TP_CLIENT_SECRET`.

Gere os dois segredos fora do histórico do shell:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Não reutilize o mesmo valor em `DB_ENCRYPTION_KEY` e `SECRET_KEY`.
Lembre de trocar `postgresql://` por **`postgresql+asyncpg://`** no `DATABASE_URL`.

## 4. Domínio, proxy e HTTPS (aba Domains & Proxy)

1. Aponte o DNS do domínio (ex.: `api.seudominio.com`) para o IP da VPS.
2. Adicione o domínio ao serviço.
3. **Proxy Port:** `8000`.
4. Marque como domínio principal.
5. Habilite o certificado HTTPS (Let's Encrypt).

Não publique a porta `8000` direto no host quando o tráfego passa pelo proxy.

## 5. Primeiro deploy e validação

O Easypanel builda e sobe. O health check da aplicação é `/health`.

```bash
curl -fsS https://api.seudominio.com/health
# esperado: {"status":"ok","env":"production"}
```

Se o build falhar, o erro mais provável é dependência de sistema do WeasyPrint —
o Dockerfile já instala Pango/Cairo/gdk-pixbuf via apt. Confira os logs de build.

## 6. Frontend (Next.js)

Duas opções:

- **Vercel** (zero-config para Next.js): defina `NEXT_PUBLIC_API_URL` com a URL do
  backend acima, e `NEXT_PUBLIC_SUPABASE_URL` / `NEXT_PUBLIC_SUPABASE_ANON_KEY`.
- **Segundo App Service no Easypanel**: builder Nixpacks (autodetecta Next.js) ou
  um Dockerfile de frontend; expor a porta do Next (`3000`).

Depois que o frontend tiver domínio, volte ao passo 3 e ajuste `FRONTEND_URL` no
backend para a URL do frontend (o CORS usa esse valor), e redeploy.

## 7. Auto Deploy

Ative **Auto Deploy** só depois do primeiro deploy aprovado, acompanhando a branch
`main`. Mantenha o CI obrigatório antes de novos merges — o webhook do Easypanel
dispara um build a cada push.

## Referências

- [Easypanel App Service](https://easypanel.io/docs/services/app)
- [Easypanel Builders](https://easypanel.io/docs/builders)
