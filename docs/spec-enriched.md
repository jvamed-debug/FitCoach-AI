# Spec Enriched — FitCoach AI
Versão: 1.0 | Data: 2026-04-30 | Fase: 07 — Spec Enricher

> Complementa o spec-v1.md com edge cases, validações, tratamento de erros,
> segurança por camada e casos limite do agente IA.

---

## Índice

1. [Validações por Entidade](#1-validações-por-entidade)
2. [Tratamento de Erros — Catálogo](#2-tratamento-de-erros--catálogo)
3. [Edge Cases por Módulo](#3-edge-cases-por-módulo)
4. [Segurança por Camada](#4-segurança-por-camada)
5. [Edge Cases do Agente IA](#5-edge-cases-do-agente-ia)
6. [Edge Cases do Job Diário](#6-edge-cases-do-job-diário)
7. [Edge Cases de Integrações Externas](#7-edge-cases-de-integrações-externas)
8. [Regras de Negócio Críticas](#8-regras-de-negócio-críticas)
9. [Estratégias de Retry e Fallback](#9-estratégias-de-retry-e-fallback)
10. [Conformidade LGPD — Casos Limite](#10-conformidade-lgpd--casos-limite)

---

## 1. Validações por Entidade

### 1.1 Athlete (Cadastro pelo Admin)

| Campo | Regra | Erro |
|-------|-------|------|
| `name` | 2–255 chars, apenas letras/espaços/hífens | `INVALID_NAME` |
| `email` | Formato RFC 5322, unicidade global | `EMAIL_ALREADY_EXISTS` / `INVALID_EMAIL` |
| `birth_date` | Passado, idade entre 14 e 100 anos | `INVALID_BIRTH_DATE` |
| `height_cm` | 100–250, numérico | `INVALID_HEIGHT` |
| `weight_kg` | 30–300, numérico | `INVALID_WEIGHT` |
| `sport_modalities` | Array não vazio, valores em enum permitido | `INVALID_MODALITY` |
| `weekly_availability` | Pelo menos 1 dia por modalidade declarada | `INVALID_AVAILABILITY` |
| `fitness_level` | `beginner` \| `intermediate` \| `advanced` | `INVALID_FITNESS_LEVEL` |

### 1.2 Anamnese (Dados Médicos)

| Campo | Regra | Erro |
|-------|-------|------|
| `ftp_watts` | 50–500, inteiro | `INVALID_FTP` |
| `max_hr` | 100–220, inteiro | `INVALID_MAX_HR` |
| `resting_hr` | 30–100, inteiro. Deve ser < `max_hr` | `INVALID_RESTING_HR` |
| `injuries_history` | Máx 2000 chars | `TEXT_TOO_LONG` |
| `medications` | Máx 1000 chars | `TEXT_TOO_LONG` |
| Acesso | Apenas admin autenticado. Requer confirmação de senha | `UNAUTHORIZED` / `WRONG_PASSWORD` |

### 1.3 Workout

| Campo | Regra | Erro |
|-------|-------|------|
| `start_time` | Não pode ser futuro (> now + 15min) para workouts completed | `INVALID_START_TIME` |
| `duration_seconds` | 60–86400 (1min a 24h) | `INVALID_DURATION` |
| `avg_power_watts` | 0–2000 | `INVALID_POWER` |
| `avg_heart_rate` | 30–250 | `INVALID_HEART_RATE` |
| `tss` | 0–500 por sessão (>500 = dado suspeito) | Log de warning, aceitar mas flag `data_suspicious=true` |
| `external_id` + `source` | Combinação única por atleta (previne duplicata) | Silencioso: update em vez de insert |

### 1.4 Strength Session

| Campo | Regra | Erro |
|-------|-------|------|
| `session_date` | Não pode ser futuro | `INVALID_DATE` |
| `rpe_overall` | 1–10, inteiro | `INVALID_RPE` |
| `duration_minutes` | 10–300 | `INVALID_DURATION` |
| `exercises` | Mínimo 1 exercício | `NO_EXERCISES` |
| `exercise_order` | Sequencial, sem gaps, começando em 1 | Normalizar automaticamente no backend |
| `load_kg` | 0–500 | `INVALID_LOAD` |
| `reps` | 1–100 (se informado) | `INVALID_REPS` |
| `sets` | 1–20 | `INVALID_SETS` |

### 1.5 Daily Metrics

| Campo | Regra | Erro |
|-------|-------|------|
| `metric_date` | Não pode ser futuro. Não pode ser anterior a `created_at` do atleta | `INVALID_DATE` |
| `sleep_hours` | 0–24, decimal (casas: 1) | `INVALID_SLEEP_HOURS` |
| `hrv_ms` | 1–300 | `INVALID_HRV` |
| `resting_hr` | 30–100 | `INVALID_RESTING_HR` |
| Scores subjetivos | 1–10, inteiro | `INVALID_SCORE` |
| Duplicata | Upsert por (athlete_id, metric_date) — não erro, atualiza | — |

### 1.6 Recommendation Feedback

| Campo | Regra | Erro |
|-------|-------|------|
| `rating` | 1–10 | `INVALID_RATING` |
| `rpe_actual` | 1–10 | `INVALID_RPE` |
| Timing | Só pode enviar feedback para recomendações de ontem ou hoje | `FEEDBACK_TOO_LATE` |
| Duplicata | Idempotente: segundo feedback do mesmo dia substitui o primeiro | — |

### 1.7 Subscription

| Campo | Regra | Erro |
|-------|-------|------|
| Transição de status | `active` → `suspended` → `active` \| `cancelled` (final, irreversível) | `INVALID_STATUS_TRANSITION` |
| Cancelamento | Requer `reason` (para auditoria) | `CANCELLATION_REASON_REQUIRED` |
| Múltiplas assinaturas | Atleta só pode ter 1 assinatura ativa por vez | `SUBSCRIPTION_ALREADY_ACTIVE` |

---

## 2. Tratamento de Erros — Catálogo

### 2.1 Formato Padrão de Erro

```json
{
  "error": "ERROR_CODE",
  "message": "Descrição legível por humano (português)",
  "details": { "field": "campo_afetado", "value": "valor_recebido" },
  "request_id": "uuid-para-rastreabilidade"
}
```

### 2.2 Catálogo de Códigos HTTP e Erros de Negócio

| HTTP | Código de Erro | Situação |
|------|---------------|---------|
| 400 | `VALIDATION_ERROR` | Campos inválidos — `details` lista erros por campo |
| 400 | `INVALID_DATE` | Data inválida ou fora do range permitido |
| 400 | `INVALID_STATUS_TRANSITION` | Transição de status não permitida |
| 400 | `NO_EXERCISES` | Sessão de musculação sem exercícios |
| 401 | `UNAUTHORIZED` | Token ausente, inválido ou expirado |
| 401 | `WRONG_PASSWORD` | Senha de confirmação incorreta (acesso a anamnese) |
| 403 | `FORBIDDEN` | Autenticado mas sem permissão para o recurso |
| 403 | `ATHLETE_INACTIVE` | Atleta com assinatura suspensa tentando acessar |
| 403 | `LGPD_CONSENT_REQUIRED` | Atleta não aceitou termos LGPD ainda |
| 404 | `NOT_FOUND` | Recurso não encontrado |
| 409 | `EMAIL_ALREADY_EXISTS` | Email já cadastrado no sistema |
| 409 | `RECOMMENDATION_ALREADY_EXISTS` | Já existe recomendação para hoje (use force=true) |
| 409 | `SUBSCRIPTION_ALREADY_ACTIVE` | Atleta já tem assinatura ativa |
| 422 | `FEEDBACK_TOO_LATE` | Feedback fora do prazo permitido |
| 429 | `RATE_LIMIT_EXCEEDED` | Muitas requisições — ver header Retry-After |
| 500 | `INTERNAL_ERROR` | Erro interno — logar com request_id, não expor detalhes |
| 502 | `AI_PROVIDER_ERROR` | Falha em Claude e GPT-4o simultaneamente |
| 502 | `INTEGRATION_ERROR` | Falha na API externa (Strava, TrainingPeaks) |
| 503 | `SERVICE_UNAVAILABLE` | Sistema em manutenção |
| 504 | `AI_TIMEOUT` | IA demorou mais de 30s (NFR-02) |

### 2.3 Erros Silenciosos (Log Apenas, Sem Resposta de Erro)

| Situação | Comportamento |
|---------|--------------|
| Webhook Strava com `owner_id` desconhecido | Log warning, responder 200 (Strava não deve receber 4xx) |
| Webhook Apple Health com token inválido | Log warning, responder 200 |
| Duplicata de workout por `external_id` | Update silencioso (idempotência) |
| Upsert de daily_metrics no mesmo dia | Atualiza, não cria novo |
| TSS calculado > 500 | Aceita mas seta `data_suspicious = true`, gera log warning |

---

## 3. Edge Cases por Módulo

### 3.1 Auth e Sessão

| Edge Case | Comportamento |
|-----------|--------------|
| Login com conta desativada (`is_active=false`) | 403 `ATHLETE_INACTIVE` — sem detalhes do motivo |
| Refresh token expirado (> 30 dias) | 401, forçar novo login |
| Múltiplas sessões simultâneas do atleta | Permitido (mobile + web) |
| Admin tenta acessar atleta de outro admin | 404 (não expor existência do recurso) |
| Atleta sem LGPD aceito tenta acessar qualquer rota | 403 `LGPD_CONSENT_REQUIRED` + URL de consentimento |
| Token JWT com `role=athlete` tenta rota `/admin/*` | 403 `FORBIDDEN` |
| Solicitação de reset de senha para email não cadastrado | Resposta idêntica ao email válido (previne enumeração) |

### 3.2 Cadastro de Atleta

| Edge Case | Comportamento |
|-----------|--------------|
| Admin cadastra email de atleta já existente em outro admin | 409 `EMAIL_ALREADY_EXISTS` |
| Admin inativo tenta cadastrar atleta | 403 `UNAUTHORIZED` |
| Email de boas-vindas falha no envio | Atleta criado mesmo assim. Admin vê aviso "Email não enviado — reenviar?" na tela de sucesso. Retry automático 3x. |
| Atleta clica no link de onboarding após 7 dias (expirado) | Tela de "Link expirado — solicite novo ao seu coach" |
| Atleta já concluiu onboarding e acessa link novamente | Redirect para `/dashboard` |

### 3.3 Plataformas OAuth

| Edge Case | Comportamento |
|-----------|--------------|
| Atleta cancela autorização Strava no meio do fluxo | Redirect para settings com `?error=auth_cancelled`, sem salvar |
| OAuth retorna `scope` insuficiente (sem `activity:read`) | Erro exibido: "Permissão insuficiente — autorize acesso a atividades" |
| Atleta conecta Strava que já está conectado em outro atleta | 409 — cada conta Strava pode ser vinculada a apenas 1 atleta |
| Token Strava expirado durante job diário | Tentar refresh automático. Se refresh falhar: marcar `is_active=false`, logar falha, alertar admin |
| Revogação de acesso pelo usuário diretamente no Strava | Webhook `athlete.delete` recebido → marcar conexão como inativa |
| Webhook Strava com assinatura HMAC inválida | Rejeitar silenciosamente, log de segurança |

### 3.4 Cálculo de Treino (CTL/ATL/TSB)

| Edge Case | Comportamento |
|-----------|--------------|
| Atleta novo (0 dias de histórico) | CTL=0, ATL=0, TSB=0. IA recebe flag `is_new_athlete=true` |
| Atleta sem FTP configurado | TSS calculado via TRIMP (FC). IA é informada: "FTP não configurado — TSS estimado por FC" |
| Atleta sem FC máxima configurada | TSS via TRIMP usa estimativa `220 - idade`. Warning no contexto da IA |
| Treino com power=0 e hr=0 (dado corrompido) | TSS=0 para esse treino, flag `data_suspicious=true`. Não bloquear cálculo geral |
| Intervalo de mais de 30 dias sem treino | CTL/ATL decaem naturalmente pela exponencial. Nenhuma ação especial além de flag `detraining_detected=true` no contexto IA |
| Dois treinos no mesmo dia | Somar TSS do dia antes de calcular CTL/ATL |
| Treino > 24h de duração (dado errado) | Rejeitar no import, `data_suspicious=true`, logar |

### 3.5 Relatórios PDF

| Edge Case | Comportamento |
|-----------|--------------|
| Atleta sem treinos no período | PDF gerado com seção "Nenhum treino registrado no período" em vez de gráficos vazios |
| Geração de PDF falha (WeasyPrint timeout) | Status `failed` no report, admin recebe alerta. Pode tentar novamente |
| Supabase Storage indisponível para upload | PDF gerado em memória, tentar upload 3x, se persistir: PDF enviado direto por email sem salvar storage |
| Email de envio ao atleta bounce | Log do bounce, marcar `sent_to_client=false`, notificar admin |

---

## 4. Segurança por Camada

### 4.1 Autenticação e Autorização

```
Toda requisição ao backend:
  1. Extrair JWT do header Authorization: Bearer {token}
  2. Verificar assinatura (Supabase Auth secret)
  3. Verificar expiração (access token: 24h)
  4. Extrair claims: { sub: user_id, role: "admin"|"athlete", athlete_id? }
  5. Para rotas /admin/*: verificar role == "admin"
  6. Para rotas /athletes/{id}/*: verificar que athlete_id do token == id da rota
  7. Para acesso admin a dados de atleta: verificar que athlete.admin_id == admin do token
```

### 4.2 Proteção de Dados Sensíveis

| Dado | Proteção |
|------|---------|
| Anamnese (lesões, medicamentos) | `pgp_sym_encrypt` via pgcrypto. Chave em env var, nunca no código |
| access_token / refresh_token OAuth | `pgp_sym_encrypt` na tabela. Descriptografar apenas no momento de uso |
| HRV, FC de repouso | Criptografados na camada de aplicação antes de salvar |
| Logs de job | Tokens NUNCA aparecem em logs. Usar masking: `"token": "sk-***"` |
| Logs de audit | Registrar acesso a anamnese com actor_id + timestamp + IP |
| Senhas | Gerenciadas pelo Supabase Auth (bcrypt, cost 12+) |
| Webhook tokens (Apple Health) | UUID v4 único por atleta, sem expiração mas rotacionável pelo admin |

### 4.3 Rate Limiting

| Endpoint | Limite | Janela | Resposta |
|---------|--------|--------|---------|
| `POST /auth/*/login` | 10 tentativas | 15 min por IP | 429 + bloqueio 15min |
| `POST /recommendations/generate` | 5 gerações | 24h por atleta | 429 `RATE_LIMIT_EXCEEDED` |
| `POST /workouts/sync/strava` | 10 syncs | 1h por atleta | 429 |
| `GET /admin/athletes` | 100 req | 1 min por admin | 429 |
| `POST /webhooks/strava` | 1000 req | 15 min por IP | 429 (mas Strava pode retentar) |
| `POST /health/apple-health/{token}` | 48 req | 24h por token | 200 (silencioso — não alertar atacante) |

### 4.4 Validação de Webhooks

```python
# Strava: verificar X-Strava-Signature
def verify_strava_signature(body: bytes, signature: str, client_secret: str) -> bool:
    expected = hmac.new(client_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)

# Stripe: verificar Stripe-Signature
# Usar stripe.Webhook.construct_event() — nunca verificar manualmente
```

### 4.5 Injeção e XSS

| Risco | Mitigação |
|-------|----------|
| SQL Injection | SQLAlchemy ORM com parâmetros bindados — nunca string format em queries |
| XSS em campos de texto | Sanitizar inputs com bleach antes de salvar `notes`, `goal`, `injuries_history` |
| Path Traversal em storage | Usar IDs de UUID como nomes de arquivo, nunca input do usuário |
| SSRF via integrações | Whitelist de domínios permitidos para chamadas HTTP externas |
| Clickjacking | Header `X-Frame-Options: DENY` em todas as respostas |

### 4.6 Headers de Segurança (FastAPI Middleware)

```
Strict-Transport-Security: max-age=31536000; includeSubDomains
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
Content-Security-Policy: default-src 'self'; connect-src 'self' *.supabase.co
```

---

## 5. Edge Cases do Agente IA

### 5.1 Atleta Sem Histórico de Treinos

**Contexto:** atleta novo, 0 a 6 dias de dados.

```python
# Contexto enviado à IA
{
  "is_new_athlete": True,
  "days_of_data": 3,
  "ctl": 0.0, "atl": 0.0, "tsb": 0.0,
  "recent_workouts": [],
  "note": "Atleta em início de acompanhamento. Priorizar avaliação basal e carga conservadora."
}
```

**Comportamento esperado da IA:**
- Prescrever treino de avaliação (ex: teste de FTP progressivo) ou carga muito baixa
- NÃO prescrever intervalos de alta intensidade sem histórico
- Incluir instrução para o atleta: "Treine no nível que considera confortável"

**Fallback se IA retornar plano de alta intensidade para atleta novo:**
- Detector de segurança no backend: se `is_new_athlete=True` e `structured_plan.intensity in ["hard","very_hard"]` → rejeitar resposta e reenviar prompt com instrução explícita de carga baixa

---

### 5.2 Resposta JSON Malformada da IA

**Estratégia de parse progressivo:**

```python
def parse_recommendation(raw: str) -> dict:
    # Tentativa 1: parse direto
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Tentativa 2: extrair bloco ```json ... ```
    match = re.search(r'```json\s*(.*?)\s*```', raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Tentativa 3: extrair primeiro { ... } válido
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    # Fallback: criar plano de descanso com nota de erro
    log.error("AI returned unparseable JSON", raw=raw[:500])
    return {
        "workout_type": "rest",
        "title": "Dia de Recuperação",
        "duration_minutes": 0,
        "intensity": "easy",
        "sections": [],
        "rationale": "Plano de descanso aplicado automaticamente devido a erro técnico na geração.",
        "key_metrics_considered": [],
        "cautions": ["Erro interno: plano de contingência aplicado. Admin notificado."],
        "_parse_error": True
    }
```

**Se `_parse_error=True`:** notificar admin via dashboard alert, não enviar plano às plataformas externas.

---

### 5.3 IA Principal Indisponível (Fallback GPT-4o)

```python
async def generate_with_fallback(context: AthleteContext) -> TrainingRecommendation:
    providers = [AIProvider.ANTHROPIC, AIProvider.OPENAI]

    for provider in providers:
        try:
            result = await call_provider(provider, context, timeout=30)
            return result
        except (APIError, TimeoutError) as e:
            log.warning(f"{provider} failed: {e}")
            continue

    # Ambos falharam
    raise BothProvidersFailedError("Claude e GPT-4o indisponíveis")
```

**Se ambos falharem:**
- Job diário: registrar falha no step GENERATE, continuar com próximo atleta
- Endpoint `/recommendations/generate`: retornar 502 `AI_PROVIDER_ERROR`
- Admin recebe alerta crítico no dashboard

---

### 5.4 Contexto Muito Grande para o Modelo

**Limite:** claude-sonnet-4-6 suporta 200k tokens de contexto; o contexto de atleta raramente excede 5k.

**Prevenção:** truncar `recent_workouts` para os últimos 14 treinos (em vez de 30), `recent_strength` para as últimas 7 sessões.

**Detecção:** se `len(formatted_context) > 50_000 chars` → log warning, truncar mais agressivamente.

---

### 5.5 IA Prescreve Carga Perigosa

**Detector de segurança pós-parse:**

```python
def safety_check(plan: dict, context: AthleteContext) -> list[str]:
    warnings = []

    # 1. TSB crítico mas IA prescreve treino pesado
    if context.tsb < -25 and plan["intensity"] in ["hard", "very_hard"]:
        warnings.append("SAFETY: TSB crítico mas intensidade alta prescrita")

    # 2. Atleta relatou fadiga alta mas IA prescreve qualidade
    if context.latest_metrics.get("fatigue_score", 0) >= 9:
        if plan["workout_type"] not in ["rest", "mobility"]:
            warnings.append("SAFETY: Fadiga extrema (9-10) mas não é descanso")

    # 3. Duração absurda
    if plan.get("duration_minutes", 0) > 360:
        warnings.append("SAFETY: Duração > 6h prescrita")

    return warnings
```

**Se warnings não vazios:** reenviar para a IA com instrução "CORRIJA o plano considerando: {warnings}" — uma única tentativa. Se persistir: fallback para `rest`.

---

### 5.6 Nutrição Não Gerada

**Fallback para nutrition_plan ausente:**
```python
if not recommendation.nutrition_plan:
    nutrition_plan = generate_default_nutrition(
        weight_kg=context.weight_kg,
        workout_type=recommendation.workout_type,
        tss_target=estimated_tss
    )
    # Fórmulas básicas: carbs = peso × fator_modalidade, proteína = 1.6g/kg, etc.
```

---

## 6. Edge Cases do Job Diário

### 6.1 Job Dispara Duas Vezes (Race Condition)

```python
# No início do job:
lock_key = f"daily_job_{date.today().isoformat()}"
acquired = await redis_or_db_lock(lock_key, ttl=3600)
if not acquired:
    log.info("Job já em execução ou já executado hoje. Abortando.")
    return

# Implementação sem Redis: verificar job_execution_logs
existing = await db.query(JobExecutionLog).filter(
    JobExecutionLog.job_name == "daily_update",
    JobExecutionLog.started_at >= today_start,
    JobExecutionLog.status.in_(["running", "completed"])
).first()
if existing:
    return
```

### 6.2 Atleta Deletado Durante Job

```python
try:
    await process_athlete(athlete_id)
except AthleteNotFoundError:
    log.warning(f"Atleta {athlete_id} não encontrado durante job. Pulando.")
    # Não incrementar failure_count — é estado esperado
```

### 6.3 Job Demora Mais de 10 Minutos (NFR-03)

- Timeout global do job: 15 minutos (margem de segurança sobre NFR de 10min)
- Se atingir 15min: cancelar processamento dos atletas restantes, logar quais foram pulados, alertar admin
- No próximo job (D+1): reprocessar normalmente

### 6.4 Atleta Sem Nenhuma Plataforma Conectada

```
STEP 1 (IMPORT): skip — sem plataformas para importar
STEP 2 (RECALC): executar com dados existentes no banco
STEP 3 (GENERATE): executar — IA usa apenas dados históricos
STEP 4 (SEND): skip — sem plataformas para enviar
Log: "Atleta sem integrações — plano gerado mas não enviado"
```

### 6.5 Duplicata de Treino no Import

```python
# Ao importar atividade do Strava:
existing = await db.query(Workout).filter(
    Workout.external_id == str(activity["id"]),
    Workout.source == "strava"
).first()

if existing:
    # Atualizar se dados mudaram (ex: atleta editou título no Strava)
    await update_workout(existing, activity)
else:
    await create_workout(activity, athlete_id)
```

### 6.6 Atleta com Métricas do Dia Ausentes

O agente IA recebe aviso explícito no contexto:
```json
{
  "latest_metrics": null,
  "metrics_note": "Sem métricas subjetivas para hoje. IA deve basear decisão apenas em dados objetivos de carga (CTL/ATL/TSB) e histórico de treinos."
}
```

### 6.7 Todos os Clientes Falham no Job

- Se `failure_count / total_athletes > 0.5` (> 50% de falhas): job marca status `critical_failure`
- Notificação crítica para admin via email (não só dashboard — email é mais confiável)
- Parar processamento para não gerar dados inconsistentes em massa

---

## 7. Edge Cases de Integrações Externas

### 7.1 Rate Limit da API Strava (200 req/15min, 2000 req/dia)

```python
class StravaRateLimiter:
    # Respeitar headers: X-RateLimit-Limit, X-RateLimit-Usage
    # Se X-RateLimit-Usage >= 180/15min: pausar 15min
    # Estratégia: processar atletas sequencialmente quando próximo do limite
    # Em vez de paralelo (que consumiria o rate limit em rafada)
    
    async def get_with_rate_limit(self, url, access_token):
        response = await httpx.get(url, headers={"Authorization": f"Bearer {access_token}"})
        
        usage = int(response.headers.get("X-RateLimit-Usage", "0,0").split(",")[0])
        limit = int(response.headers.get("X-RateLimit-Limit", "200,2000").split(",")[0])
        
        if usage >= limit * 0.9:  # 90% do limite
            await asyncio.sleep(900)  # esperar 15 min
        
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", "900"))
            await asyncio.sleep(retry_after)
            return await self.get_with_rate_limit(url, access_token)  # retry
        
        return response
```

### 7.2 Token Strava Expirado

```python
async def get_valid_access_token(db, connection: PlatformConnection) -> str:
    if connection.token_expires_at > datetime.utcnow() + timedelta(minutes=5):
        return decrypt(connection.access_token_enc)

    # Refrescar token
    new_tokens = await strava_service.refresh_access_token(
        decrypt(connection.refresh_token_enc)
    )

    if new_tokens:
        await update_connection_tokens(db, connection, new_tokens)
        return new_tokens["access_token"]
    else:
        # Refresh falhou (usuário revogou acesso)
        await mark_connection_inactive(db, connection)
        raise StravaTokenRefreshError(f"Token refresh failed for athlete {connection.athlete_id}")
```

### 7.3 TrainingPeaks API Indisponível

- Retry: 3 tentativas com backoff exponencial (1s, 4s, 16s)
- Se persistir: registrar `send_error` na recomendação, marcar `sent_to_trainingpeaks=False`
- Admin recebe alerta: "Falha no envio para TrainingPeaks — [nome do atleta]"
- Não bloquear restante do job

### 7.4 Webhook Strava Não Verificado (Subscription)

```python
# Durante setup inicial: Strava verifica o endpoint com GET
# O endpoint deve responder com hub.challenge

@router.get("/webhooks/strava")
async def strava_webhook_verify(
    hub_mode: str = Query(alias="hub.mode"),
    hub_challenge: str = Query(alias="hub.challenge"),
    hub_verify_token: str = Query(alias="hub.verify_token")
):
    if hub_mode == "subscribe" and hub_verify_token == settings.strava_webhook_verify_token:
        return {"hub.challenge": hub_challenge}
    raise HTTPException(403)
```

### 7.5 Apple Health — Token Comprometido

- Se admin suspeitar de uso indevido: endpoint `POST /admin/athletes/{id}/rotate-apple-health-token`
- Gera novo `apple_health_token` (UUID v4), invalida o anterior
- Admin envia novo link de Shortcut ao atleta

### 7.6 TrainingPeaks → Garmin Sync Falha

- FitCoach não tem visibilidade direta desta falha (é interna ao TrainingPeaks)
- Mitigação: incluir instruções no treino enviado ao TrainingPeaks para o atleta verificar o Garmin
- Pós-MVP: monitorar via API Garmin direta quando aprovada

---

## 8. Regras de Negócio Críticas

### 8.1 Geração de Recomendação

1. **Uma recomendação por atleta por dia.** Tentativa de gerar segunda no mesmo dia retorna 409 (a menos que `force=true` na request do admin)
2. **Recomendação gerada D-1 para execução em D.** Job de 06h gera o treino de hoje para execução naquele dia
3. **Sequência respeitada:** IMPORT → RECALC → GENERATE → SEND. Não gerar sem dados de carga atualizados
4. **Fallback de descanso:** se nenhum provider de IA responder: plano de descanso automático
5. **Nunca enviar às plataformas** se `_parse_error=True` ou `safety_check` tiver warnings não resolvidos

### 8.2 Cálculo de Carga (CTL/ATL/TSB)

1. **CTL e ATL sempre recalculados em série temporal completa** — nunca incrementais isolados (garante consistência se treino passado for corrigido)
2. **TSS mínimo de treinos planejados não executados:** 0 (não penalizar dias perdidos com TSS negativo)
3. **Dias sem treino:** TSS=0 no cálculo — CTL e ATL decaem naturalmente
4. **FTP nulo:** usar TSS via TRIMP. Registrar em `anamnese_note` para admin revisar

### 8.3 LGPD

1. **Nenhum dado pessoal em URLs** (query params, path params que não sejam UUIDs opacos)
2. **Logs de produção nunca contêm:** email, nome, dados de saúde, tokens
3. **Exclusão em cascata total:** delete em `athletes` dispara CASCADE em todas as tabelas filhas
4. **Solicitação de exclusão:** criar registro em `lgpd_deletion_requests` com deadline (now + 72h). Job verifica e executa. Confirmar por email
5. **Exportação de dados:** gerar ZIP com JSON de todos os dados do atleta. Excluir dados criptografados descriptografados (senão expõe chave)

### 8.4 Assinaturas

1. **Atleta com `subscription.status != "active"` não acessa nenhum dado** (exceto tela de "conta inativa")
2. **Cancelamento é irreversível** — para reativar: criar nova assinatura
3. **Período de carência de 3 dias** para `past_due` antes de suspender acesso (webhook `payment_failed`)
4. **Admin não pode ter sua própria conta suspensa** pelo sistema (conta admin é separada das assinaturas dos atletas)

### 8.5 Integridade Referencial

1. **Deletar atleta:** bloquear se tiver `subscription.status = "active"` (retornar 409 — cancelar antes)
2. **Deletar admin:** bloquear se tiver atletas ativos (admin deve transferir ou cancelar antes)
3. **Treinos planejados enviados às plataformas:** ao deletar `ai_recommendation`, não deletar o treino externo automaticamente (seria necessário chamar API do Strava/TP para deletar — fazer manualmente)

---

## 9. Estratégias de Retry e Fallback

### 9.1 Retry Padrão (Tenacity)

```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=16),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
)
async def call_external_api(url: str, **kwargs):
    async with httpx.AsyncClient() as client:
        return await client.get(url, timeout=30, **kwargs)
```

### 9.2 Fallback por Módulo

| Módulo | Falha | Fallback |
|--------|-------|---------|
| Claude API | Timeout ou erro 5xx | GPT-4o (1 tentativa) |
| GPT-4o | Timeout ou erro 5xx | Plano de descanso (ultimo recurso) |
| Strava send | Erro 4xx/5xx | Retry 3x; se persistir: log + alerta admin |
| TrainingPeaks send | Erro | Retry 3x; se persistir: log + alerta admin |
| Email (Resend) | Erro | Retry 3x com backoff; log se persistir |
| Supabase Storage (PDF) | Erro upload | Enviar PDF por email diretamente (sem storage) |
| Job diário (APScheduler) | Crash do processo | Railway reinicia o processo. APScheduler agenda novamente na inicialização |

### 9.3 Circuit Breaker (Pós-MVP Refinamento)

Para o MVP: retry simples com backoff exponencial é suficiente.
Pós-MVP com > 50 clientes: implementar circuit breaker por provider externo usando `tenacity` com estado compartilhado.

---

## 10. Conformidade LGPD — Casos Limite

### 10.1 Atleta Solicita Exclusão Durante Job Diário

```
Cenário: atleta solicita exclusão às 05:58h; job começa às 06:00h

Mitigação:
- Job verifica status do atleta antes de cada step
- Se lgpd_deletion_requests tiver registro pendente para o atleta: skip completo
- Exclusão agendada para ser executada após confirmação manual do admin (ou automaticamente às 23:59h do mesmo dia)
```

### 10.2 Atleta Revoga Consentimento (Sem Solicitar Exclusão)

```
Comportamento:
- Acesso ao app suspenso (403 LGPD_CONSENT_REQUIRED com opção de reaceitar)
- Job diário para de processar o atleta (status verificado no início)
- Dados mantidos por até 5 anos conforme permitido para fins de saúde (Art. 11 LGPD)
- Admin notificado: "João revogou consentimento LGPD — contato recomendado"
```

### 10.3 Exportação de Dados Pessoais

```
Conteúdo do ZIP gerado:
├── perfil.json          (dados cadastrais)
├── anamnese.json        (dados de saúde — descriptografados)
├── treinos.json         (histórico completo)
├── metricas.json        (métricas diárias)
├── recomendacoes.json   (planos gerados pela IA com rationale)
├── nutricao.json        (orientações nutricionais)
├── consentimento.json   (registro LGPD com timestamp)
└── README.txt           (explicação de cada arquivo)

Segurança:
- ZIP gerado em memória, não persistido em storage
- Link de download com validade de 1h
- Acesso ao link requer autenticação JWT do próprio atleta
- Log de auditoria gerado para cada exportação
```

### 10.4 Menor de Idade (< 18 anos)

```
Regra: aceitar cadastro de atletas a partir de 14 anos (definido na validação de birth_date).
Para menores de 18: campo obrigatório `guardian_name` + `guardian_email` no cadastro.
Consentimento LGPD deve ser aceito pelo responsável (registrado com campo guardian_id).
Dados do menor têm as mesmas proteções de dados sensíveis.
```

---

*Próxima fase: Planner (Fase 08) — plano de sprints com tarefas rastreáveis e estimativas.*
