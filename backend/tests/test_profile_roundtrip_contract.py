"""
Simetria entre leitura e escrita do perfil.

O invariante: todo campo que um formulário ENVIA precisa VOLTAR na leitura.
Quebrá-lo causa perda silenciosa de dados — a tela carrega o valor atual, o
usuário edita outro campo, e o formulário reenvia como vazio o que nunca
recebeu.

Foi exatamente o que aconteceu: `weekly_availability` e `goal` eram aceitos
pelo PUT /api/auth/me mas não devolvidos pelo GET, então o primeiro "salvar"
na tela de Configurações apagaria a disponibilidade já gravada.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.routers.auth import ProfileUpdateRequest

_AUTH_PY = Path(__file__).resolve().parent.parent / "app" / "routers" / "auth.py"


def _chaves_da_resposta_do_atleta() -> set[str]:
    """
    Extrai as chaves do dict de resposta do atleta em get_me().

    Lê a AST em vez de chamar a função porque montá-la exigiria banco e
    autenticação — e o que interessa aqui é o contrato, não a execução.
    """
    arvore = ast.parse(_AUTH_PY.read_text(encoding="utf-8"))
    fn = next(
        n for n in ast.walk(arvore)
        if isinstance(n, ast.AsyncFunctionDef) and n.name == "get_me"
    )
    # O último `return` de get_me é o do atleta — o do admin retorna antes.
    # Percorrer por `ast.walk` e pegar o último Dict não serve: a ordem de walk
    # é por largura e pega dicts aninhados de outros pontos da função.
    returns = [
        n for n in ast.walk(fn)
        if isinstance(n, ast.Return) and isinstance(n.value, ast.Dict)
    ]
    assert returns, "get_me deveria retornar um dict literal"
    ultimo = max(returns, key=lambda n: n.lineno).value
    return {
        k.value for k in ultimo.keys
        if isinstance(k, ast.Constant) and isinstance(k.value, str)
    }


# Campos que o atleta edita nas telas (Configurações e onboarding). Cada um
# precisa voltar no GET, senão a tela os reenvia vazios.
CAMPOS_EDITAVEIS_PELO_ATLETA = {
    "ftp_watts", "max_hr", "resting_hr", "goal",
    "weekly_availability", "weight_kg", "height_cm", "timezone",
}


@pytest.mark.parametrize("campo", sorted(CAMPOS_EDITAVEIS_PELO_ATLETA))
def test_campo_editavel_volta_na_leitura(campo):
    assert campo in _chaves_da_resposta_do_atleta(), (
        f"'{campo}' é aceito pelo PUT /api/auth/me mas não volta no GET. "
        f"A tela carregaria vazio e o primeiro salvar apagaria o valor gravado."
    )


def test_campos_editaveis_sao_aceitos_pelo_put():
    """A outra ponta: o endpoint precisa aceitar o que a tela envia."""
    aceitos = set(ProfileUpdateRequest.model_fields)
    faltando = CAMPOS_EDITAVEIS_PELO_ATLETA - aceitos
    assert not faltando, f"PUT /api/auth/me não aceita: {sorted(faltando)}"


def test_disponibilidade_sobrevive_ao_ciclo_ler_editar_salvar():
    """
    Simula o ciclo da tela: lê o perfil, o usuário mexe só no FTP, salva.
    A disponibilidade tem de continuar lá.
    """
    from app.utils.availability import normalize

    # O que o GET devolve hoje (com a correção).
    perfil_lido = {
        "ftp_watts": 250,
        "goal": "Gran fondo",
        "weekly_availability": {"cycling": {"days": ["tue", "thu"], "minutes": 90}},
    }

    # A tela carrega no formulário e reenvia tudo, com o FTP alterado.
    enviado = ProfileUpdateRequest(
        ftp_watts=260,
        goal=perfil_lido["goal"],
        weekly_availability=perfil_lido["weekly_availability"],
    )

    assert enviado.ftp_watts == 260
    assert normalize(enviado.weekly_availability)["cycling"]["minutes"] == 90, (
        "a disponibilidade foi perdida no ciclo ler-editar-salvar"
    )
