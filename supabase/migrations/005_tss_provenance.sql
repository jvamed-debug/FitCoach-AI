-- §13 do contrato do agente: proveniência do TSS por treino.
-- Distingue MEDIDA (potência) de ESTIMATIVA (FC/TRIMP) e origem importada.
ALTER TABLE workouts ADD COLUMN IF NOT EXISTS tss_method VARCHAR(20);

COMMENT ON COLUMN workouts.tss_method IS
    'Origem do TSS: power (medida) | hr (estimativa TRIMP) | stored (importado) | strength (RPE) | NULL';
