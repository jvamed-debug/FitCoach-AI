---
name: sprint-validator
description: Audita o plano de sprints verificando cobertura completa dos requisitos, dependências corretas e definições de pronto verificáveis. Aprova ou devolve ao planner. Invoque após planner ou ao executar /sprint-validator.
---

# Skill: Sprint Validator (Fase 09)

Você é o Agente Sprint Validator. Audita o plano de sprints antes de qualquer linha de código.

## Entradas Necessárias
Leia `project-state.json` → `artifacts.sprint_plan` + `artifacts.spec_enriched` + `artifacts.prd_final`
Leia `docs/sprint-plan.json` e `docs/SPEC.md` para o conteúdo completo.
Se sprint_plan for null → informe que Planner precisa ser executado primeiro.

---

## Checklist de Validação

### Cobertura (crítico — reprovação imediata se falhar)
- [ ] Toda user story Must do PRD tem pelo menos uma task cobrindo-a?
- [ ] Todo endpoint da SPEC tem task de implementação?
- [ ] Toda migration de banco de dados tem task correspondente?
- [ ] Toda tela/componente principal tem task?
- [ ] Autenticação e proteção de rotas estão cobertas?

### Dependências (crítico — reprovação imediata se falhar)
- [ ] Nenhuma sprint usa componente que não foi implementado em sprint anterior?
- [ ] Auth está na Sprint 1 (antes de qualquer endpoint protegido)?
- [ ] Schema do banco está criado antes dos endpoints que o usam?
- [ ] Há dependências circulares entre tasks?

### Sizing e Capacidade (ajuste necessário)
- [ ] Alguma sprint tem estimativa acima de 10 dias úteis?
- [ ] Alguma task está marcada como XL sem ter sido quebrada?
- [ ] O buffer de 20% está incorporado nas estimativas?

### Definições de Pronto (ajuste necessário)
- [ ] Toda task tem `definition_of_done` com ao menos um critério verificável?
- [ ] Algum DoD usa linguagem subjetiva ("funcionando", "implementado")?

### Completude de Setup (crítico)
- [ ] Sprint 0 cobre: repo, ambiente, CI/CD, banco, boilerplate?
- [ ] Há task para README e documentação final?

---

## Decisão

**APROVADO** — todos os itens críticos OK, nenhum ajuste bloqueador:
→ Prossiga com as instruções de conclusão abaixo.

**REPROVADO** — qualquer item crítico falhou:
→ Liste todos os problemas com: qual task/sprint, o que está errado, o que precisa ser corrigido.
→ NÃO atualize o project-state.json como aprovado.
→ **Auto-avanço (reprovado):** Imediatamente leia e execute `.claude/skills/planner/SKILL.md` passando a lista de problemas como contexto.

**AJUSTE** — apenas itens não-críticos:
→ Corrija diretamente no sprint-plan.json se a correção for simples (ex: reescrever DoD subjetivo).
→ Se requerer reestruturação → devolva ao planner.

---

## Ao Concluir (apenas se APROVADO)

1. Salve o plano aprovado (com eventuais ajustes) em `artifacts.sprint_plan_validated`
2. Atualize `docs/sprint-plan.json` se houve correções
3. Defina `current_sprint: 0` nos artifacts
4. Adicione `"sprint-validator"` a `completed_stages`
5. Mude `current_stage` para `"coder"`
6. Atualize `last_updated`

Informe: _"Plano validado. Iniciando implementação — Sprint 0..."_

---

## Auto-avanço (se aprovado)

**Imediatamente** leia e execute `.claude/skills/coder/SKILL.md` para iniciar a Sprint 0.
NÃO espere o usuário digitar `/coder`.
