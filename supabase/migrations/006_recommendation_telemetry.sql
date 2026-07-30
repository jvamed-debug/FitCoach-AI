-- Correção de schema drift: o modelo ORM AIRecommendation tem tokens_used e
-- generation_time_ms, mas a migration 001 nunca criou essas colunas. Sem elas,
-- o INSERT de /api/recommendations/generate falha com "column does not exist"
-- (erro 500 "Erro interno do servidor" ao gerar recomendação).
ALTER TABLE ai_recommendations ADD COLUMN IF NOT EXISTS tokens_used INTEGER;
ALTER TABLE ai_recommendations ADD COLUMN IF NOT EXISTS generation_time_ms INTEGER;
