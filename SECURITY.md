# Segurança — FitCoach AI

Aplicação de coaching esportivo que processa **dados pessoais sensíveis de saúde**
(métricas fisiológicas, HRV, peso, sono) sob a **LGPD**. Este documento descreve o
modelo de ameaças, as fronteiras de confiança e os requisitos de produção.

## Fronteiras de confiança

| Fronteira | Dados que cruzam | Controle principal |
|---|---|---|
| Navegador/PWA → API | JWT Supabase, payloads de treino e métricas | HTTPS, verificação de assinatura JWT (`SUPABASE_JWT_SECRET`), RLS |
| API → Supabase/Postgres | dados de atletas, tokens OAuth, anamnese | RLS por atleta/admin, `service_key` só no backend |
| API → Strava / TrainingPeaks | `access_token` / `refresh_token` OAuth | tokens **criptografados** (Fernet) em `platform_connections`; refresh automático |
| API → Anthropic / OpenAI | contexto do atleta (sem PII desnecessária) | chave server-side, contexto mínimo, resposta parseada |
| API → Stripe | eventos de assinatura | verificação de **assinatura HMAC** do webhook + idempotência (`webhook_events`) |
| Strava → API (webhook) | notificações de atividade | validação de **HMAC** e `verify_token` |
| Convite de atleta (e-mail) | token de convite | **HMAC-SHA256** com `SECRET_KEY`, expiração |

## Ameaças prioritárias

- **Exposição de segredos** — `.env` ignorado no Git; CI rejeita chaves commitadas
  (job `secrets-scan`); nunca logar tokens, chaves ou corpos de requisição em produção.
- **Vazamento de dados de saúde (LGPD)** — RLS garante que cada atleta só acessa os
  próprios dados; admin só acessa atletas sob sua gestão; consentimento obrigatório
  antes de qualquer dado sensível; export e exclusão de dados suportados.
- **Roubo de token OAuth** — `access_token`/`refresh_token` de Strava/TP são
  criptografados em repouso (Fernet, `DB_ENCRYPTION_KEY`); nunca retornados ao cliente.
- **Anamnese sensível** — criptografada com `pgcrypto`/`pgp_sym_encrypt` no banco.
- **Forjação de webhook** — Stripe e Strava validados por HMAC antes de qualquer efeito;
  eventos Stripe deduplicados por `webhook_events` (idempotência).
- **Autorização entre papéis** — endpoints de escrita exigem JWT válido; separação
  estrita admin × atleta; limite de atletas por plano aplicado no servidor (HTTP 402).
- **Brute force / abuso** — recomendado rate limiting no proxy/borda em produção.
- **Prompt injection na IA** — dados do atleta entram como contexto delimitado; a IA
  gera propostas de treino, **sem** autoridade para executar ações ou alterar dados.

## Requisitos de produção

- HTTPS obrigatório; headers defensivos (CSP, HSTS) no frontend/borda.
- Segredos apenas em variáveis de ambiente do provedor (Railway/Vercel), nunca no código.
- `DB_ENCRYPTION_KEY`, `SECRET_KEY`, `SUPABASE_JWT_SECRET` com entropia ≥ 32 chars.
- Rotação periódica de chaves e tokens OAuth; revogar conexões inativas.
- Backup do banco Supabase; RLS habilitado em todas as tabelas com dados de atleta.
- Rate limiting adicional no proxy para endpoints de auth e geração de IA.
- Revisão de segurança antes de habilitar qualquer nova integração externa.

## Divulgação de vulnerabilidades

Relate por canal privado ao mantenedor. **Não** publique segredos, tokens ou dados
de usuários em issues ou pull requests. Se uma chave for exposta, **rotacione-a
imediatamente** — remover do histórico do Git não a torna segura novamente.
