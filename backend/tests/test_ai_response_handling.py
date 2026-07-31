"""
Testes das duas funções que codificam bugs já vividos em produção.

Ambos os bugs tinham o mesmo sintoma — a recomendação virava "dia de descanso"
sem erro visível — e causas totalmente diferentes. Os testes existem para que a
terceira ocorrência falhe na CI em vez de na tela do atleta.
"""

from __future__ import annotations

import pytest

from app.services.ai_service import _first_text, _is_config_error


class Block:
    """Dublê de um content block da Anthropic."""

    def __init__(self, type_: str, text: str | None = None):
        self.type = type_
        if text is not None:
            self.text = text


class ThinkingBlock:
    """Bloco de raciocínio real: não tem atributo `text` nenhum."""

    type = "thinking"

    def __init__(self, thinking: str):
        self.thinking = thinking


# ── _first_text ───────────────────────────────────────────────────────────────

def test_extrai_texto_com_thinking_na_frente():
    """
    O caso que quebrou produção: nos modelos atuais o raciocínio vem ligado por
    padrão e ocupa os primeiros blocos, então content[0] não é o texto.
    """
    blocks = [ThinkingBlock("deixa eu pensar..."), Block("text", '{"workout_type": "rest"}')]
    assert _first_text(blocks) == '{"workout_type": "rest"}'


def test_indexar_em_zero_quebraria():
    """Prende a razão de _first_text existir: content[0].text levanta erro."""
    blocks = [ThinkingBlock("..."), Block("text", "ok")]
    with pytest.raises(AttributeError):
        _ = blocks[0].text


def test_concatena_multiplos_blocos_de_texto():
    blocks = [Block("text", '{"a": 1,'), Block("text", ' "b": 2}')]
    assert _first_text(blocks) == '{"a": 1, "b": 2}'


def test_ignora_blocos_nao_textuais():
    blocks = [ThinkingBlock("x"), Block("tool_use"), Block("text", "só isto")]
    assert _first_text(blocks) == "só isto"


@pytest.mark.parametrize("entrada", [[], None, [ThinkingBlock("só raciocínio")]])
def test_sem_texto_devolve_string_vazia(entrada):
    """Nunca levanta — quem chama trata string vazia como parse failure."""
    assert _first_text(entrada) == ""


# ── _is_config_error ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("exc", [
    TypeError("unexpected keyword argument 'output_config'"),  # SDK desatualizado
    AttributeError("'ThinkingBlock' object has no attribute 'text'"),
    NameError("name 'settings' is not defined"),
    ImportError("cannot import name 'AsyncAnthropic'"),
])
def test_erros_de_codigo_sao_classificados_como_configuracao(exc):
    assert _is_config_error(exc) is True


@pytest.mark.parametrize("exc", [
    ConnectionError("connection reset"),
    TimeoutError("read timeout"),
    RuntimeError("Anthropic recusou a requisição (stop_reason=refusal)"),
    ValueError("resposta ilegível"),
])
def test_falhas_transitorias_nao_sao_configuracao(exc):
    """Estas justificam retry/fallback; as de configuração não."""
    assert _is_config_error(exc) is False
