# Sprint Plan — FitCoach AI
Versão: 1.0 | Data: 2026-04-30 | Fase: 08 — Planner

> **Contexto:** 1 desenvolvedor + Claude Code | Sprints de 10 dias úteis (2 semanas)
> **Estimativa total:** 12 sprints = 120 dias úteis (~6 meses)
> **Critério de "done" global:** código commitado, testes passando, funcionalidade verificada localmente

---

## Visão Geral dos Sprints

| Sprint | Período | Foco | Stories |
|--------|---------|------|---------|
| S01 | Dias 01–10 | Infraestrutura + Auth | US-001, US-002, US-004, US-005, US-006 |
| S02 | Dias 11–20 | Gestão de Clientes | US-007, US-008, US-009, US-010, US-011 |
| S03 | Dias 21–30 | Cálculo de Carga + Musculação | US-022, US-023 (parcial), strength CRUD |
| S04 | Dias 31–40 | Integração Strava | US-012 (Strava), US-018, US-021 (Strava) |
| S05 | Dias 41–55 | Agente IA Coach | US-013, US-014, US-015, US-017 |
| S06 | Dias 56–65 | Integrações TP + Garmin + Apple Health | US-019, US-020, US-021b |
| S07 | Dias 66–75 | Adaptação Pós-treino + Métricas | US-016, US-023 (completo), US-024 |
| S08 | Dias 76–85 | Job Diário + Dashboard Admin | US-026, US-027, US-028, US-029 |
| S09 | Dias 86–95 | App Cliente (PWA) + Feedback | US-025, US-030, US-031 |
| S10 | Dias 96–102 | Relatórios PDF | US-036, US-037, US-038 |
| S11 | Dias 103–113 | Assinaturas + Stripe | US-032, US-033, US-003 (CI/CD) |
| S12 | Dias 114–121 | QA, Performance, Deploy Final | NFRs, testes, produção |

---

## Sprint 01 — Infraestrutura e Auth
**Dias 01–10 | Objetivo: projeto rodando localmente com auth funcional**

### Tarefas

#### T01.1 — Repositório e Estrutura (US-001) `2d`
- [ ] Criar repositório Git com estrutura `/backend` + `/frontend`
- [ ] Configurar `.gitignore` (Python, Node, `.env`)
- [ ] Criar `README.md` raiz com instruções de setup
- [ ] Criar `docker-compose.yml` para desenvolvimento local
- **Done:** `git clone` + `docker-compose up` sobe sem erros

#### T01.2 — Backend: Setup FastAPI (US-001) `1d`
- [ ] Criar estrutura de pastas: `app/`, `routers/`, `services/`, `models/`, `utils/`
- [ ] `app/main.py` com CORS, lifespan e health check
- [ ] `app/config.py` com Pydantic Settings
- [ ] `app/database.py` com SQLAlchemy async engine
- [ ] `requirements.txt` completo
- [ ] `.env.example`
- **Done:** `uvicorn app.main:app --reload` responde 200 em `/health`

#### T01.3 — Banco de Dados Supabase (US-002) `2d`
- [ ] Criar projeto Supabase
- [ ] Executar `supabase/migrations/001_initial_schema.sql` (spec-v1: schema completo)
- [ ] Configurar `DATABASE_URL` no `.env`
- [ ] Testar conexão async com SQLAlchemy (`asyncpg`)
- [ ] Configurar Alembic: `alembic init`, `env.py`, primeira migration de baseline
- [ ] Habilitar RLS e criar policies básicas
- **Done:** `alembic upgrade head` sem erros; query de teste retorna resultado

#### T01.4 — Auth Admin: Login + JWT (US-004) `2d`
- [ ] Configurar Supabase Auth (email + senha)
- [ ] `routers/auth.py`: `POST /api/auth/admin/login`
- [ ] `POST /api/auth/refresh`
- [ ] `POST /api/auth/logout`
- [ ] `GET /api/auth/me`
- [ ] `dependencies.py`: `get_current_admin()` — extrai e valida JWT
- [ ] Middleware de role check: `admin` vs `athlete`
- **Done:** login retorna JWT; rota protegida retorna 401 sem token

