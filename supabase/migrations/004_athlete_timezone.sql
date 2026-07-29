-- 004 — Fuso horário do atleta (§8.8 do contrato do agente)
-- O agrupamento diário de carga (CTL/ATL/TSB) deve usar a data LOCAL do atleta,
-- não UTC. Persistimos o fuso IANA no perfil.

ALTER TABLE athletes
    ADD COLUMN IF NOT EXISTS timezone VARCHAR(64) DEFAULT 'America/Sao_Paulo';

-- Preenche os já existentes com o padrão.
UPDATE athletes SET timezone = 'America/Sao_Paulo' WHERE timezone IS NULL;
