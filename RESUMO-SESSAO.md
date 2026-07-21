# FitCoach AI — Resumo da Sessão de Descoberta
Data: 2026-04-30

---

## O que fizemos nesta sessão

Executamos as **5 primeiras fases** do pipeline multiagente de criação de software:

```
✅ Fase 01 — Discovery         (entrevista estruturada)
✅ Fase 02 — PRD Generator     (38 user stories geradas)
✅ Fase 03 — PRD Validator     (checkpoint humano — aprovado)
✅ Fase 04 — PRD Complete      (PRD.md consolidado)
⏸ Fase 05 — Tech Decisions    (aguardando confirmação da stack)
```

---

## O Produto: FitCoach AI

**Problema resolvido:** Médico sem expertise em educação física precisa prescrever e gerenciar treinos personalizados para múltiplos clientes (ciclismo, musculação, corrida, natação, triathlon), com adaptação automática baseada em dados reais de performance — sem depender de ação manual do cliente.

**Solução:** Plataforma de coaching esportivo com agente IA especializado em medicina do esporte que cria, envia e adapta planos de treino diários de forma totalmente automatizada, integrada a Strava, Garmin, TrainingPeaks e Apple Health.

**Diferencial central:** O ciclo completo é 100% automático —
```
Cadastro → IA gera plano → Envia à plataforma → Cliente treina
→ Dados recebidos automaticamente → IA ajusta próximo treino
```
O cliente não precisa fazer nada além de treinar.

---

## Personas

| Persona | Papel |
|---------|-------|
| **Dr. Admin** | Médico que administra a plataforma, cadastra clientes, acompanha carteira |
| **Agente IA Coach** | Sistema autônomo especializado em medicina do esporte — gera e adapta planos |
| **Cliente Atleta** | Atleta que recebe treinos no app e nas plataformas conectadas |

---

## Escopo do MVP (12 épicos · 38 user stories)

| # | Épico | Funcionalidade Principal |
|---|-------|--------------------------|
| EP-01 | Infraestrutura | Repositório, Supabase, CI/CD deploy automático |
| EP-02 | Autenticação + LGPD | Login admin/cliente, consentimento LGPD, criptografia de dados de saúde |
| EP-03 | Gestão de Clientes | Cadastro, anamnese esportiva, disponibilidade, conexão com plataformas |
| EP-04 | Agente IA Coach | Geração de planos por modalidade, análise de TSB, adaptação pós-treino |
| EP-05 | Integrações | Strava, Garmin Connect, TrainingPeaks, Apple Health (bidirecional) |
| EP-06 | Planos e Treinos | CTL/ATL/TSB, visualização do treino do dia, histórico |
| EP-07 | Automação Diária | Job 6h/dia: importa → recalcula → gera → envia (sem ação humana) |
| EP-08 | Dashboard Admin | Visão multi-cliente com alertas de overtraining e falhas |
| EP-09 | App Mobile (PWA) | Interface responsiva, offline, carrega em < 2s em 4G |
| EP-10 | Assinaturas | Gestão de acesso + Stripe para cobrança recorrente |
| EP-11 | Orientação Nutricional | Recomendações diárias de macros, hidratação e timing integradas ao treino |
| EP-12 | Relatórios | PDF semanal/mensal com evolução, envio automático ao cliente |

### Modalidades suportadas
Ciclismo · Musculação · Corrida · Natação · Triathlon

### Integrações
Strava · Garmin Connect · TrainingPeaks · Apple Health · Stripe

---

## Decisões importantes tomadas

| Decisão | Motivo |
|---------|--------|
| Automação total sem ação do cliente | Core do produto — diferencial competitivo |
| LGPD como requisito primordial | Dados de saúde de atletas — responsabilidade médica |
| Mobile-first (PWA no MVP) | Cliente acessa principalmente pelo celular |
| Natação + Triathlon no MVP | Confirmado pelo usuário como essencial |
| Apple Health no MVP | Fundamental para captura de dados em iOS |
| Orientação nutricional no MVP | Parte integral do coaching esportivo completo |
| Relatórios exportáveis em PDF no MVP | Necessário para acompanhamento e engajamento |

---

## Stack Técnica Proposta (aguardando confirmação)

| Camada | Tecnologia |
|--------|-----------|
| Frontend | Next.js 14 (App Router) + TypeScript + Tailwind CSS + shadcn/ui |
| Backend | Python 3.11 + FastAPI + Pydantic v2 |
| Banco de Dados | Supabase (PostgreSQL) + Row Level Security |
| Autenticação | Supabase Auth (JWT) + OAuth 2.0 para plataformas externas |
| API | REST + WebSocket (notificações) |
| Deploy Backend | Railway |
| Deploy Frontend | Vercel |
| ORM | SQLAlchemy 2.0 async + Alembic |
| Agendador | APScheduler (embutido no FastAPI) |
| IA | Claude API (Anthropic) |
| Pagamentos | Stripe |
| CI/CD | GitHub Actions |
| Gráficos | Recharts |

---

## Requisitos Não-Funcionais chave

| Requisito | Meta |
|-----------|------|
| APIs do backend | < 500ms no p95 |
| Geração de plano pela IA | < 30 segundos |
| Importação pós-treino | ≤ 30 minutos após sincronização |
| Carregamento do app (4G) | < 2 segundos |
| Uptime | ≥ 99,5% |
| Clientes simultâneos (MVP) | ≥ 50 |
| Dados de saúde | AES-256 em repouso, HTTPS/TLS 1.3 em trânsito |
| Exclusão de dados LGPD | ≤ 72h após solicitação |

---

## Artefatos gerados (pasta `docs/`)

| Arquivo | Conteúdo |
|---------|----------|
| `docs/discovery.json` | Resultado completo da entrevista de Discovery |
| `docs/prd-draft.json` | PRD draft inicial (33 stories, 10 épicos) |
| `docs/prd-validated.json` | PRD após validação humana (38 stories, 12 épicos) |
| `docs/PRD.md` | **PRD Final** — fonte da verdade de requisitos |
| `project-state.json` | Estado atual do pipeline multiagente |

---

## Próximos passos

1. **Confirmar a stack técnica** (Tech Decisions — Fase 05) → responder "pode avançar"
2. **Spec Generation** (Fase 06) — modelo de dados, contratos de API, estados de UI
3. **Spec Enricher** (Fase 07) — edge cases, erros, validações, segurança
4. **Planner** (Fase 08) — plano de sprints com tarefas rastreáveis
5. **Sprint Validator** (Fase 09) — auditoria do plano
6. **Coder ↺ Evaluator** (Fases 10-11) — implementação iterativa
7. **Acceptance Reviewer** (Fase 12) — revisão final

---

## Para retomar a sessão

Abra o Claude Code neste diretório. O pipeline lerá automaticamente o `project-state.json` e retomará da **Fase 05 (Tech Decisions)** aguardando sua confirmação da stack técnica.

Ou digite: `/tech-decisions` para reapresentar as opções.