#### T01.5 — Pré-requisitos Externos (paralelo, sem custo de dev) `0d`
- [ ] Criar conta Stripe → iniciar processo KYC/verificação de identidade
- [ ] Solicitar acesso à API TrainingPeaks (https://developers.trainingpeaks.com)
- **Done:** solicitações enviadas; aprovações chegam durante S02–S06

#### T01.6 — Auth Atleta: Login + Onboarding (US-005, US-006) `3d`
- [ ] `POST /api/auth/athlete/login`
- [ ] `dependencies.py`: `get_current_athlete()`
- [ ] `POST /api/lgpd/consent` — registra aceite com timestamp + IP
- [ ] `GET /api/lgpd/consent`
- [ ] Middleware LGPD: 403 se atleta não aceitou termos
- [ ] Modelo `lgpd_consents` no SQLAlchemy
- [ ] Frontend `/login` (admin e atleta)
- [ ] Frontend `/onboarding` step 1: aceitar LGPD (modal obrigatório)
- **Done:** atleta sem LGPD recebe 403; com LGPD aceito acessa dashboard vazio

#### T01.7 — Testes de Auth (NFR-16) `1d`
- [ ] `tests/test_auth.py`: login válido retorna JWT; token expirado retorna 401; role athlete bloqueada em /admin/*; LGPD middleware bloqueia sem consent
- **Done:** 4 cenários passando

---

## Sprint 02 — Gestão de Clientes
**Dias 11–20 | Objetivo: admin consegue cadastrar e gerenciar atletas**

### Tarefas

#### T02.1 — Cadastro de Atleta (US-008) `3d`
- [ ] Modelo SQLAlchemy `Athlete` completo
- [ ] `POST /api/admin/athletes` — validações do spec-enriched
- [ ] Criptografia da anamnese com `pgp_sym_encrypt` (pgcrypto)
- [ ] Envio de email de boas-vindas via Resend (template HTML)
- [ ] Geração de link de onboarding com token temporário (7 dias)
- [ ] Frontend `/admin/athletes/new` — formulário completo com validação Zod
- **Done:** atleta criado, email recebido com link, dados no banco

#### T02.2 — Anamnese Esportiva (US-009) `2d`
- [ ] `PUT /api/admin/athletes/{id}/anamnese` — requer senha do admin
- [ ] Descriptografia para leitura no backend (nunca no frontend)
- [ ] `GET /api/admin/athletes/{id}` retorna anamnese descriptografada
- [ ] Log de auditoria: `audit_logs` para acesso à anamnese
- [ ] Frontend: aba "Anamnese" no perfil do atleta com campos médicos
- **Done:** anamnese salva criptografada; admin lê com confirmação de senha; log criado

#### T02.3 — Disponibilidade e Objetivos (US-010) `1d`
- [ ] Campo `weekly_availability` (JSONB) + `goal` no atleta
- [ ] `PUT /api/admin/athletes/{id}` — atualiza disponibilidade e objetivos
- [ ] Frontend: seletor de dias por modalidade (checkboxes) + campo de objetivo
- **Done:** disponibilidade salva e retornada corretamente no GET

#### T02.4 — Lista de Atletas com Indicadores (US-011) `2d`
- [ ] `GET /api/admin/athletes` — com paginação, busca e filtros
- [ ] Query SQL com joins para TSB atual e último treino
- [ ] Lógica de `tsb_status`: good/moderate/alert/critical
- [ ] Badge de alerta: ≥ 3 dias sem treino
- [ ] Frontend `/admin/athletes` — tabela com cards, busca em tempo real, badges coloridos
- **Done:** lista renderiza em < 500ms com 20 atletas; badges corretos

#### T02.5 — Convite e Onboarding do Atleta `2d`
- [ ] Endpoint `GET /auth/onboarding?token=...` — valida token + redireciona
- [ ] `POST /api/auth/athlete/set-password` — define senha no primeiro acesso
- [ ] Frontend `/onboarding` steps 2–4: definir senha, completar perfil, conectar plataformas (tela de teaser)
- [ ] Flag `onboarding_complete = true` ao final
- **Done:** atleta clica no link, define senha, completa onboarding, acessa dashboard

---

## Sprint 03 — Cálculo de Carga + Musculação
**Dias 21–30 | Objetivo: CTL/ATL/TSB calculados; registro de musculação funcionando**

### Tarefas

#### T03.1 — Engine de Cálculo de Carga (US-022) `3d`
- [ ] `utils/calculations.py` — todas as funções implementadas:
  - `calculate_tss_cycling(duration, normalized_power, ftp)` → float
  - `calculate_tss_from_hr(duration, avg_hr, max_hr, resting_hr)` → float (TRIMP)
  - `calculate_strength_tss(duration_minutes, rpe)` → float
  - `calculate_ctl(previous_ctl, daily_tss, tc=42)` → float
  - `calculate_atl(previous_atl, daily_tss, tc=7)` → float
  - `calculate_tsb(ctl, atl)` → float
  - `calculate_training_load_series(tss_series)` → list[dict]
  - `calculate_intensity_zones_cycling(ftp)` → dict (7 zonas Coggan)
  - `calculate_hr_zones(max_hr, resting_hr)` → dict (5 zonas Karvonen)
- [ ] `tests/test_calculations.py` — cobertura ≥ 90% com valores de referência conhecidos
- **Done:** todos os testes passam; TSS de treino real (ex: 90min Z2) retorna valor coerente

#### T03.2 — Serviço de Carga no Banco (US-022) `2d`
- [ ] `services/training_load.py`:
  - `recalculate_athlete_load(db, athlete_id, days_back=90)` — upsert em `training_load`
  - `get_current_load(db, athlete_id)` → dict
  - `get_load_history(db, athlete_id, days=60)` → list
- [ ] `GET /api/workouts/load` — retorna current + history
- [ ] `GET /api/workouts/stats/weekly`
- **Done:** após inserir treinos manualmente no banco, CTL/ATL/TSB calculados corretamente

#### T03.3 — CRUD de Musculação (US-009 parcial, US-015 parcial) `3d`
- [ ] Modelos SQLAlchemy: `StrengthSession`, `StrengthExercise`
- [ ] `POST /api/strength` — com cálculo automático de TSS por força
- [ ] `GET /api/strength` — lista com paginação
- [ ] `GET /api/strength/{id}` — com exercícios
- [ ] `PUT /api/strength/{id}`
- [ ] `DELETE /api/strength/{id}`
- [ ] Frontend `/strength/new` — formulário com adição dinâmica de exercícios
- [ ] Frontend `/strength` — lista de sessões
- **Done:** sessão criada, TSS calculado, exercícios salvos e retornados corretamente

#### T03.4 — Métricas Diárias (EP-06 parcial) `2d`
- [ ] Modelo SQLAlchemy `DailyMetrics`
- [ ] `POST /api/metrics` — upsert por data
- [ ] `GET /api/metrics/today`
- [ ] `GET /api/metrics` — histórico com range de datas
- [ ] `GET /api/metrics/trends` — médias 7d e 30d
- [ ] Frontend `/metrics` — formulário com sliders 1–10 + campos numéricos
- **Done:** métricas do dia salvas; upsert funciona; trends calculados

---

## Sprint 04 — Integração Strava
**Dias 31–40 | Objetivo: Strava conectado, treinos importados e recebidos por webhook**

### Tarefas

#### T04.1 — OAuth Strava (US-012) `2d`
- [ ] Registrar app no Strava Developers (client_id + secret)
- [ ] `GET /api/auth/oauth/strava/authorize` — gera URL e redireciona
- [ ] `GET /api/auth/oauth/strava/callback` — troca code por tokens, criptografa e salva
- [ ] `DELETE /api/auth/oauth/strava` — desconecta, revoga tokens locais
- [ ] Modelo `PlatformConnection` com campos criptografados
- [ ] Frontend: tela de integrações em `/settings` com botão "Conectar Strava"
- **Done:** fluxo OAuth completo funciona; tokens salvos criptografados; status exibido no app

#### T04.2 — Cliente Strava API (US-018, US-021) `3d`
- [ ] `services/strava_service.py` — implementação completa:
  - `get_authorization_url(state)` → str
  - `exchange_code_for_tokens(code)` → dict
  - `refresh_access_token(refresh_token)` → dict
  - `get_athlete(access_token)` → dict
  - `get_activities(access_token, after, before, page)` → list
  - `get_activity_detail(access_token, activity_id)` → dict
  - `create_planned_workout(access_token, workout_data)` → dict
  - `parse_activity_to_workout(activity, athlete_id)` → dict (com cálculo de TSS)
  - `sync_recent_activities(db, athlete_id, access_token, days_back)` → list
- [ ] Rate limiter via headers `X-RateLimit-Usage`
- [ ] Retry com backoff exponencial (Tenacity, 3 tentativas)
- **Done:** `sync_recent_activities` importa últimos 7 dias sem duplicatas; TSS calculado

#### T04.3 — Webhook Strava (US-021) `2d`
- [ ] Instalar ngrok (ou cloudflared) para expor localhost em desenvolvimento — documentar em `docs/STRAVA_SETUP.md`
- [ ] `POST /api/webhooks/strava` — verificação HMAC + processamento de eventos
- [ ] `GET /api/webhooks/strava` — hub.challenge para subscription Strava
- [ ] Registrar subscription via `POST /push_subscriptions` com URL ngrok (dev) ou URL de produção
- [ ] Background task: ao receber evento, buscar detalhes e salvar workout
- [ ] Recalcular CTL/ATL/TSB do atleta após import
- [ ] Testar payload de atividade Garmin-relay (campos `device_watts: false`) — verificar TSS via TRIMP
- **Done:** treino feito no Strava aparece no banco em < 5min; atividade Garmin-relay processada corretamente

#### T04.4 — Sync Manual e Endpoint de Workouts `1d`
- [ ] `POST /api/workouts/sync/strava` — importa últimos N dias
- [ ] `GET /api/workouts` — lista com filtros
- [ ] `GET /api/workouts/{id}` — detalhes completos
- [ ] Frontend `/workouts` — lista de treinos com ícones por tipo
- **Done:** sync manual funciona; lista renderiza corretamente

#### T04.5 — Token Refresh Automático `2d`
- [ ] `get_valid_access_token(db, connection)` — verifica expiração + refresh automático
- [ ] Se refresh falhar: marcar conexão inativa + flag para alerta
- [ ] `tests/test_strava_service.py` — mocks da API com respostas de sucesso e erro
- **Done:** token renovado automaticamente; conexão marcada inativa se refresh falhar

---

## Sprint 05 — Agente IA Coach + Nutrição
**Dias 41–55 | Objetivo: agente gerando planos estruturados com nutrição integrada**

*Sprint de 15 dias pela complexidade central do produto. US-034 (nutrição) incluída aqui pois é gerada no mesmo prompt que o treino.*

### Tarefas

#### T05.0 — Pré-requisitos Paralelos (iniciar no S01, sem custo de dev) `0d`
- [ ] Criar conta Stripe + iniciar verificação de identidade KYC (processo pode levar 3–10 dias úteis)
- [ ] Solicitar acesso à API TrainingPeaks em https://developers.trainingpeaks.com
- **Done:** aprovações prontas antes de S06/S11

#### T05.1 — AI Service: Estrutura e Prompts (US-013) `3d`
- [ ] `services/ai_service.py` — implementação completa:
  - `AthleteContext` dataclass com todos os campos do spec-v1
  - `TrainingRecommendation` dataclass
  - `SYSTEM_PROMPT` — expert em medicina do esporte (spec-v1 §3.9)
  - `format_athlete_context(ctx)` → str formatado para o prompt
  - `_call_anthropic(user_message)` → str (claude-sonnet-4-6, temp=0.3)
  - `_call_openai(user_message)` → str (gpt-4o, json_object mode)
  - `_parse_recommendation(raw, provider, model)` → TrainingRecommendation (parse progressivo do spec-enriched §5.2)
- **Done:** chamada direta para Claude retorna JSON válido com estrutura correta

#### T05.2 — Fallback e Safety Check (US-013, spec-enriched §5) `2d`
- [ ] `generate_with_fallback(context)` — Claude → GPT-4o → rest day
- [ ] `safety_check(plan, context)` — detector de carga perigosa (TSB crítico, fadiga extrema, duração absurda)
- [ ] Re-prompt se safety_check retornar warnings
- [ ] `tests/test_ai_service.py` — mocks de Claude e GPT-4o, teste de parse malformado, teste de fallback
- **Done:** com Claude mockado para falhar, GPT-4o é usado; com JSON malformado, parse progressivo funciona

#### T05.3 — Análise de TSB na Geração (US-014) `2d`
- [ ] `build_athlete_context(db, athlete_id)` — monta `AthleteContext` do banco
  - Busca CTL/ATL/TSB atual
  - Busca últimos 14 treinos (cycling + strength)
  - Busca métricas do dia (ou None se ausente)
  - Inclui flags: `is_new_athlete`, `detraining_detected`, `metrics_missing`
- [ ] Prompt incluir instrução explícita sobre TSB ranges (spec-v1 §3.9)
- [ ] `tests/`: testar contexto com TSB < -25 → esperar workout_type = "rest" ou "mobility"
- **Done:** com TSB=-28 no contexto, IA prescreve recuperação; log mostra raciocínio

#### T05.4 — Planos por Modalidade (US-015) `3d`
- [ ] Prompt com seção de formato por modalidade (ciclismo, musculação, corrida, natação, triathlon)
- [ ] Validação pós-parse: campos obrigatórios por `workout_type`
  - ciclismo: `sections` com `targets.power_pct_ftp`
  - musculação: `exercises` com `sets`, `reps`, `load`
  - corrida: `sections` com `targets.rpe` e descrição de ritmo
  - natação: `sections` com distâncias e pausas
  - triathlon: `sections` combinando 3 modalidades
- [ ] Testar geração para cada modalidade com perfil de atleta variado
- **Done:** cada modalidade retorna plano estruturado coerente com o nível do atleta

#### T05.5 — Endpoints de Recomendação (US-013, US-017) `3d`
- [ ] Modelo SQLAlchemy `AIRecommendation`
- [ ] `GET /api/recommendations/today` — gera se não existir
- [ ] `POST /api/recommendations/generate` — força geração (admin)
- [ ] `POST /api/recommendations/{id}/feedback`
- [ ] `GET /api/recommendations` — histórico
- [ ] `GET /api/admin/athletes/{id}/recommendations/weekly-plan` (stub — gerar 7 chamadas)
- [ ] Salvar `input_context`, `tokens_used`, `generation_time_ms` para auditoria
- **Done:** GET /today retorna plano em < 30s; feedback salvo corretamente

#### T05.6 — Nutrição Integrada ao Agente (US-034) `2d`
- [ ] Expandir prompt para gerar `nutrition_plan` no mesmo call (ou segundo call se tokens insuficientes)
- [ ] Campos: `calories_target`, `carbs_g`, `protein_g`, `fat_g`, `hydration_ml`, `pre_workout`, `during`, `post_workout`, `meals`
- [ ] Fallback `generate_default_nutrition(weight_kg, workout_type)` se IA não gerar nutrição
- [ ] Salvar em `nutrition_plans` vinculado à `ai_recommendation`
- [ ] Incluir `nutrition_plan` no response de `GET /api/recommendations/today`
- [ ] `tests/`: nutrição de dia intenso tem mais carbs; descanso tem mais proteína
- **Done:** nutrição gerada junto ao treino; valores coerentes com tipo de sessão

#### T05.7 — Frontend: Tela de Recomendação (US-017 parcial) `2d`
- [ ] `/recommendations` — card com treino do dia, seções expansíveis, rationale
- [ ] Loading state com "Gerando seu treino..." + polling 5s (até 60s)
- [ ] Exibição de raciocínio da IA em acordeão "Por que este treino?"
- [ ] Stars de feedback (1–10) + campo de notas
- **Done:** tela renderiza plano completo; feedback enviado e confirmado

---

## Sprint 06 — Integrações TP + Garmin + Apple Health
**Dias 56–65 | Objetivo: todas as integrações bidirecional funcionando**

### Tarefas

#### T06.1 — OAuth TrainingPeaks (US-012) `2d`
- [ ] `GET /api/auth/oauth/trainingpeaks/authorize`
- [ ] `GET /api/auth/oauth/trainingpeaks/callback`
- [ ] `DELETE /api/auth/oauth/trainingpeaks`
- [ ] `services/tp_service.py`:
  - `get_authorization_url(state)` → str
  - `exchange_code_for_tokens(code)` → dict
  - `refresh_access_token(refresh_token)` → dict
  - `create_planned_workout(access_token, workout)` → dict
  - `get_completed_workouts(access_token, from_date)` → list (polling)
  - `parse_tp_workout_to_workout(tp_workout, athlete_id)` → dict
- **Done:** OAuth completo; token salvo criptografado

#### T06.2 — Envio para TrainingPeaks e Garmin relay (US-019, US-020) `2d`
- [ ] `send_recommendation_to_trainingpeaks(db, recommendation_id)` — formata estrutura TP
- [ ] Campos obrigatórios TP: `title`, `sport_type`, `plannedDate`, `structure` (intervalos)
- [ ] Mapping `workout_type` → `sport_type` TrainingPeaks
- [ ] Marcar `sent_to_trainingpeaks = true` + salvar `trainingpeaks_workout_id`
- [ ] Frontend: badge "Enviado ao TrainingPeaks ✓" na tela de recomendação
- **Done:** treino aparece no calendário TrainingPeaks do atleta; fluxo → Garmin testado manualmente

#### T06.3 — Import TrainingPeaks Polling (US-021) `2d`
- [ ] `sync_trainingpeaks_workouts(db, athlete_id, access_token)` — polling a cada 15min via APScheduler
- [ ] Deduplicação por `external_id`
- [ ] Calcular TSS do workout importado
- [ ] Recalcular carga após import
- **Done:** treino executado no TrainingPeaks importado em ≤ 15min

#### T06.4 — Apple Health iOS Shortcut (US-021b) `2d`
- [ ] `POST /api/health/apple-health/{token}` — sem JWT, autenticado pelo token único
- [ ] Validação do token vs `athletes.apple_health_token`
- [ ] Upsert em `daily_metrics` (source: "apple_health")
- [ ] `GET /api/admin/athletes/{id}/apple-health-shortcut-link` — gera link de instalação
- [ ] Template do Shortcut iOS (arquivo `.shortcut` exportável)
- [ ] Frontend: instruções de instalação do Shortcut em `/settings`
- **Done:** POST do Shortcut salva métricas corretamente; métricas visíveis no dashboard

#### T06.5 — Tela de Integrações Completa `2d`
- [ ] `/settings` — status por plataforma (Strava, TrainingPeaks, Apple Health)
- [ ] Estado: not_connected / connecting / connected (com data de última sync) / error (com botão reconectar)
- [ ] Fluxo de reconexão quando token expirado
- [ ] `DELETE /api/auth/oauth/strava` + `DELETE /api/auth/oauth/trainingpeaks` com confirmação
- **Done:** todas as integrações com status correto; desconexão funciona

---

## Sprint 07 — Adaptação Pós-treino + App Cliente
**Dias 66–75 | Objetivo: ciclo de adaptação fechado; cliente vê treino e histórico**

### Tarefas

#### T07.1 — Adaptação Pós-treino (US-016) `3d`
- [ ] `analyze_workout_adherence(planned, executed)` → dict com desvios em %
- [ ] Incorporar feedback e desvios no `AthleteContext.recent_workouts`
- [ ] Prompt: seção "Análise do último treino: planejado vs executado"
- [ ] Se desvio > 20% de carga: instrução no prompt para ajuste proporcional
- [ ] Se RPE reportado > planejado em 2+ pontos: instrução para reduzir intensidade
- [ ] `GET /api/workouts/{id}` — retorna campos `planned_tss` e `actual_tss` quando workout_type = completed de recomendação
- **Done:** após treino com desvio, próxima recomendação reflete o ajuste no rationale

#### T07.2 — Histórico e Evolução do Atleta (US-023, US-024) `2d`
- [ ] Frontend `/dashboard` — componentes:
  - `CTLATLTSBChart` — gráfico linha triplo (60d, Recharts)
  - `DailyRecommendationCard` — treino do dia com todos os estados
  - `WeeklyTSSBar` — TSS semanal vs semana anterior
  - `RecentWorkoutsList` — últimos 5 treinos compactos
  - `DailyMetricsCard` — fadiga, sono, HRV do dia
- [ ] Frontend `/workouts` — lista com filtros por tipo e data
- [ ] Frontend `/workouts/{id}` — detalhe com planejado vs executado
- **Done:** dashboard carrega em < 2s; gráfico CTL/ATL/TSB correto; treinos listados

#### T07.3 — CTLATLTSBChart Completo `2d`
- [ ] `components/charts/CTLATLTSBChart.tsx`:
  - LineChart com 3 séries (CTL azul, ATL laranja, TSB verde/vermelho dinâmico)
  - TSB positivo = verde, negativo = vermelho (via gradiente ou stroke condicional)
  - Linha de referência em TSB=0 (ReferenceLine)
  - Tooltip com data + CTL + ATL + TSB + TSS do dia
  - Selector de período: 30d / 60d / 90d
  - Skeleton loader enquanto carrega
- **Done:** gráfico renderiza corretamente com dados reais; hover funciona; período altera dados

#### T07.4 — Visão Admin do Atleta (US-025) `2d`
- [ ] `/admin/athletes/{id}` — abas: Perfil / Plano / Histórico / Relatórios / Assinatura
- [ ] Aba Plano: mesma view que o atleta vê
- [ ] Aba Histórico: lista de treinos + gráfico CTL/ATL/TSB
- [ ] Indicador de aderência: % de treinos seguidos (planejado vs executado)
- [ ] Alerta visual se TSB < -25 (banner vermelho no topo do perfil)
- **Done:** admin vê dados completos do atleta; aderência calculada corretamente

#### T07.5 — Envio de Treino ao Strava (US-018) `1d`
- [ ] `send_recommendation_to_strava(db, recommendation_id)` — POST /workouts (Strava API)
- [ ] Marcar `sent_to_strava = true` + salvar `strava_workout_id`
- [ ] Tratar rate limit
- **Done:** treino planejado aparece no Strava do atleta

---

## Sprint 08 — Job Diário + Dashboard Admin
**Dias 76–85 | Objetivo: automação diária rodando; admin monitora em tempo real**

### Tarefas

#### T08.1 — Job Diário: Estrutura (US-026) `3d`
- [ ] `services/scheduler.py` — APScheduler com cron job 06:00 BRT
- [ ] `scripts/daily_update.py` — orquestrador completo:
  ```
  1. Criar job_execution_log (status=running)
  2. Buscar todos os atletas ativos
  3. asyncio.gather com semaphore=10 para processamento paralelo
  4. Para cada atleta: IMPORT → RECALC → GENERATE → SEND
  5. Salvar job_client_result por atleta
  6. Atualizar job_execution_log (status=completed/failed)
  ```
- [ ] Lock por data (evitar job duplo — spec-enriched §6.1)
- [ ] Timeout por atleta: 60s; timeout global: 15min
- [ ] Se > 50% de falhas: status `critical_failure` + email ao admin
- **Done:** job executa manualmente sem erros com 1 atleta de teste; log correto

#### T08.2 — Job Diário: Resiliência (US-026, spec-enriched §6) `2d`
- [ ] Cada step isolado em try/except com log + continua para o próximo atleta
- [ ] Verificar `lgpd_deletion_requests` antes de processar atleta
- [ ] Verificar `subscription.status == "active"` antes de processar
- [ ] Skip gracioso se token de plataforma inativo
- [ ] `tests/test_daily_job.py` — mock de Strava e IA, testar fluxo completo com 3 atletas
- **Done:** falha em 1 atleta não impede processamento dos outros; log detalha cada step

#### T08.3 — Dashboard Admin (US-028, US-029) `3d`
- [ ] `GET /api/admin/dashboard` — dados consolidados (spec-v1 §2.8)
- [ ] `GET /api/admin/job-logs` — últimos 7 dias
- [ ] Frontend `/admin/dashboard`:
  - Grid de cards por atleta: nome, TSB colorido, treino de hoje, status de integração
  - Seção de alertas: overtraining / falha de integração / inatividade / job não executado
  - Resumo do último job (success/failure count)
- [ ] Frontend `/admin/logs` — tabela com resultado por cliente por execução
- [ ] Badges de alerta com contagem no ícone da sidebar
- **Done:** dashboard carrega com dados reais; alertas corretos; logs de job exibidos

#### T08.4 — Notificações de Alerta (US-029) `2d`
- [ ] Detector de condições críticas no job:
  - TSB < -25 → gerar alerta em `admin_alerts` (tabela simples)
  - ≥ 3 falhas consecutivas de integração → alerta
  - ≥ 5 dias sem treino → alerta
  - Job não executado às 06:30 → alerta (verificado via endpoint de health check)
- [ ] `GET /api/admin/alerts` — alertas não lidos
- [ ] `PUT /api/admin/alerts/{id}/read`
- [ ] Frontend: badge com contagem de alertas na sidebar; painel de alertas
- **Done:** TSB < -25 gera alerta visível no dashboard; badge aparece corretamente

---

## Sprint 09 — App Cliente PWA + Feedback
**Dias 86–95 | Objetivo: atleta usa o app no celular; feedback fechando o ciclo**

### Tarefas

#### T09.1 — PWA Setup (US-030) `2d`
- [ ] Instalar e configurar `next-pwa`
- [ ] `manifest.json` — ícone, nome, cores, display standalone
- [ ] Service worker: cache do treino do dia (offline first)
- [ ] Testar instalação como PWA no Chrome/Safari iOS/Android
- [ ] Layout responsivo: todos os componentes funcionam em 360px+
- **Done:** app instalável como PWA; treino do dia acessível offline após carregamento inicial

#### T09.2 — Tela do Treino do Dia (US-023 completo) `2d`
- [ ] `/training` — card principal do dia:
  - Tipo de treino com ícone (bicicleta, haltere, tênis, natação, etc.)
  - Título, duração, intensidade (badge colorido)
  - Seções expansíveis (aquecimento, principal, desaquecimento)
  - Para musculação: tabela de exercícios com sets/reps/carga
  - Para ciclismo: alvos em watts % FTP + zona FC + RPE
  - Indicador de TSB atual com cor
  - Botão "Marcar como feito" → abre formulário de feedback
- [ ] Estado `rest_day`: card verde especial com orientações de recuperação ativa
- [ ] Loading state: skeleton animado
- **Done:** todas as modalidades renderizam corretamente no celular; estados OK

#### T09.3 — Nutrição do Dia Integrada (US-035) `1d`
- [ ] Seção "Nutrição do Dia" abaixo do treino
- [ ] Exibir: calorias, macros (carbs/proteína/gordura/hidratação)
- [ ] Cards visuais para pré-treino, durante, pós-treino, refeições
- [ ] Linguagem simplificada (sem jargão técnico)
- **Done:** nutrição visível abaixo do treino; dados corretos do banco

#### T09.4 — Feedback Pós-treino (US-031) `2d`
- [ ] Modal de feedback: "Como foi o treino?" (1–10) + RPE real + "Completou? Sim/Não" + notas
- [ ] `POST /api/recommendations/{id}/feedback`
- [ ] Feedback considerado no próximo prompt da IA (via `recent_workouts`)
- [ ] Frontend: modal abre após tocar "Marcar como feito" ou botão "Dar feedback" no histórico
- **Done:** feedback salvo; próxima recomendação menciona feedback no rationale

#### T09.5 — Histórico Completo do Atleta (US-024) `2d`
- [ ] `/workouts` no app do cliente — lista últimos 30 treinos
- [ ] Cada item: data, tipo (ícone), TSS, status (realizado/planejado/perdido)
- [ ] Tocar: abre detalhe com planejado vs executado
- [ ] Seção "Minha Evolução": gráfico CTL/ATL/TSB (mesmo componente do admin)
- [ ] `/metrics` no app do cliente — formulário de métricas + gráficos de tendência
- **Done:** histórico correto; gráfico renderiza; formulário de métricas funciona no celular

#### T09.6 — Sidebar e Navegação `1d`
- [ ] Sidebar/bottom-nav responsiva: Dashboard / Treino / Histórico / Métricas / Config
- [ ] `AppShell.tsx` com layout adaptativo (desktop: sidebar; mobile: bottom nav)
- [ ] Indicadores de notificação (treino não visualizado)
- **Done:** navegação funciona em desktop e mobile; ativo destacado

---

## Sprint 10 — Relatórios PDF
**Dias 96–102 | Objetivo: relatórios PDF gerados e enviados por email**
*(Nutrição movida para S05 — gerada junto ao agente IA)*

### Tarefas

#### T10.1 — Engine de Relatórios (US-036) `3d`
- [ ] `services/report_service.py`:
  - `generate_weekly_report(db, athlete_id, period_start, period_end)` → dict
  - `generate_monthly_report(db, athlete_id, month_start)` → dict
  - `render_report_to_pdf(report_data)` → bytes (WeasyPrint)
- [ ] Template HTML/CSS para relatório:
  - Cabeçalho com logo + dados do atleta + período
  - Resumo: treinos realizados vs planejados (%), TSS total, aderência %
  - Gráfico CTL/ATL/TSB do período (imagem SVG embutida)
  - Top 3 treinos da semana
  - Métricas subjetivas (sono, fadiga, HRV — médias)
  - Insights da IA (resumo do rationale dos treinos)
  - Orientações para próxima semana
- [ ] Upload do PDF para Supabase Storage
- **Done:** PDF gerado em < 10s; layout legível e profissional

#### T10.3 — Endpoints de Relatório (US-036, US-037) `1d`
- [ ] `POST /api/admin/athletes/{id}/reports/generate`
- [ ] `GET /api/admin/athletes/{id}/reports/{id}/download`
- [ ] `POST /api/admin/athletes/{id}/reports/{id}/send` — email via Resend
- [ ] `GET /api/athletes/reports` — histórico de relatórios (atleta autenticado)
- **Done:** relatório gerado, baixado e enviado por email com PDF anexado

#### T10.4 — Envio Automático Semanal (US-037) `1d`
- [ ] Job APScheduler: domingos às 20h — gerar e enviar relatório semanal para todos os atletas com envio automático ativado
- [ ] Campo `auto_report_enabled` em `athletes`
- [ ] `PUT /api/admin/athletes/{id}` — toggle de envio automático
- **Done:** job de domingo gera PDFs e envia emails

#### T10.5 — Relatório no App do Cliente (US-038) `2d`
- [ ] `/reports` no app do atleta — lista de relatórios recebidos
- [ ] Resumo visual: gráfico de barras de TSS por semana + aderência em %
- [ ] Botão "Exportar PDF" — download direto
- **Done:** atleta visualiza relatórios; download funciona no celular

---

## Sprint 11 — Assinaturas + Stripe + CI/CD
**Dias 106–115 | Objetivo: controle de acesso por assinatura; deploy automático**

### Tarefas

#### T11.1 — Gestão de Assinaturas Manual (US-032) `2d`
- [ ] Modelo SQLAlchemy `Subscription`
- [ ] `GET /api/admin/athletes/{id}/subscription`
- [ ] `PUT /api/admin/athletes/{id}/subscription` — ativar/suspender/cancelar
- [ ] Validação de transições de status (spec-enriched §1.7)
- [ ] Middleware: verificar `subscription.status == "active"` em todas as rotas do atleta
- [ ] Frontend: aba "Assinatura" no perfil do atleta (admin)
- **Done:** suspender bloqueia acesso do atleta; reativar restaura; cancelar é irreversível

#### T11.1b — Testes Stripe (NFR-16) `1d`
- [ ] `tests/test_stripe_webhooks.py`: payment_succeeded → ativo; payment_failed → past_due; subscription.deleted → cancelled
- **Done:** 3 eventos processados corretamente com assinatura HMAC mockada

#### T11.2 — Stripe Integration (US-033) `4d`
- [ ] Configurar conta Stripe (modo teste)
- [ ] `services/stripe_service.py`:
  - `create_customer(athlete)` → str (customer_id)
  - `create_subscription(customer_id, price_id)` → dict
  - `cancel_subscription(subscription_id)` → dict
  - `list_invoices(customer_id)` → list
- [ ] `POST /api/webhooks/stripe` — processar eventos:
  - `invoice.payment_succeeded` → manter status ativo, renovar `current_period_end`
  - `invoice.payment_failed` → status `past_due`, iniciar carência 3 dias
  - `customer.subscription.deleted` → status `cancelled`
- [ ] `GET /api/admin/financials` — MRR, clientes ativos, inadimplentes
- [ ] Frontend `/admin/financials` — painel financeiro simples
- **Done:** cobrança recorrente funciona em modo teste; webhook atualiza status corretamente

#### T11.3 — Período de Carência e Notificações (US-033) `1d`
- [ ] Job diário verifica atletas `past_due` há > 3 dias → suspender
- [ ] Email ao atleta em `payment_failed`: "Pagamento não processado — regularize em 3 dias"
- [ ] Email ao admin com lista de inadimplentes
- **Done:** 3 dias após falha de pagamento, acesso suspenso; emails enviados

#### T11.4 — CI/CD com GitHub Actions (US-003) `2d`
- [ ] Workflow `.github/workflows/deploy-backend.yml`:
  - Trigger: push em `main`
  - Steps: checkout → setup Python → install deps → run tests → deploy Railway
- [ ] Workflow `.github/workflows/deploy-frontend.yml`:
  - Trigger: push em `main`
  - Steps: checkout → setup Node → install → type-check → lint → deploy Vercel
- [ ] Variáveis de ambiente nos secrets do GitHub
- [ ] Status badges no README
- **Done:** push na main dispara deploy automático; testes falham = deploy bloqueado

#### T11.5 — LGPD: Exportação e Deleção (US-006, US-007) `1d`
- [ ] `GET /api/lgpd/my-data` — gerar ZIP com todos os dados do atleta
- [ ] `DELETE /api/lgpd/my-data` — criar `lgpd_deletion_requests`, responder 202
- [ ] Job: verificar `lgpd_deletion_requests` pendentes e executar deleção em cascata
- [ ] Email de confirmação de deleção ao atleta (7 dias após solicitação, após execução)
- **Done:** ZIP gerado com todos os dados; solicitação de deleção cria registro e executa

---

## Sprint 12 — QA, Performance e Deploy Final
**Dias 114–121 (8 dias) | Objetivo: produto em produção, todos os NFRs verificados**

### Tarefas

#### T12.1 — Performance e NFRs `3d`
- [ ] **NFR-01** (< 500ms p95): cenário k6 com 50 usuários simultâneos em `/api/recommendations/today` por 60s; otimizar queries com índices se necessário
- [ ] **NFR-02** (< 30s geração IA): medir tempo real com 5 atletas; adicionar timeout com mensagem amigável
- [ ] **NFR-03** (< 10min job total): simular job com 50 atletas mockados; medir duração total
- [ ] **NFR-05** (< 2s PWA 4G): medir com Lighthouse mobile; otimizar bundle (`next build --analyze`)
- [ ] **NFR-14** (uptime 99,5%): configurar health check Railway; alerta se > 26h sem execução do job
- [ ] **NFR-15** (50 clientes simultâneos): cenário k6 de carga com 50 usuários paralelos no dashboard admin
- [ ] **NFR-16** (cobertura ≥ 70%): rodar `pytest --cov`; adicionar testes até atingir meta nas funções críticas

#### T12.2 — Segurança Final `1d`
- [ ] Revisar todos os endpoints: auth, role check, validação de input
- [ ] Confirmar headers de segurança (NFR-09)
- [ ] Confirmar que nenhum token ou dado de saúde aparece em logs de produção
- [ ] Testar rate limiting em `/auth/login` (10 tentativas → bloqueio)
- [ ] Verificar RLS: atleta A não consegue acessar dados do atleta B

#### T12.3 — Deploy Produção `1d`
- [ ] Deploy backend no Railway (produção)
- [ ] Configurar variáveis de ambiente de produção
- [ ] Executar migrations Alembic em produção
- [ ] Deploy frontend na Vercel (produção)
- [ ] Configurar domínio customizado (se disponível)
- [ ] Registrar webhook Strava com URL de produção
- [ ] Configurar Stripe webhook com URL de produção
- [ ] Smoke test: cadastrar 1 atleta real, conectar Strava, executar job manualmente

#### T12.4 — Documentação Final `1d`
- [ ] `docs/ARCHITECTURE.md` — diagrama ASCII + descrição de componentes
- [ ] `docs/STRAVA_SETUP.md` — passo a passo OAuth
- [ ] `docs/DEPLOY.md` — variáveis de ambiente + comandos
- [ ] `README.md` — instruções de início rápido atualizadas
- [ ] `docs/AI_PROMPTS.md` — prompts documentados com exemplos

---

## Dependências entre Sprints

```
S01 (Auth + Infra)
  └─► S02 (Clientes)
        └─► S03 (Carga + Musculação)
              └─► S04 (Strava)
                    └─► S05 (Agente IA) ◄─── S03
                          └─► S06 (TP + Garmin + Apple Health)
                                └─► S07 (Adaptação + App Cliente)
                                      └─► S08 (Job Diário + Dashboard)
                                            └─► S09 (PWA + Feedback)
                                                  └─► S10 (Nutrição + PDFs)
                                                        └─► S11 (Stripe + CI/CD)
                                                              └─► S12 (QA + Deploy)
```

---

## Estimativas e Riscos

| Sprint | Dias | Risco | Mitigação |
|--------|------|-------|----------|
| S01 | 10 | Baixo | Stack conhecida |
| S02 | 10 | Baixo | CRUD padrão |
| S03 | 10 | Médio | Cálculos CTL/ATL devem ser validados com dados reais |
| S04 | 10 | Médio | Strava API pode mudar ou ter rate limits inesperados |
| S05 | 15 | **Alto** | Qualidade dos planos da IA depende de prompt engineering iterativo |
| S06 | 10 | **Alto** | TrainingPeaks API e Garmin relay dependem de aprovações/quirks externos |
| S07 | 10 | Médio | Adaptação pós-treino é lógica complexa de negócio |
| S08 | 10 | Médio | Job diário com múltiplos atletas pode ter race conditions |
| S09 | 10 | Baixo | PWA e UI mobile são previsíveis |
| S10 | 10 | Médio | WeasyPrint pode ter quirks de CSS no PDF |
| S11 | 10 | Médio | Stripe em produção requer aprovação e testes de webhooks reais |
| S12 | 5 | Baixo | Buffer para imprevistos |

**Total:** 120 dias úteis (~6 meses)
**Margem de segurança:** ±15 dias (dentro da estimativa original de 110–150 dias)

---

## Critérios de Aceite do MVP Completo

- [ ] Ciclo completo funcionando: cadastro → plano → plataforma → treino → import → adaptação
- [ ] Job diário executa automaticamente às 06h sem intervenção manual
- [ ] Admin gerencia ≥ 10 atletas no painel sem degradação
- [ ] App do atleta carrega em < 2s em 4G
- [ ] Dados de saúde criptografados confirmados por inspeção no banco
- [ ] LGPD: exportação e deleção funcionando em < 72h
- [ ] Todos os testes automatizados passando (cobertura ≥ 70% nas funções críticas)
- [ ] Deploy automático funcionando via GitHub Actions
- [ ] Stripe processando cobranças em modo produção

---

*Próxima fase: Sprint Validator (Fase 09) — auditoria do plano de sprints*
