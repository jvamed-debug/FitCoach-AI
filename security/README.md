# Security Master — FitCoach AI

Gate de segurança para cinco falhas recorrentes em aplicações aceleradas por IA.
Ele complementa SECURITY.md; não substitui revisão de arquitetura, testes de
autorização nem pentest autenticado.

## Cobertura

| Risco | Controle no FitCoach |
|---|---|
| RLS/Data API | migrations verificadas; policies por usuário/gestor e tabelas server-only sem grants para clientes |
| Autorização no frontend | decisões de papel permanecem no backend e no banco; flags da UI são somente UX |
| IDOR/BOLA | heurísticas em rotas e revisão obrigatória de queries por ID/ownership |
| Segredos | .env ignorado, CI e Gitleaks opt-in; service_role é somente server-side |
| Input, upload e abuso | validação Pydantic, revisão de upload e de rate limiting para auth/IA/webhooks |

## CI

O CI roda análise estática sem instalar ferramentas ou fazer tráfego de rede
para o aplicativo:

    python scripts/security_master.py --target . --fail-on critical

O relatório local fica em security-artifacts/security-master-report.json e é
ignorado pelo Git. Ele omite valores de segredos, snippets e payloads HTTP.

## Scanners externos — opt-in

Em ambiente aprovado, com versões e imagens deliberadamente geridas:

    python scripts/security_master.py \
      --target . \
      --run-tools \
      --require-tools \
      --opengrep-rules security/opengrep-security-master.yml \
      --fail-on high

O comando usa somente binários já instalados: Gitleaks, Bandit (Python) e
Opengrep. Para uma auditoria de segredos no histórico, trate cada achado de
Gitleaks como potencial vazamento e revogue a credencial antes de removê-la.

## ZAP

Nenhum scan dinâmico é iniciado por padrão. O baseline passivo exige URL de
staging explicitamente autorizada, confirmação literal
I_AUTHORIZE_BASELINE_SCAN e imagem aprovada fixada por digest:

    python scripts/security_master.py \
      --target . \
      --run-tools \
      --zap-baseline-url https://staging.exemplo.com \
      --zap-authorization I_AUTHORIZE_BASELINE_SCAN \
      --zap-image registry.exemplo/zap@sha256:<digest>

Nunca use contra produção ou dados reais sem escopo formal.

## Verificação pós-deploy da migration

A migration 007_security_master_hardening.sql precisa ser aplicada no projeto
Supabase correto por fluxo aprovado. Depois, valide com dois usuários reais de
teste (dois atletas e dois gestores): leitura, inserção, atualização e exclusão
devem falhar entre usuários/tenants diferentes. Confirme também que tabelas
server-only não são acessíveis via Data API com chave publishable/anon.
