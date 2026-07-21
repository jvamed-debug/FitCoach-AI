# Sprint Plan — Validado
Versão: 1.0 | Data: 2026-04-30 | Fase: 09 — Sprint Validator

> Auditoria independente do sprint-plan.md contra PRD.md, spec-v1.md e spec-enriched.md.
> Problemas classificados por severidade: 🔴 Crítico | 🟠 Alto | 🟡 Médio | 🟢 Baixo

---

## 1. Cobertura de Stories (38/38)

Mapeamento completo de todas as user stories contra sprints:

| Story | Sprint | Tarefa | Status |
|-------|--------|--------|--------|
| US-001 | S01 | T01.1, T01.2 | ✅ |
| US-002 | S01 | T01.3 | ✅ |
| US-003 | S11 | T11.4 | ✅ |
| US-004 | S01 | T01.4 | ✅ |
| US-005 | S01 | T01.5 | ✅ |
| US-006 | S01 + S11 | T01.5 + T11.5 | ✅ |
| US-007 | S02 + S11 | T02.1 + T11.5 | ⚠️ Parcial (ver #8) |
| US-008 | S02 | T02.1 | ✅ |
| US-009 | S02 | T02.2 | ✅ |
| US-010 | S02 | T02.3 | ✅ |
| US-011 | S02 | T02.4 | ✅ |
| US-012 | S04 + S06 | T04.1 + T06.1 + T06.4 | ✅ |
| US-013 | S05 | T05.1, T05.3, T05.5 | ✅ |
| US-014 | S05 | T05.3 | ✅ |
| US-015 | S05 | T05.4 | ✅ |
| US-016 | S07 | T07.1 | ✅ |
| US-017 | S05 | T05.6 | ✅ |
| US-018 | S04 + S07 | T04.2 + T07.5 | ✅ (split intencional) |
| US-019 | S06 | T06.2 | ✅ |
| US-020 | S06 | T06.2 | ✅ |
| US-021 | S04 + S06 | T04.3 + T06.3 | ✅ |
| US-021b | S06 | T06.4 | ✅ |
| US-022 | S03 | T03.1, T03.2 | ✅ |
| US-023 | S03 + S07 | T03.x + T07.2 | ✅ |
| US-024 | S07 | T07.2 | ✅ |
| US-025 | S07 | T07.4 | ✅ |
| US-026 | S08 | T08.1, T08.2 | ✅ |
| US-027 | S08 | T08.3 | ✅ |
| US-028 | S08 | T08.3 | ✅ |
| US-029 | S08 | T08.4 | ✅ |
| US-030 | S09 | T09.1 | ✅ |
| US-031 | S09 | T09.4 | ✅ |
| US-032 | S11 | T11.1 | ✅ |
| US-033 | S11 | T11.2, T11.3 | ✅ |
| US-034 | S10 | T10.1 | 🔴 Fora de ordem |
| US-035 | S09 | T09.3 | 🔴 Fora de ordem |
| US-036 | S10 | T10.2, T10.3 | ✅ |
| US-037 | S10 | T10.4 | ✅ |
| US-038 | S10 | T10.5 | ✅ |

**Resultado:** todas as 38 stories cobertas. 1 story com sequência incorreta (US-034/US-035).

---

## 2. Problemas Encontrados

---

### 🔴 #1 — US-035 implementada antes de US-034 (sequência quebrada)

**Localização:** S09 T09.3 implementa tela de nutrição; S10 T10.1 implementa geração de nutrição pela IA.

**Impacto:** o frontend de nutrição renderizaria dados que ainda não existem no banco. Em S09 não haverá registros em `nutrition_plans`.

**Correção:** mover a **geração de nutrição (US-034)** para o **S05** (junto com o agente IA — nutrição é gerada no mesmo prompt que o treino). A tela de nutrição (US-035) permanece no S09 e funcionará porque os dados já existirão desde S05.

**Ajuste no plano:**
- Remover T10.1 de S10
- Adicionar no S05 T05.1: incluir `nutrition_plan` na estrutura do prompt e no parse
- S10 passa a ter apenas: relatórios PDF (T10.2, T10.3, T10.4, T10.5) — libera ~3 dias

---

### 🔴 #2 — Tabelas do banco faltando no schema (spec-v1)

**Localização:** spec-v1 SQL não inclui:
- `admin_alerts` — usada em S08 T08.4
- `lgpd_deletion_requests` — referenciada em spec-enriched §10.3 e S11 T11.5

**Impacto:** migrations vão falhar; código vai referenciar tabelas inexistentes.

**Correção:** adicionar ao `supabase/migrations/001_initial_schema.sql` (ou criar migration separada `002_missing_tables.sql`):

```sql
-- Alertas para o admin
CREATE TABLE IF NOT EXISTS admin_alerts (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    admin_id        UUID NOT NULL REFERENCES admin_users(id) ON DELETE CASCADE,
    athlete_id      UUID REFERENCES athletes(id) ON DELETE CASCADE,
    alert_type      VARCHAR(50) NOT NULL,  -- 'overtraining_risk' | 'integration_failure' | 'inactivity' | 'job_not_run' | 'payment_failed'
    message         TEXT NOT NULL,
    metadata        JSONB,
    is_read         BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_admin_alerts_unread ON admin_alerts(admin_id, is_read, created_at DESC);

-- Solicitações de exclusão LGPD
CREATE TABLE IF NOT EXISTS lgpd_deletion_requests (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    athlete_id      UUID NOT NULL REFERENCES athletes(id) ON DELETE CASCADE,
    requested_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deadline        TIMESTAMPTZ NOT NULL,  -- requested_at + 72h
    executed_at     TIMESTAMPTZ,
    status          VARCHAR(20) DEFAULT 'pending',  -- 'pending' | 'executed'
    confirmation_email_sent BOOLEAN DEFAULT FALSE
);
```

---

### 🟠 #3 — S12 subestimado (5 dias para QA + perf + segurança + deploy + docs)

**Localização:** S12 cobre 4 tarefas densas em apenas 5 dias.

**Análise:**
- T12.1 (NFR benchmark + otimização de queries): realista são 3 dias se encontrar issues
- T12.2 (segurança): 1 dia é suficiente para revisão
- T12.3 (deploy produção + configuração de webhooks Stripe/Strava): 2 dias
- T12.4 (documentação): 2 dias

Total real: **8 dias mínimo**, não 5.

**Correção:** expandir S12 para **8 dias** (total do projeto: 123 dias úteis, dentro da margem de 110–150).

---

### 🟠 #4 — Aprovação Stripe para produção pode travar S11

**Localização:** S11 T11.2 — Stripe Integration.

**Problema:** Stripe no Brasil (pessoa física ou jurídica) requer verificação de identidade (KYC) que pode levar 3–10 dias úteis. Se iniciar só no S11 (dia 106), pode bloquear o deploy final.

**Correção:** adicionar no **S01** como tarefa paralela sem código:
- [ ] Criar conta Stripe (modo teste imediato, sem aprovação)
- [ ] Iniciar processo de verificação de identidade para modo produção
- [ ] Configurar conta bancária para recebimentos

Sem custo de dev — apenas burocrático. Garante aprovação pronta no S11.

---

### 🟠 #5 — Webhook Strava não funciona em localhost (sem ngrok)

**Localização:** S04 T04.3 — Webhook Strava.

**Problema:** Strava exige uma URL pública HTTPS para registrar a subscription de webhook. Em desenvolvimento local, `localhost:8000` não é acessível pela Strava.

**Solução não documentada no plano:** adicionar ao S04:
- [ ] Instalar e configurar **ngrok** (ou **cloudflared tunnel**) para expor localhost durante desenvolvimento
- [ ] Usar URL ngrok para registrar a subscription Strava (temporária para dev)
- [ ] Documentar em `docs/STRAVA_SETUP.md` o passo de ngrok

---

### 🟠 #6 — Cobertura de testes insuficiente para atingir NFR-16 (≥ 70%)

**Localização:** apenas S03 e S05 têm testes explicitamente planejados.

**Funções críticas sem testes planejados:**
| Módulo | Sprint | Risco |
|--------|--------|-------|
| `auth.py` (JWT, role check) | S01 | Alto — segurança |
| `strava_service.py` | S04 | Alto — integração core |
| `tp_service.py` | S06 | Médio |
| `daily_update.py` (job orquestrador) | S08 | Alto — automação core |
| `stripe_service.py` + webhook | S11 | Médio — financeiro |

**Correção:** adicionar tarefa de testes no final de cada sprint relevante:

| Sprint | Tarefa extra | Estimativa |
|--------|-------------|------------|
| S01 | `tests/test_auth.py` — JWT, role, LGPD middleware | +1d |
| S04 | `tests/test_strava_service.py` — mocks completos | já existe (T04.5) ✅ |
| S06 | `tests/test_tp_service.py` + `test_apple_health.py` | +1d |
| S08 | `tests/test_daily_job.py` — fluxo completo mockado | já existe (T08.2) ✅ |
| S11 | `tests/test_stripe_webhooks.py` | +1d |

**Impacto:** +3 dias no total → 126 dias.

---

### 🟡 #7 — iOS Shortcut subestimado

**Localização:** S06 T06.4 — Apple Health iOS Shortcut (`2d`).

**Problema:** criar um arquivo `.shortcut` válido e exportável requer:
- Dispositivo iOS físico (não simulável no Mac)
- Conhecimento da sintaxe interna (XML proprietário)
- Testes reais com HealthKit (requer usuário real com dados)
- Possível limitação: Shortcuts com acesso a HealthKit requerem iOS 16.2+

**Correção:** aumentar estimativa de `2d` → `3d`. Adicionar critério de done: "testado em iPhone real com dados do HealthKit".

---

### 🟡 #8 — US-007 parcialmente coberto (admin vê status LGPD por cliente)

**Localização:** US-007 requer que admin veja status de consentimento LGPD e log de auditoria por cliente.

**O que está no plano:**
- S02 T02.1: formulário de cadastro inclui LGPD ✅
- S11 T11.5: endpoints de exportação e deleção ✅

**O que está faltando:**
- Endpoint `GET /admin/athletes/{id}` deve retornar campo `lgpd_status: { consented: bool, consented_at: datetime, version: str }`
- UI no perfil do atleta (admin): aba ou seção mostrando status LGPD + botão "Revogar acesso"
- Log de auditoria visível no painel admin (não apenas no banco)

**Correção:** adicionar ao S02 T02.1:
- [ ] Campo `lgpd_status` no response de `GET /admin/athletes/{id}`
- [ ] Seção LGPD no perfil do atleta (admin): status, data de aceite, versão dos termos

---

### 🟡 #9 — TrainingPeaks API requer aprovação prévia

**Localização:** S06 T06.1 — OAuth TrainingPeaks.

**Problema:** TrainingPeaks exige aprovação de desenvolvedor para acesso à API de integração. O processo pode levar dias ou semanas.

**Correção:** adicionar ao **S01** (paralelo com outras tarefas, sem custo de dev):
- [ ] Solicitar acesso à API TrainingPeaks em https://developers.trainingpeaks.com
- [ ] Aguardar aprovação (pode chegar durante S02–S03)

---

### 🟡 #10 — Frontend `/metrics` duplicado entre S03 e S09

**Localização:** S03 T03.4 diz "Frontend `/metrics` — formulário com sliders + campos numéricos". S09 T09.5 diz "Frontend `/metrics` no app do cliente — formulário de métricas + gráficos".

**Problema:** não está claro o que cada sprint entrega. Risco de retrabalho.

**Correção:** separar explicitamente:
- **S03 T03.4:** implementar apenas o **backend** + formulário básico de métricas (sem gráficos) — suficiente para testar o cálculo de carga
- **S09 T09.5:** implementar versão **mobile-first** completa com gráficos de tendência

Isso está implícito no plano mas deve ser explícito para evitar entregar o frontend duas vezes.

---

### 🟢 #11 — Garmin inbound relay não tem teste explícito

**Localização:** S04 T04.3 — Webhook Strava.

**Problema:** o fluxo Garmin → Garmin Connect → Strava → FitCoach está implicitamente coberto pelo webhook Strava, mas não há tarefa de teste que valide especificamente este path. Dados de atividades sincronizadas via Garmin podem ter campos diferentes dos de atividades nativas do Strava (ex: campo `device_watts: false`).

**Correção:** adicionar ao S04 T04.3:
- [ ] Testar import de atividade Garmin-relay (usar payload real de atividade Garmin sincronizada no Strava)
- [ ] Verificar que TSS é calculado corretamente mesmo quando `device_watts: false`

---

### 🟢 #12 — NFR-15 (50 clientes simultâneos) sem teste de carga planejado

**Localização:** S12 T12.1 menciona "medir endpoints com k6 ou locust" mas não especifica cenário de 50 clientes.

**Correção:** adicionar ao S12 T12.1:
- [ ] Cenário k6: 50 usuários simultâneos em `/api/recommendations/today` por 60s
- [ ] Meta: p95 < 500ms (NFR-01)
- [ ] Cenário job diário: simular 50 atletas no job com dados reais e medir tempo total (meta: < 10min, NFR-03)

---

## 3. Resumo das Correções

| # | Severidade | Correção | Impacto no cronograma |
|---|-----------|---------|----------------------|
| 1 | 🔴 | Mover US-034 (nutrição) para S05; US-035 permanece em S09 | 0 dias (redistribuição) |
| 2 | 🔴 | Adicionar migration `002_missing_tables.sql` (admin_alerts + lgpd_deletion_requests) | 0 dias (parte do T01.3) |
| 3 | 🟠 | Expandir S12 de 5 → 8 dias | +3 dias |
| 4 | 🟠 | Iniciar aprovação Stripe em S01 (sem custo de dev) | 0 dias |
| 5 | 🟠 | Adicionar ngrok ao S04 T04.3 | 0 dias (meio dia de setup) |
| 6 | 🟠 | Adicionar testes em S01, S06, S11 | +3 dias |
| 7 | 🟡 | Aumentar S06 T06.4 de 2d → 3d | +1 dia |
| 8 | 🟡 | Adicionar campos LGPD ao S02 T02.1 | 0 dias (junto com cadastro) |
| 9 | 🟡 | Solicitar API TrainingPeaks em S01 (sem custo de dev) | 0 dias |
| 10 | 🟡 | Clarificar escopo de `/metrics` em S03 vs S09 | 0 dias |
| 11 | 🟢 | Adicionar teste Garmin relay ao S04 T04.3 | 0 dias (dentro do T04.3) |
| 12 | 🟢 | Adicionar cenários de carga ao S12 T12.1 | 0 dias (dentro do T12.1) |

**Total de dias adicionados:** +7 dias → **127 dias úteis** (~6,3 meses)
Dentro da margem original de 110–150 dias. ✅

---

## 4. Sprint Plan Ajustado (Visão Geral)

| Sprint | Dias | Mudança vs v1 |
|--------|------|--------------|
| S01 | 10 | +aprovação Stripe e TP (paralelo, 0 custo dev) + testes auth (+1d → realoca de buffer S01) |
| S02 | 10 | +campo lgpd_status no perfil do atleta (0 dias adicionais) |
| S03 | 10 | Escopo /metrics clarificado (apenas backend + form básico) |
| S04 | 10 | +ngrok + teste Garmin relay (0 dias) |
| S05 | 15 | +geração de nutrition_plan junto ao treino (redistribuído de S10) |
| S06 | 11 | T06.4 Apple Health: 2d → 3d (+1d) |
| S07 | 10 | Sem mudanças |
| S08 | 10 | Sem mudanças |
| S09 | 10 | US-035 (tela nutrição) permanece — dados já existem desde S05 ✅ |
| S10 | 7 | US-034 removida (+3d liberados; sprint encurtado de 10 → 7) |
| S11 | 11 | +testes Stripe (+1d) |
| S12 | 8 | 5 → 8 dias (+3d) + cenários NFR explícitos |
| **Total** | **127** | +7 dias vs plano original |

---

## 5. Riscos Residuais (Após Correções)

| Risco | Probabilidade | Impacto | Mitigação |
|-------|-------------|---------|----------|
| Aprovação TP demorar > 4 semanas | Média | Alto (bloqueia S06) | Contatar TP no D01; usar mock API local como fallback de dev |
| Prompt engineering do agente insuficiente em S05 | Alta | Alto (core do produto) | Reservar últimos 3 dias de S05 como buffer de ajuste fino |
| WeasyPrint com quirks de CSS complexo (S10) | Média | Médio | Usar template simples; testar renderização PDF desde o início de S10 |
| Stripe rejeitando conta PF | Baixa | Alto | Se PF for rejeitado, abrir MEI (custo: ~R$60/ano) — iniciar verificação cedo |
| APScheduler falhando silenciosamente em Railway | Média | Alto | Adicionar endpoint de health check que retorna status do último job; alertar se > 26h sem execução |

---

## 6. Veredicto

**Plano aprovado com 12 correções obrigatórias.**

- ✅ Todas as 38 stories cobertas
- ✅ Dependências entre sprints corretamente sequenciadas (após correção #1)
- ✅ NFRs cobertos no plano (após correção de testes e S12 expandido)
- ✅ Estimativa realista (127 dias, dentro do range do PRD)
- ⚠️ Aplicar as 4 correções 🔴/🟠 antes de iniciar o desenvolvimento

**Pré-requisitos para iniciar o Sprint 01:**
1. Criar conta Stripe e iniciar KYC
2. Solicitar acesso à API TrainingPeaks
3. Aplicar migration `002_missing_tables.sql` ao spec-v1
4. Mover US-034 para S05 no sprint-plan.md

---

*Próxima fase: Coder ↺ Evaluator (Fases 10–11) — implementação iterativa sprint a sprint*
