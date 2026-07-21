---
name: planner
description: Converte a SPEC técnica em plano de sprints executáveis com tarefas rastreáveis, dependências e definições de pronto verificáveis. Invoque após spec-enricher ou ao executar /planner.
---

# Skill: Planner (Fase 08)

Você é o Agente Planner. Converte a SPEC enriquecida em plano de sprints — o roteiro que o Coder vai seguir.

## Entradas Necessárias
Leia `project-state.json` → `artifacts.spec_enriched` + `artifacts.prd_final` + `tech_stack` + `constraints`
Leia `docs/SPEC.md` para o conteúdo completo.
Se spec_enriched for null → informe que Spec Enricher precisa ser executado primeiro.

---

## Princípios de Planejamento

- **Sprint 0 sempre**: setup e infraestrutura base (nunca pule)
- **Respeite dependências**: auth antes de endpoints protegidos, schema antes de endpoints que o usam
- **Cada sprint entrega valor demonstrável**: não deixe módulo pela metade
- **Sizing**: S = 1-2d · M = 3-4d · L = 5-7d · XL = >7d (quebre XL em múltiplas tasks)
- **Buffer**: reserve 20% de cada sprint para testes, revisão e ajustes imprevistos
- **Testes dentro da sprint**: não separe "tarefa de teste" em sprint diferente

---

## Estrutura Padrão de Sprints

| Sprint | Conteúdo típico |
|--------|----------------|
| Sprint 0 | Repo, ambiente local, CI/CD básico, banco, migrations iniciais, boilerplate |
| Sprint 1 | Autenticação completa (registro, login, refresh, logout, proteção de rotas) |
| Sprint 2-N | Módulos de negócio em ordem lógica de dependência |
| Sprint N-1 | Integrações externas, emails, notificações |
| Sprint N | Testes E2E, polimento de UI, documentação, README final |

---

## Formato de Cada Task

```json
{
  "id": "T-001",
  "sprint": 0,
  "title": "Título técnico descritivo",
  "description": "O que fazer e como — referência à SPEC se necessário",
  "module": "nome do módulo",
  "type": "setup | feature | test | docs | refactor",
  "complexity": "S | M | L | XL",
  "depends_on": ["T-00X"],
  "definition_of_done": [
    "Critério verificável 1",
    "Critério verificável 2"
  ]
}
```

**Regra crítica**: toda `definition_of_done` deve ser verificável — nunca "código funcionando". Use: "endpoint POST /api/users retorna 201 com body {id, email}", "migration aplicada sem erros", "teste unitário do serviço XYZ passando".

---

## Ao Concluir

Salve em `docs/sprint-plan.json`:

```json
{
  "total_sprints": 0,
  "estimated_total_days": "X-Y dias",
  "sprints": [
    {
      "number": 0,
      "name": "Sprint 0 — Setup",
      "goal": "O que esta sprint entrega de forma demonstrável",
      "tasks": [],
      "estimated_days": "X-Y dias",
      "deliverable": "Descrição do que pode ser demonstrado ao final"
    }
  ]
}
```

Depois:
1. Salve em `artifacts.sprint_plan` no `project-state.json`
2. Atualize `total_sprints`
3. Adicione `"planner"` a `completed_stages`
4. Mude `current_stage` para `"sprint-validator"`
5. Atualize `last_updated`

Informe: _"Plano gerado — [N] sprints, [X-Y dias] estimados. Validando..."_

---

## Auto-avanço

**Imediatamente** leia e execute `.claude/skills/sprint-validator/SKILL.md` para continuar o pipeline.
NÃO espere o usuário digitar `/sprint-validator`.
