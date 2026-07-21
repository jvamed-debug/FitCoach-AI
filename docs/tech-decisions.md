# Tech Decisions — FitCoach AI
Versão: 1.0 | Data: 2026-04-30 | Fase: 05

---

## Decisões Confirmadas pelo Usuário

### 1. Stack Geral — Aprovada

| Camada | Tecnologia | Versão |
|--------|-----------|--------|
| Backend | Python + FastAPI | 3.11 / 0.111 |
| Validação | Pydantic v2 | 2.7 |
| ORM | SQLAlchemy async + Alembic | 2.0 |
| Agendador | APScheduler (embutido no FastAPI) | 3.10 |
| Geração PDF | WeasyPrint | latest |
| Email | Resend (API HTTP) | latest |
| Frontend | Next.js 14 App Router + TypeScript | 14.2 |
| UI | Tailwind CSS + shadcn/ui | 3.4 |
| Gráficos | Recharts | 2.x |
| Estado global | Zustand | 4.x |
| Forms | React Hook Form + Zod | 7.x / 3.x |
| PWA | next-pwa | latest |
| Banco | Supabase PostgreSQL + pgcrypto + RLS | — |
| Auth | Supabase Auth (JWT) + OAuth 2.0 | — |
| IA Principal | Claude API — claude-sonnet-4-6 | — |
| IA Fallback | OpenAI GPT-4o | — |
| Pagamentos | Stripe (assinatura recorrente) | — |
| Backend deploy | Railway | — |
| Frontend deploy | Vercel | — |
| CI/CD | GitHub Actions | — |
| Storage | Supabase Storage (PDFs) | — |

---

### 2. Apple Health no MVP — Aceito (iOS Shortcut)

**Estratégia:** sem app nativo iOS, integração via iOS Shortcut automatizado.

**Fluxo de implementação:**
1. FitCoach gera um iOS Shortcut personalizado por cliente (URL de webhook único)
2. Cliente instala o Shortcut em 1 clique (link de instalação gerado no app)
3. Shortcut é configurado como automação diária (ex: 7h da manhã)
4. Shortcut coleta via HealthKit: FC de repouso, horas de sono, qualidade do sono, atividades do dia anterior
5. Shortcut envia JSON para o webhook `/api/health/apple-health/{client_token}`
6. Backend processa e armazena em `daily_metrics`
7. Agente IA considera esses dados na análise de recuperação

**Limitações aceitas:**
- Depende do cliente instalar o Shortcut manualmente (1x)
- Shortcut precisa de iOS 15+ e Shortcuts app instalado
- Dados chegam uma vez por dia (não tempo real)
- Usuários Android: apenas Strava/Garmin/TrainingPeaks

---

### 3. Garmin no MVP — Aceito via Relay Bidirecional (Strava + TrainingPeaks)

**Decisão:** Integração bidirecional via relay, sem a API oficial Garmin.

#### Fluxo INBOUND (Garmin → FitCoach)
```
Garmin Device → Garmin Connect → auto-sync Strava → Strava Webhook → FitCoach
```
- Cliente conecta Garmin Connect ao Strava (configuração única pelo cliente)
- Quando treino é concluído no Garmin e sincronizado, Strava notifica FitCoach via webhook
- FitCoach processa atividade normalmente (mesma pipeline do Strava)

#### Fluxo OUTBOUND (FitCoach → Garmin)
```
FitCoach → TrainingPeaks API → TrainingPeaks → Garmin Connect sync → Garmin Device
```
- TrainingPeaks tem integração nativa bidirecional com Garmin Connect
- Treino estruturado criado no TrainingPeaks aparece no dispositivo Garmin automaticamente
- Requer que o cliente conecte TrainingPeaks ao Garmin (1x na configuração)

**Pré-condição:** cliente deve ter conta TrainingPeaks para receber treinos no Garmin.
Se não tiver TrainingPeaks: treino é enviado apenas via Strava (planejado), sem garantia de aparecer no dispositivo.

**Pós-MVP:** assim que API Garmin for aprovada, substituir relay por integração direta (Health API).

---

## Decisões Técnicas Complementares

### Modelo de IA
- **Modelo padrão:** claude-sonnet-4-6 (custo/performance ideal para geração diária)
- **Fallback automático:** GPT-4o quando Claude indisponível (NFR-14)
- **Temperatura:** 0.3 (determinístico para prescrições médicas)
- **Max tokens:** 2048 por plano (suficiente para plano estruturado em JSON)

### Scheduler (Job Diário)
- APScheduler no processo FastAPI para MVP
- Job executa às **06:00 BRT** diariamente
- Processamento paralelo por cliente (asyncio gather com limite de concorrência: 10)
- Timeout por cliente: 60 segundos
- Em falha: retry 1x após 5 minutos, depois log de erro e continua próximo cliente
- Migrar para Celery + Redis pós-MVP (> 50 clientes)

### Criptografia de Dados de Saúde (LGPD)
- Campos sensíveis criptografados com `pgp_sym_encrypt` (pgcrypto)
- Campos afetados: `anamnese`, `access_token`, `refresh_token`, `hrv_ms`, `resting_hr`
- Chave de criptografia via variável de ambiente `DB_ENCRYPTION_KEY` (nunca no código)
- RLS do Supabase como segunda camada de isolamento por `user_id`

### Webhooks de Plataformas Externas
- Strava: Subscription API (POST /push_subscriptions) — eventos: `activity.create`, `activity.update`
- TrainingPeaks: Polling a cada 15min como fallback (não tem webhook público)
- Apple Health: Webhook próprio (POST /api/health/apple-health/{token})
- Endpoint de webhook protegido por `X-Strava-Signature` (HMAC-SHA256)
