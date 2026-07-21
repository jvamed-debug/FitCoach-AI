"""
PDF generation via WeasyPrint.

Functions:
  generate_monthly_report_pdf(db, athlete_id, year, month) -> bytes
  generate_lgpd_export_pdf(db, athlete_id)                 -> bytes

Both return raw PDF bytes ready to be streamed or base64-encoded for email.
"""

from __future__ import annotations

import base64
import logging
from datetime import date, datetime
from calendar import monthrange

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete
from app.models.workout import Workout
from app.models.strength import StrengthSession, StrengthExercise
from app.models.metric import DailyMetric
from app.models.recommendation import AIRecommendation
from app.models.training_load import TrainingLoad

logger = logging.getLogger(__name__)

# ── Shared CSS ────────────────────────────────────────────────────────────────

_BASE_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, 'Helvetica Neue', Arial, sans-serif;
       font-size: 12px; color: #1a1a1a; background: white; padding: 32px; }
h1 { font-size: 22px; color: #0284c7; margin-bottom: 4px; }
h2 { font-size: 15px; color: #374151; margin: 24px 0 10px; border-bottom: 1px solid #e5e7eb;
     padding-bottom: 6px; }
h3 { font-size: 13px; color: #374151; margin: 16px 0 6px; }
p  { line-height: 1.5; color: #374151; margin-bottom: 8px; }
.subtitle { color: #6b7280; font-size: 12px; margin-bottom: 2px; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 4px;
         font-size: 10px; font-weight: 700; }
.badge-green  { background: #d1fae5; color: #065f46; }
.badge-orange { background: #ffedd5; color: #9a3412; }
.badge-red    { background: #fee2e2; color: #991b1b; }
.badge-blue   { background: #dbeafe; color: #1e40af; }
table { width: 100%; border-collapse: collapse; margin-bottom: 16px; font-size: 11px; }
th { text-align: left; background: #f3f4f6; padding: 6px 8px;
     color: #6b7280; font-weight: 600; font-size: 10px; text-transform: uppercase; }
td { padding: 6px 8px; border-bottom: 1px solid #f3f4f6; }
tr:last-child td { border-bottom: none; }
.kpi-grid { display: flex; gap: 12px; margin: 16px 0; flex-wrap: wrap; }
.kpi { background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px;
       padding: 12px 16px; min-width: 110px; }
.kpi-label { font-size: 10px; color: #6b7280; text-transform: uppercase; font-weight: 600; }
.kpi-value { font-size: 20px; font-weight: 700; color: #111827; margin: 2px 0; }
.kpi-sub   { font-size: 10px; color: #9ca3af; }
.bar-wrap  { background: #e5e7eb; border-radius: 4px; height: 8px; width: 100%; }
.bar-fill  { height: 8px; border-radius: 4px; background: #0284c7; }
footer { margin-top: 40px; padding-top: 16px; border-top: 1px solid #e5e7eb;
         font-size: 10px; color: #9ca3af; text-align: center; }
"""

# ── Helpers ───────────────────────────────────────────────────────────────────

def _sport_icon(sport: str) -> str:
    return {"cycling": "🚴", "running": "🏃", "swimming": "🏊", "triathlon": "🏅",
            "strength": "💪", "rest": "😴", "mobility": "🧘"}.get(sport, "⚡")

def _fmt_duration(seconds: int | None, minutes: int | None = None) -> str:
    if seconds:
        h, m = divmod(seconds, 3600)
        m = m // 60
        return f"{h}h {m}min" if h else f"{m}min"
    if minutes:
        return f"{minutes}min"
    return "—"

def _fmt_dist(meters: float | None) -> str:
    if not meters:
        return "—"
    return f"{meters/1000:.1f} km" if meters >= 1000 else f"{meters:.0f} m"

def _tsb_badge(tsb: float | None) -> str:
    if tsb is None:
        return ""
    if tsb < -25:
        return '<span class="badge badge-red">Crítico</span>'
    if tsb < -10:
        return '<span class="badge badge-orange">Fatigado</span>'
    if tsb < 5:
        return '<span class="badge badge-blue">Neutro</span>'
    return '<span class="badge badge-green">Fresco</span>'

def _kpi(label: str, value: str, sub: str = "") -> str:
    return f"""<div class="kpi">
      <div class="kpi-label">{label}</div>
      <div class="kpi-value">{value}</div>
      {"" if not sub else f'<div class="kpi-sub">{sub}</div>'}
    </div>"""

# ── Monthly Report ────────────────────────────────────────────────────────────

async def generate_monthly_report_pdf(
    db: AsyncSession,
    athlete_id: str,
    year: int,
    month: int,
) -> bytes:
    _, last_day = monthrange(year, month)
    start = date(year, month, 1)
    end   = date(year, month, last_day)

    athlete_result = await db.execute(select(Athlete).where(Athlete.id == athlete_id))
    athlete = athlete_result.scalar_one_or_none()
    if not athlete:
        raise ValueError(f"Athlete {athlete_id} not found")

    # Workouts
    workouts_result = await db.execute(
        select(Workout).where(
            Workout.athlete_id == athlete_id,
            func.date(Workout.start_time) >= start,
            func.date(Workout.start_time) <= end,
            Workout.is_completed == True,
        ).order_by(Workout.start_time)
    )
    workouts = workouts_result.scalars().all()

    # Strength sessions
    strength_result = await db.execute(
        select(StrengthSession).where(
            StrengthSession.athlete_id == athlete_id,
            StrengthSession.session_date >= start,
            StrengthSession.session_date <= end,
        ).order_by(StrengthSession.session_date)
    )
    strength = strength_result.scalars().all()

    # Training load history for the month
    load_result = await db.execute(
        select(TrainingLoad).where(
            TrainingLoad.athlete_id == athlete_id,
            TrainingLoad.load_date >= start,
            TrainingLoad.load_date <= end,
        ).order_by(TrainingLoad.load_date)
    )
    loads = load_result.scalars().all()

    # Daily metrics
    metrics_result = await db.execute(
        select(DailyMetric).where(
            DailyMetric.athlete_id == athlete_id,
            DailyMetric.metric_date >= start,
            DailyMetric.metric_date <= end,
        ).order_by(DailyMetric.metric_date)
    )
    metrics = metrics_result.scalars().all()

    # AI Recommendations (followed only)
    recs_result = await db.execute(
        select(AIRecommendation).where(
            AIRecommendation.athlete_id == athlete_id,
            AIRecommendation.recommendation_date >= start,
            AIRecommendation.recommendation_date <= end,
        ).order_by(AIRecommendation.recommendation_date.desc())
    )
    recs = recs_result.scalars().all()

    # ── Summary calculations
    total_tss = sum(float(w.tss or 0) for w in workouts)
    total_tss += sum(float(s.tss or 0) for s in strength if hasattr(s, "tss") and s.tss)
    total_duration = sum(w.duration_seconds or 0 for w in workouts)
    total_distance = sum(float(w.distance_meters or 0) for w in workouts)
    avg_sleep = None
    avg_fatigue = None
    avg_hrv = None
    if metrics:
        sleeps = [float(m.sleep_hours) for m in metrics if m.sleep_hours]
        fatigue = [m.fatigue_score for m in metrics if m.fatigue_score]
        hrvs = [m.hrv_ms for m in metrics if m.hrv_ms]
        avg_sleep = f"{sum(sleeps)/len(sleeps):.1f}h" if sleeps else "—"
        avg_fatigue = f"{sum(fatigue)/len(fatigue):.1f}/10" if fatigue else "—"
        avg_hrv = f"{sum(hrvs)/len(hrvs):.0f} ms" if hrvs else "—"

    load_start = loads[0] if loads else None
    load_end   = loads[-1] if loads else None
    ctl_delta = (float(load_end.ctl) - float(load_start.ctl)) if (load_start and load_end) else None
    ctl_delta_str = (f"{'↑' if ctl_delta >= 0 else '↓'}{abs(ctl_delta):.1f}") if ctl_delta is not None else "—"
    tsb_end = float(load_end.tsb) if load_end and load_end.tsb else None

    followed = [r for r in recs if r.was_followed is True]
    adherence = f"{len(followed)}/{len(recs)}" if recs else "—"

    month_name_pt = ["Janeiro","Fevereiro","Março","Abril","Maio","Junho",
                     "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"][month - 1]

    # ── Workouts table rows
    workout_rows = ""
    for w in workouts:
        dt = w.start_time.strftime("%d/%m") if w.start_time else "—"
        icon = _sport_icon(w.sport_type)
        name = w.title or w.sport_type.capitalize()
        tss_str = f"{float(w.tss):.0f}" if w.tss else "—"
        workout_rows += f"""<tr>
          <td>{dt}</td>
          <td>{icon} {name}</td>
          <td>{_fmt_duration(w.duration_seconds)}</td>
          <td>{_fmt_dist(float(w.distance_meters) if w.distance_meters else None)}</td>
          <td>{w.avg_power_watts or "—"}</td>
          <td>{tss_str}</td>
        </tr>"""

    for s in strength:
        dt = s.session_date.strftime("%d/%m") if s.session_date else "—"
        session_label = {"upper":"Superior","lower":"Inferior","full_body":"Corpo todo",
                         "push":"Empurrar","pull":"Puxar"}.get(s.session_type or "", "Musculação")
        tss_str = f"{float(s.tss):.0f}" if hasattr(s,"tss") and s.tss else "—"
        workout_rows += f"""<tr>
          <td>{dt}</td>
          <td>💪 {session_label}</td>
          <td>{_fmt_duration(None, s.duration_minutes)}</td>
          <td>—</td>
          <td>RPE {s.rpe_overall or "—"}</td>
          <td>{tss_str}</td>
        </tr>"""

    if not workout_rows:
        workout_rows = '<tr><td colspan="6" style="text-align:center;color:#9ca3af;">Nenhum treino registrado</td></tr>'

    # ── Load table rows
    load_rows = ""
    for l in loads[::3]:  # every 3 days to keep concise
        load_rows += f"""<tr>
          <td>{l.load_date.strftime('%d/%m')}</td>
          <td>{float(l.ctl):.1f}</td>
          <td>{float(l.atl):.1f}</td>
          <td>{float(l.tsb):+.1f}</td>
          <td>{float(l.daily_tss or 0):.0f}</td>
        </tr>"""

    if not load_rows:
        load_rows = '<tr><td colspan="5" style="text-align:center;color:#9ca3af;">Sem dados de carga</td></tr>'

    # ── Metrics table
    metrics_rows = ""
    for m in metrics[-10:]:
        metrics_rows += f"""<tr>
          <td>{m.metric_date.strftime('%d/%m')}</td>
          <td>{m.sleep_hours or "—"}h</td>
          <td>{m.sleep_quality or "—"}/10</td>
          <td>{m.hrv_ms or "—"} ms</td>
          <td>{m.fatigue_score or "—"}/10</td>
          <td>{m.motivation_score or "—"}/10</td>
        </tr>"""

    if not metrics_rows:
        metrics_rows = '<tr><td colspan="6" style="text-align:center;color:#9ca3af;">Nenhuma métrica registrada</td></tr>'

    generated_at = datetime.now().strftime("%d/%m/%Y %H:%M")

    html = f"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="UTF-8">
<style>{_BASE_CSS}</style></head>
<body>

<h1>FitCoach AI — Relatório Mensal</h1>
<p class="subtitle">{athlete.name} · {month_name_pt} de {year}</p>
<p class="subtitle">Gerado em {generated_at}</p>

<h2>Resumo do Mês</h2>
<div class="kpi-grid">
  {_kpi("Treinos", str(len(workouts) + len(strength)), f"{len(workouts)} endurance · {len(strength)} força")}
  {_kpi("TSS Total", f"{total_tss:.0f}", "carga de treino acumulada")}
  {_kpi("Distância", _fmt_dist(total_distance), "treinos de endurance")}
  {_kpi("Tempo", _fmt_duration(total_duration), "endurance total")}
  {_kpi("Aderência", adherence, "treinos seguidos / gerados")}
  {_kpi("CTL Δ", ctl_delta_str, "variação de fitness")}
</div>

<h2>Carga de Treino (CTL/ATL/TSB)</h2>
{"" if not load_end else f"""
<div class="kpi-grid">
  {_kpi("CTL Final", f"{float(load_end.ctl):.1f}", "fitness acumulado")}
  {_kpi("ATL Final", f"{float(load_end.atl):.1f}", "fadiga atual")}
  {_kpi("TSB Final", f"{float(load_end.tsb):+.1f}", "forma → " + ("ótima" if tsb_end and tsb_end > 5 else "neutra" if tsb_end and tsb_end > -10 else "fatigado"))}
</div>"""}
<table>
  <thead><tr><th>Data</th><th>CTL</th><th>ATL</th><th>TSB</th><th>TSS Dia</th></tr></thead>
  <tbody>{load_rows}</tbody>
</table>

<h2>Treinos Realizados</h2>
<table>
  <thead><tr><th>Data</th><th>Treino</th><th>Duração</th><th>Distância</th><th>Potência/RPE</th><th>TSS</th></tr></thead>
  <tbody>{workout_rows}</tbody>
</table>

<h2>Métricas de Bem-estar (últimas {min(len(metrics),10)} entradas)</h2>
<div class="kpi-grid">
  {_kpi("Sono médio", avg_sleep or "—")}
  {_kpi("Fadiga média", avg_fatigue or "—")}
  {_kpi("HRV médio", avg_hrv or "—")}
  {_kpi("Dias registrados", str(len(metrics)), f"de {last_day} dias no mês")}
</div>
<table>
  <thead><tr><th>Data</th><th>Sono</th><th>Qualidade</th><th>HRV</th><th>Fadiga</th><th>Motivação</th></tr></thead>
  <tbody>{metrics_rows}</tbody>
</table>

<footer>
  FitCoach AI — Relatório gerado em {generated_at} · Dados confidenciais
</footer>
</body></html>"""

    return _html_to_pdf(html)


# ── LGPD Export ───────────────────────────────────────────────────────────────

async def generate_lgpd_export_pdf(db: AsyncSession, athlete_id: str) -> bytes:
    athlete_result = await db.execute(select(Athlete).where(Athlete.id == athlete_id))
    athlete = athlete_result.scalar_one_or_none()
    if not athlete:
        raise ValueError(f"Athlete {athlete_id} not found")

    workouts_result = await db.execute(
        select(func.count()).select_from(Workout).where(Workout.athlete_id == athlete_id)
    )
    workout_count = workouts_result.scalar() or 0

    strength_result = await db.execute(
        select(func.count()).select_from(StrengthSession).where(StrengthSession.athlete_id == athlete_id)
    )
    strength_count = strength_result.scalar() or 0

    metrics_result = await db.execute(
        select(func.count()).select_from(DailyMetric).where(DailyMetric.athlete_id == athlete_id)
    )
    metrics_count = metrics_result.scalar() or 0

    recs_result = await db.execute(
        select(func.count()).select_from(AIRecommendation).where(AIRecommendation.athlete_id == athlete_id)
    )
    recs_count = recs_result.scalar() or 0

    generated_at = datetime.now().strftime("%d/%m/%Y %H:%M")

    def _row(label: str, value: str) -> str:
        return f"<tr><td style='font-weight:600;width:200px;color:#374151;'>{label}</td><td>{value}</td></tr>"

    profile_rows = "".join([
        _row("Nome completo", athlete.name or "—"),
        _row("E-mail", athlete.email or "—"),
        _row("Telefone", athlete.phone or "—"),
        _row("Data de nascimento", athlete.birth_date.strftime("%d/%m/%Y") if athlete.birth_date else "—"),
        _row("Gênero", athlete.gender or "—"),
        _row("Altura", f"{athlete.height_cm} cm" if athlete.height_cm else "—"),
        _row("Peso", f"{athlete.weight_kg} kg" if athlete.weight_kg else "—"),
        _row("Modalidade principal", athlete.primary_modality or "—"),
        _row("Objetivo", athlete.goal or "—"),
        _row("FTP", f"{athlete.ftp_watts} W" if athlete.ftp_watts else "—"),
        _row("FC máxima", f"{athlete.max_hr} bpm" if athlete.max_hr else "—"),
        _row("FC de repouso", f"{athlete.resting_hr} bpm" if athlete.resting_hr else "—"),
        _row("Conta criada em", athlete.created_at.strftime("%d/%m/%Y") if athlete.created_at else "—"),
    ])

    data_rows = "".join([
        _row("Treinos de endurance", str(workout_count)),
        _row("Sessões de musculação", str(strength_count)),
        _row("Métricas diárias", str(metrics_count)),
        _row("Recomendações de IA", str(recs_count)),
        _row("Tokens de plataforma (Strava/TP)", "Armazenados criptografados (AES-256)"),
        _row("Anamnese", "Armazenada criptografada (pgcrypto)"),
    ])

    html = f"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="UTF-8">
<style>{_BASE_CSS}
  .legal {{ font-size: 10px; color: #6b7280; line-height: 1.6; }}
</style></head>
<body>

<h1>FitCoach AI — Exportação de Dados Pessoais</h1>
<p class="subtitle">Solicitado por: {athlete.name}</p>
<p class="subtitle">Gerado em: {generated_at} · Conforme LGPD (Lei 13.709/2018)</p>

<h2>Dados de Perfil</h2>
<table><tbody>{profile_rows}</tbody></table>

<h2>Dados Coletados e Processados</h2>
<table><tbody>{data_rows}</tbody></table>

<h2>Bases Legais e Finalidades</h2>
<p class="legal">
  Seus dados são processados com base em <strong>consentimento informado</strong> (Art. 7º, I da LGPD).
  Finalidades: personalização de recomendações de treino, cálculo de carga de treino (CTL/ATL/TSB),
  integração com plataformas de terceiros (Strava, TrainingPeaks) com autorização explícita,
  e geração de relatórios de desempenho.
</p>

<h2>Seus Direitos</h2>
<p class="legal">
  Você tem direito a: acesso (Art. 18, II), retificação (III), eliminação (VI), portabilidade (V),
  revogação de consentimento a qualquer momento (IX). Para exercer esses direitos, acesse
  as configurações do app ou contate privacidade@fitcoachai.com.
</p>

<footer>
  FitCoach AI · Este documento é confidencial e destina-se exclusivamente ao titular dos dados.
  Gerado em {generated_at}.
</footer>
</body></html>"""

    return _html_to_pdf(html)


# ── WeasyPrint wrapper ────────────────────────────────────────────────────────

def _html_to_pdf(html: str) -> bytes:
    try:
        from weasyprint import HTML, CSS
        pdf_bytes = HTML(string=html).write_pdf()
        return pdf_bytes
    except Exception as exc:
        logger.exception("WeasyPrint PDF generation failed: %s", exc)
        raise RuntimeError(f"PDF generation failed: {exc}") from exc
