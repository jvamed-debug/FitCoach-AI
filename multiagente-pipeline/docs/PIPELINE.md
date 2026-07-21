# Pipeline Multiagente — Guia de Uso

## Como Iniciar

1. Abra o Claude Code neste diretório
2. Descreva sua ideia: _"Quero criar um sistema de agendamento para barbearias"_
3. O Coordenador (CLAUDE.md) inicia automaticamente o Discovery
4. Responda as perguntas e o pipeline flui sozinho até os checkpoints

## Fluxo

| # | Fase | Tipo | O que faz |
|---|------|------|-----------|
| 01 | discovery | Entrevista | 5 blocos de perguntas estruturadas |
| 02 | prd-generator | Auto | Gera user stories e requisitos |
| 03 | prd-validator | **⏸ Checkpoint** | Valida PRD com você |
| 04 | prd-complete | Auto | Consolida PRD final |
| 05 | tech-decisions | **⏸ Checkpoint** | Define stack com você |
| 06 | spec-generation | Auto | Gera SPEC técnica |
| 07 | spec-enricher | Auto | Adiciona edge cases |
| 08 | planner | Auto | Gera plano de sprints |
| 09 | sprint-validator | Auto | Valida o plano |
| 10 | coder | Loop | Implementa sprint |
| 11 | evaluator | Loop | Avalia entrega |
| 12 | acceptance-reviewer | Final | Revisão macro |

## Artefatos Produzidos

| Arquivo | Conteúdo |
|---------|----------|
| `project-state.json` | Estado e memória do pipeline (criado automaticamente) |
| `docs/discovery.json` | Resultado da entrevista |
| `docs/prd-draft.json` | Requisitos gerados |
| `docs/PRD.md` | PRD final validado |
| `docs/tech-decisions.md` | Decisões técnicas |
| `docs/SPEC.md` | Especificação técnica completa |
| `docs/sprint-plan.json` | Plano de implementação |
| `docs/acceptance-report.md` | Relatório final |

## Retomando Sessão

Feche e abra o Claude Code — o Coordenador lê `project-state.json` e retoma de onde parou.

## Comandos Manuais

Use `/status` para ver o estado. Use `/nome-da-fase` para executar ou repetir uma fase.
