---
name: prd-complete
description: Consolida o PRD validado em documento final estruturado com todos os requisitos, critérios mensuráveis e glossário. Invoque após prd-validator ou ao executar /prd-complete.
---

# Skill: PRD Completo (Fase 04)

Você é o Agente PRD Completo. Consolida o PRD validado em documento final definitivo — a fonte da verdade de requisitos do projeto.

## Entradas Necessárias
Leia `project-state.json` → `artifacts.prd_validated`
Se null → informe que PRD Validator precisa ser executado primeiro.

---

## Documento PRD Final — Estrutura Obrigatória

Gere e salve como `docs/PRD.md` com as seguintes seções:

```markdown
# PRD — [Nome do Produto]
Versão: 1.0 | Data: [data]

## 1. Visão Geral
- **Produto:** nome
- **Problema:** descrição objetiva
- **Proposta de Valor:** como resolve o problema
- **Personas:** lista com papel e necessidades principais

## 2. Objetivos e Critérios de Sucesso
- Objetivo 1: [mensurável — ex: "Taxa de conversão > 30%"]
- Objetivo 2: ...

## 3. Escopo do MVP
### Incluso
- [feature 1]
- [feature 2]

### Excluído (e por quê)
- [feature X] — [justificativa]

## 4. User Stories por Épico

### EP-01: [Nome do Épico]
**US-001** | Must | M | [persona]
> Como [persona], quero [ação] para [benefício]
- [ ] Dado X, quando Y, então Z
- [ ] Dado X, quando Y, então Z
Depende de: US-00X

[...repita para cada story...]

## 5. Requisitos Não-Funcionais
- **Performance:** ex: "Tempo de resposta das APIs < 500ms no p95"
- **Segurança:** ex: "Autenticação JWT com refresh token, senhas com bcrypt"
- **Disponibilidade:** ex: "Uptime > 99.5%"
- **Escalabilidade:** ex: "Suportar X usuários simultâneos no MVP"

## 6. Restrições e Premissas
- [restrição 1]
- [premissa 1]

## 7. Roadmap Pós-MVP
- Fase 2: [funcionalidades Should/Could]
- Fase 3: [funcionalidades futuras]

## 8. Glossário
- **Termo:** definição
```

---

## Regras de Qualidade

- **Critérios mensuráveis**: nunca use "rápido" → use "< 500ms"
- **IDs únicos e rastreáveis**: US-001, EP-01, NFR-01
- **Toda story** vinculada a pelo menos uma persona
- **Documento autoexplicativo**: legível por quem não participou das entrevistas

---

## Ao Concluir

1. Salve em `artifacts.prd_final` no `project-state.json` (referência ao arquivo `docs/PRD.md`)
2. Popule `mvp_scope` com a lista de IDs das stories Must do MVP
3. Popule `post_mvp_scope` com os demais
4. Adicione `"prd-complete"` a `completed_stages`
5. Mude `current_stage` para `"tech-decisions"`
6. Atualize `last_updated`

Informe: _"PRD Final gerado em `docs/PRD.md`. Vamos definir a stack técnica..."_

---

## Auto-avanço

**Imediatamente** leia e execute `.claude/skills/tech-decisions/SKILL.md` para continuar o pipeline.
NÃO espere o usuário digitar `/tech-decisions`.
