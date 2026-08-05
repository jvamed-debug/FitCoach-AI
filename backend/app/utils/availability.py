"""
Disponibilidade semanal: quais modalidades em quais dias, e por quanto tempo.

O campo `weekly_availability` nasceu como {"cycling": ["tue","thu","sat"]} — só
dias, sem duração. Prescrever sem saber o tempo disponível produz o erro mais
comum e mais irritante: um treino de 90 min num dia em que o atleta tem 40.

Este módulo aceita as DUAS formas. A antiga continua válida (há dados em
produção com ela) e a nova acrescenta minutos:

    {"cycling": ["tue", "thu"]}                        # legado
    {"cycling": {"days": ["tue", "thu"], "minutes": 90}}   # com duração

Migração por leitura, não por escrita: nada precisa ser reescrito no banco.
"""

from __future__ import annotations

from datetime import date

# Ordem ISO: segunda = 0, para casar com date.weekday().
DIAS_ISO = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

DIA_PT = {
    "mon": "segunda-feira", "tue": "terça-feira", "wed": "quarta-feira",
    "thu": "quinta-feira", "fri": "sexta-feira", "sat": "sábado", "sun": "domingo",
}


def weekday_key(d: date) -> str:
    """Devolve a chave de três letras usada em weekly_availability."""
    return DIAS_ISO[d.weekday()]


def normalize(weekly: dict | None) -> dict[str, dict]:
    """
    Normaliza qualquer das duas formas para {modalidade: {days, minutes}}.

    `minutes` é None quando o atleta não informou — e None significa "não
    declarado", nunca "sem limite". O agente é instruído a tratar os dois
    diferente: sem duração declarada ele usa o histórico; com duração, ela é
    um teto.
    """
    if not weekly:
        return {}

    saida: dict[str, dict] = {}
    for modalidade, valor in weekly.items():
        if isinstance(valor, dict):
            dias = [d for d in (valor.get("days") or []) if d in DIAS_ISO]
            minutos = valor.get("minutes")
            minutos = int(minutos) if isinstance(minutos, (int, float)) and minutos > 0 else None
        elif isinstance(valor, (list, tuple)):
            dias = [d for d in valor if d in DIAS_ISO]
            minutos = None
        else:
            continue
        if dias:
            saida[modalidade] = {"days": dias, "minutes": minutos}
    return saida


def scheduled_for(weekly: dict | None, dia: date) -> list[dict]:
    """
    O que está agendado para uma data específica.

    Devolve [{modality, minutes}] — vazio quando o dia não tem nada marcado,
    o que é informação útil por si só: um dia livre sugere descanso ou
    mobilidade, não uma sessão inventada.
    """
    chave = weekday_key(dia)
    return [
        {"modality": modalidade, "minutes": cfg["minutes"]}
        for modalidade, cfg in normalize(weekly).items()
        if chave in cfg["days"]
    ]


def describe_for_prompt(weekly: dict | None, dia: date) -> list[str]:
    """Linhas prontas para o prompt, na perspectiva do dia da sessão."""
    linhas: list[str] = []
    normalizado = normalize(weekly)
    if not normalizado:
        return linhas

    linhas.append("Weekly availability (declared by the athlete):")
    for modalidade, cfg in normalizado.items():
        dias = ", ".join(cfg["days"])
        janela = f" — up to {cfg['minutes']} min" if cfg["minutes"] else " — duration not declared"
        linhas.append(f"  {modalidade}: {dias}{janela}")

    agendado = scheduled_for(weekly, dia)
    if agendado:
        partes = [
            f"{a['modality']}" + (f" ({a['minutes']} min)" if a["minutes"] else "")
            for a in agendado
        ]
        linhas.append(f"Scheduled for this day: {', '.join(partes)}")
    else:
        linhas.append(
            "Scheduled for this day: NOTHING. The athlete did not mark this "
            "weekday for any modality — prefer rest, mobility, or a short "
            "optional session, and say why."
        )
    return linhas
