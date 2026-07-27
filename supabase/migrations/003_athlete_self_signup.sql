-- 003 — Auto-cadastro de atleta (B2C)
-- Atletas que se cadastram sozinhos não têm treinador. admin_id passa a ser
-- opcional; quando um treinador é removido, os atletas dele ficam sem treinador
-- (SET NULL) em vez de bloquear a remoção.

ALTER TABLE athletes
    ALTER COLUMN admin_id DROP NOT NULL;

-- Ajusta a ação de FK de RESTRICT para SET NULL.
ALTER TABLE athletes
    DROP CONSTRAINT IF EXISTS athletes_admin_id_fkey;

ALTER TABLE athletes
    ADD CONSTRAINT athletes_admin_id_fkey
    FOREIGN KEY (admin_id) REFERENCES admin_users(id) ON DELETE SET NULL;

-- Índice para consultar atletas autônomos (sem treinador).
CREATE INDEX IF NOT EXISTS idx_athletes_self_serve
    ON athletes(id) WHERE admin_id IS NULL;
