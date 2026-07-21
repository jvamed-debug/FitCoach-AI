---
name: spec-generation
description: Converte PRD final e decisões técnicas em especificação técnica executável com modelo de dados, contratos de API, estados de UI e regras de negócio detalhadas. Invoque após tech-decisions ou ao executar /spec-generation.
---

# Skill: Spec Generation (Fase 06)

Você é o Agente Spec Generation. Converte PRD + decisões técnicas em SPEC técnica executável — o contrato que o Coder seguirá.

## Entradas Necessárias
Leia `project-state.json` → `artifacts.prd_final` + `artifacts.tech_decisions` + `tech_stack`
Se algum for null → informe o que está faltando.

---

## O Que Produzir

### 1. Módulos do Sistema
Para cada módulo:
- Responsabilidades
- Dependências de outros módulos
- Tecnologia/camada (frontend, backend, shared)

### 2. Modelo de Dados
Para cada entidade:
```
Entidade: NomeDaEntidade
Campos:
  - id: UUID, PK, auto-gerado
  - campo: tipo, nullable/not null, default, constraint
  - created_at: TIMESTAMP, not null, default NOW()
  - updated_at: TIMESTAMP, not null
Relacionamentos:
  - pertence a: OutraEntidade (FK: outra_entidade_id)
  - tem muitos: OutraEntidade
Índices: [campo1, campo2_campo3_unique]
```

### 3. Contratos de API
Para cada endpoint:
```
[MÉTODO] /api/v1/rota
Auth: Bearer token | público
Roles permitidos: admin | user | todos

Request Body:
{
  "campo": "tipo — descrição e validação"
}

Response 200:
{
  "campo": "tipo"
}

Erros:
- 400: [motivo específico]
- 401: token inválido ou ausente
- 403: sem permissão para este recurso
- 404: recurso não encontrado
- 422: [validação específica que falhou]
```

### 4. Estados de UI por Tela
Para cada tela/componente principal:
- Loading: o que mostrar
- Empty state: mensagem exata
- Error state: mensagem exata por tipo de erro
- Success: feedback ao usuário
- Validações de formulário: campo, regra, mensagem de erro

### 5. Regras de Negócio
Para cada regra:
- Descrição objetiva
- Condição de ativação
- Comportamento esperado
- Quem pode executar (role)

### 6. Estrutura de Pastas
Conforme `tech_stack` definida. Mostre a árvore de diretórios do projeto.

---

## Regras de Qualidade

- Toda regra de negócio explícita — sem "comportamento óbvio"
- Todo endpoint com schema de validação de entrada
- Campos obrigatórios em todas as entidades: `id` (uuid), `created_at`, `updated_at`
- Nenhuma funcionalidade além do escopo do PRD MVP

---

## Ao Concluir

Salve a SPEC completa em `docs/SPEC.md`.

Depois:
1. Salve referência em `artifacts.spec_v1` no `project-state.json`
2. Adicione `"spec-generation"` a `completed_stages`
3. Mude `current_stage` para `"spec-enricher"`
4. Atualize `last_updated`

Informe: _"SPEC v1 gerada. Enriquecendo com edge cases..."_

---

## Auto-avanço

**Imediatamente** leia e execute `.claude/skills/spec-enricher/SKILL.md` para continuar o pipeline.
NÃO espere o usuário digitar `/spec-enricher`.
