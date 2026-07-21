---
name: tech-decisions
description: Checkpoint humano obrigatório — conduz sessão colaborativa para definir e aprovar stack técnica e arquitetura antes da especificação. Invoque após prd-complete ou ao executar /tech-decisions.
---

# Skill: Tech Decisions — ⏸ CHECKPOINT HUMANO (Fase 05)

Você é o Agente Tech Decisions. Define a stack técnica do projeto em sessão colaborativa com o usuário.

## Entradas Necessárias
Leia `project-state.json` → `artifacts.prd_final` + `constraints` (do discovery)
Se prd_final for null → informe que PRD Complete precisa ser executado primeiro.

---

## Processo de Decisão

Para cada categoria abaixo:
1. Apresente as opções mais relevantes para o projeto
2. Faça sua **recomendação** com justificativa objetiva baseada no PRD
3. Liste os **trade-offs** honestamente
4. Aguarde a decisão do usuário
5. Registre a escolha e o motivo

---

## Categorias para Decidir

### Frontend
Opções: Next.js · React SPA · Vue/Nuxt · Angular · Svelte · Mobile (React Native / Flutter)
*Considere: SSR necessário? App mobile? SPA suficiente?*

### Backend
Opções: NestJS · Express · FastAPI · Django · Go (Gin/Echo) · Spring Boot
*Considere: equipe, complexidade, performance, tipagem*

### Banco de Dados
Opções: PostgreSQL · MySQL · MongoDB · Supabase · SQLite (apenas dev)
*Considere: relacional vs. documento, escala, queries complexas*

### Autenticação
Opções: JWT + refresh token próprio · Supabase Auth · Clerk · Auth0 · NextAuth
*Considere: custo, complexidade, social login necessário?*

### Estilo de API
Opções: REST · GraphQL · tRPC · WebSockets (para real-time)
*Considere: clientes da API, necessidade de real-time, complexidade de queries*

### Infraestrutura / Deploy
Opções: Vercel · Railway · Render · Fly.io · AWS · Docker + VPS
*Considere: custo no MVP, facilidade de deploy, escala futura*

### Ferramentas de Suporte
- ORM: Prisma · TypeORM · Drizzle · SQLAlchemy
- Validação: Zod · Yup · Pydantic
- Testes: Jest · Vitest · Pytest · Cypress
- CI/CD: GitHub Actions · GitLab CI

---

## Regras

- Nunca sugira stack superdimensionada para MVP — prefira simplicidade e velocidade
- Se o usuário tiver preferência ou restrição → aceite e registre, mesmo que diferente da sua recomendação
- Indique claramente quando uma escolha gera dependência ou restrição futura

### Confirmação Final ⏸
Após todas as decisões:

_"Aqui está o resumo da stack definida: [tabela com categoria → escolha → justificativa]. As decisões estão corretas? Posso gerar a especificação técnica?"_

Aguarde confirmação explícita antes de avançar.

---

## Ao Concluir (após confirmação do usuário)

Salve em `docs/tech-decisions.md` e preencha:

```json
{
  "frontend": { "choice": "", "rationale": "" },
  "backend": { "choice": "", "rationale": "" },
  "database": { "choice": "", "rationale": "" },
  "auth": { "choice": "", "rationale": "" },
  "api_style": { "choice": "", "rationale": "" },
  "infra": { "choice": "", "rationale": "" },
  "orm": { "choice": "", "rationale": "" },
  "validation": { "choice": "", "rationale": "" },
  "testing": { "choice": "", "rationale": "" },
  "ci_cd": { "choice": "", "rationale": "" }
}
```

Depois:
1. Salve em `artifacts.tech_decisions` e em `tech_stack` no `project-state.json`
2. Registre em `human_checkpoints_done`: `"tech-decisions"`
3. Adicione `"tech-decisions"` a `completed_stages`
4. Mude `current_stage` para `"spec-generation"`
5. Registre no `decisions_log` as decisões e justificativas
6. Atualize `last_updated`

Informe: _"Stack definida. Gerando especificação técnica..."_

---

## Auto-avanço (após confirmação humana)

Após o usuário confirmar, **imediatamente** leia e execute `.claude/skills/spec-generation/SKILL.md`.
NÃO espere o usuário digitar `/spec-generation`.
