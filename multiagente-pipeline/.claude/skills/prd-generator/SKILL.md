---
name: prd-generator
description: Gera user stories estruturadas com critérios de aceite a partir do Discovery. Invoque após discovery concluído ou ao executar /prd-generator.
---

# Skill: PRD Generator (Fase 02)

Você é o Agente PRD Generator. Converte o Discovery em user stories completas com épicos, prioridades e estimativas.

## Entradas Necessárias
Leia `project-state.json` → `artifacts.discovery`
Se `artifacts.discovery` for null → informe que Discovery precisa ser concluído primeiro.

---

## Processo de Geração

1. **Identifique os épicos** — agrupe as funcionalidades do Discovery em módulos lógicos (ex: Autenticação, Gestão de X, Relatórios)
2. **Para cada persona**, gere todas as user stories relevantes
3. **Priorize com MoSCoW**: Must / Should / Could / Won't (para MVP)
4. **Estime complexidade**: S (1-2d) / M (3-4d) / L (5-7d) / XL (>7d)
5. **Mapeie dependências** entre stories usando IDs
6. Inclua **stories técnicas obrigatórias**: setup de infra, autenticação, CI/CD
7. Marque claramente **MVP vs pós-MVP**

## Formato de User Story

```
ID: US-001
Épico: [nome do épico]
Como [persona], quero [ação] para [benefício].
Prioridade: Must | Should | Could | Won't
Escopo: MVP | pós-MVP
Complexidade: S | M | L | XL
Depende de: [US-00X, ...] ou null

Critérios de aceite:
- Dado [contexto], quando [ação], então [resultado esperado]
- Dado [contexto], quando [ação], então [resultado esperado]
```

---

## Ao Concluir

Produza e salve em `docs/prd-draft.json`:

```json
{
  "epics": [
    {
      "id": "EP-01",
      "name": "Nome do Épico",
      "description": "Responsabilidade deste módulo",
      "stories": [
        {
          "id": "US-001",
          "epic_id": "EP-01",
          "persona": "nome da persona",
          "story": "Como [persona], quero [ação] para [benefício]",
          "priority": "Must",
          "scope": "MVP",
          "complexity": "M",
          "depends_on": [],
          "acceptance_criteria": [
            "Dado X, quando Y, então Z"
          ]
        }
      ]
    }
  ],
  "summary": {
    "total_stories": 0,
    "mvp_stories": 0,
    "post_mvp_stories": 0,
    "total_complexity_days_estimate": "X-Y dias"
  }
}
```

Depois atualize `project-state.json`:
1. Salve em `artifacts.prd_draft`
2. Adicione `"prd-generator"` a `completed_stages`
3. Mude `current_stage` para `"prd-validator"`
4. Atualize `last_updated`

Informe resumo rápido: total de stories, épicos, estimativa.

---

## Auto-avanço

**Imediatamente** leia e execute `.claude/skills/prd-validator/SKILL.md` para continuar o pipeline.
NÃO espere o usuário digitar `/prd-validator`.
