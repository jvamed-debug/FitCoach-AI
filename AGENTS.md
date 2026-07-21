# AGENTS.md

Convenções para agentes de IA e humanos que contribuem com o FitCoach AI.
Para o modelo de ameaças, ver [SECURITY.md](SECURITY.md).

## Stack

- **Backend:** Python 3.11+, FastAPI, SQLAlchemy 2.0 **async**, Pydantic v2, Alembic.
- **Frontend:** Next.js 14 (App Router), TypeScript, Tailwind, shadcn/ui, Zustand.
- **Dados:** PostgreSQL via Supabase (Auth + RLS). IA: Anthropic Claude + OpenAI (fallback).

## Convenções de código

- **Async em todo o backend.** Handlers FastAPI, acesso a banco e chamadas HTTP usam
  `async/await`. Nunca bloquear o event loop com I/O síncrono.
- **Tipagem explícita.** Pydantic v2 para schemas de entrada/saída; TypeScript estrito no front.
- **Sem segredos no código.** Toda configuração vem de `settings` (`app/config.py`),
  carregado de variáveis de ambiente. Nunca hardcode chaves, tokens ou URLs de provedor.
- **Nunca logar dados sensíveis** em produção: tokens OAuth, JWT, chaves, HRV/peso/saúde,
  corpos de requisição ou histórico de IA.
- **Isolamento por papel.** Toda query respeita RLS: atleta acessa só os próprios dados;
  admin acessa só atletas sob sua gestão. Novos endpoints de escrita exigem autenticação.
- **Idempotência em webhooks.** Eventos externos (Stripe, Strava) validam HMAC e
  deduplicam antes de qualquer efeito colateral.
- **Migrations versionadas.** Alterações de schema entram como migration em
  `supabase/migrations/` — nunca alterar tabelas em produção manualmente.

## Regras de negócio críticas (não quebrar)

- Cálculo de carga (CTL/ATL/TSB) segue o modelo Banister PMC — ver `app/utils/calculations.py`.
- TSS de força é limitado a 150 por sessão.
- Limite de atletas por plano é aplicado **no servidor** (HTTP 402), nunca só no cliente.
- Consentimento LGPD é obrigatório antes de processar qualquer dado sensível.

## Verificação antes de commitar

```bash
# Backend
cd backend
ruff check app/ --select=E,W,F --ignore=E501
pytest tests/ -v

# Frontend
cd frontend
npm run type-check
npm run lint
```

O CI (`.github/workflows/ci.yml`) roda `secrets-scan` → backend (lint+tests) →
frontend (type-check). Nenhum PR deve ser mesclado com o CI vermelho.

## Fora de escopo desta versão

- Agentes de IA geram **propostas** de treino; não executam ações nem alteram dados
  automaticamente. Qualquer ação com efeito externo exige revisão humana.
