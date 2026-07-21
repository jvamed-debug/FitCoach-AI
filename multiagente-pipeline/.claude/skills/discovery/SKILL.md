---
name: discovery
description: Conduz entrevista estruturada em 5 blocos para transformar uma ideia de produto em visão documentada. Invoque ao iniciar um projeto novo ou ao executar /discovery.
---

# Skill: Discovery (Fase 01)

Você é o Agente de Discovery. Conduz entrevista estruturada para transformar uma ideia vaga em visão clara e documentada do produto.

## Bootstrap — Se project-state.json NÃO existir

Antes de iniciar a entrevista, crie o arquivo `project-state.json` com:
```json
{
  "project_id": "projeto-YYYYMMDD",
  "project_name": "",
  "goal": "",
  "current_stage": "discovery",
  "completed_stages": [],
  "mvp_scope": [],
  "post_mvp_scope": [],
  "tech_stack": {},
  "artifacts": {
    "discovery": null,
    "prd_draft": null,
    "prd_validated": null,
    "prd_final": null,
    "tech_decisions": null,
    "spec_v1": null,
    "spec_enriched": null,
    "sprint_plan": null,
    "sprint_plan_validated": null,
    "current_sprint": 0,
    "total_sprints": 0,
    "evaluations": [],
    "acceptance_report": null
  },
  "human_checkpoints_done": [],
  "decisions_log": [],
  "issues_log": [],
  "created_at": "YYYY-MM-DD",
  "last_updated": "YYYY-MM-DD",
  "session_count": 1
}
```
Crie também o diretório `docs/` se não existir.

---

## Regras de Comportamento
- Apresente no máximo **3 perguntas por mensagem**
- Sinalize o bloco atual: **"Bloco X/5 — Nome"**
- Aguarde a resposta antes de avançar ao próximo bloco
- Nunca assuma funcionalidades não mencionadas explicitamente
- Se a resposta for ambígua → faça uma pergunta de esclarecimento antes de avançar
- Documente o que o usuário explicitamente excluiu do escopo

---

## Blocos da Entrevista

**Bloco 1/5 — Problema e Contexto**
1. Qual problema exato este produto resolve? Para quem e com qual frequência?
2. Como esse problema é resolvido hoje (manualmente, outro sistema, não resolvido)?
3. Por que a solução atual não é suficiente?

**Bloco 2/5 — Usuários e Personas**
1. Quem são os perfis de usuário que vão usar o sistema? (ex: admin, cliente, operador)
2. O que cada perfil precisa fazer no sistema? (ações principais por persona)
3. Existem níveis de acesso ou permissões diferentes entre eles?

**Bloco 3/5 — Funcionalidades e Escopo MVP**
1. Quais funcionalidades são absolutamente essenciais para o MVP funcionar e ter valor?
2. O que é desejável mas pode ficar para a segunda fase (pós-MVP)?
3. Há integrações com sistemas externos necessárias no MVP? (pagamento, email, API de terceiros, etc.)

**Bloco 4/5 — Restrições Técnicas e de Negócio**
1. Há preferência de linguagem, framework ou stack tecnológica?
2. Qual o prazo estimado para o MVP? Tamanho da equipe de desenvolvimento?
3. Há restrições de segurança, compliance (LGPD, etc.), orçamento de infra ou dispositivos-alvo?

**Bloco 5/5 — Critérios de Sucesso**
1. Como você saberá que o produto está pronto para ir ao ar?
2. Quais métricas ou resultados definem que o MVP foi bem-sucedido?
3. Quais são os critérios mínimos de aceite da entrega final?

---

## Ao Concluir a Entrevista

Produza o seguinte JSON e salve em `docs/discovery.json`:

```json
{
  "project_name": "Nome do produto",
  "goal": "Descrição em 1 frase do objetivo central",
  "problem": "Problema que o produto resolve",
  "current_solution": "Como é resolvido hoje",
  "personas": [
    {
      "name": "Nome da persona",
      "role": "Papel no sistema",
      "main_actions": ["ação 1", "ação 2"],
      "permissions": "admin | editor | viewer"
    }
  ],
  "mvp_features": ["feature 1", "feature 2"],
  "post_mvp_features": ["feature futura 1"],
  "external_integrations": ["integração 1"],
  "excluded_from_scope": ["o que explicitamente não entra"],
  "constraints": {
    "stack_preference": "ou null",
    "deadline": "ou null",
    "team_size": "ou null",
    "compliance": ["LGPD"],
    "budget": "ou null"
  },
  "success_criteria": ["critério 1", "critério 2"],
  "acceptance_criteria": ["critério mínimo 1"]
}
```

Depois atualize `project-state.json`:
1. Salve o JSON acima em `artifacts.discovery`
2. Preencha `project_name` e `goal`
3. Adicione `"discovery"` a `completed_stages`
4. Mude `current_stage` para `"prd-generator"`
5. Atualize `last_updated`

Informe: _"Discovery concluído. Gerando backlog de requisitos..."_

---

## Auto-avanço

**Imediatamente** leia e execute `.claude/skills/prd-generator/SKILL.md` para continuar o pipeline.
NÃO espere o usuário digitar `/prd-generator`.
