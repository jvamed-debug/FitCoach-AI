"""
Email service via Resend API.
All email sending is fire-and-forget with structured logging.
"""

import logging
import resend
from app.config import settings

logger = logging.getLogger(__name__)

resend.api_key = settings.resend_api_key


async def send_athlete_invite(
    to_email: str,
    athlete_name: str,
    admin_name: str,
    onboarding_url: str,
) -> bool:
    html = f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head><meta charset="UTF-8"></head>
    <body style="font-family: sans-serif; color: #1a1a1a; max-width: 600px; margin: 0 auto; padding: 24px;">
      <h1 style="color: #0284c7; font-size: 24px; margin-bottom: 4px;">FitCoach AI</h1>
      <p style="color: #6b7280; margin-top: 0; font-size: 14px;">Plataforma de coaching esportivo com IA</p>

      <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 24px 0;">

      <p>Olá, <strong>{athlete_name}</strong>!</p>
      <p>
        <strong>{admin_name}</strong> convidou você para usar o FitCoach AI —
        uma plataforma que usa inteligência artificial para gerar recomendações
        de treino personalizadas com base no seu histórico e estado de fadiga.
      </p>

      <div style="text-align: center; margin: 32px 0;">
        <a href="{onboarding_url}"
           style="display: inline-block; background-color: #0284c7; color: white;
                  text-decoration: none; padding: 12px 28px; border-radius: 8px;
                  font-weight: 600; font-size: 15px;">
          Criar minha conta
        </a>
      </div>

      <p style="font-size: 13px; color: #6b7280;">
        Este link é válido por 7 dias. Se você não esperava este convite,
        pode ignorar este e-mail com segurança.
      </p>

      <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 24px 0;">
      <p style="font-size: 12px; color: #9ca3af; text-align: center;">
        FitCoach AI · Seus dados são protegidos pela LGPD · privacidade@fitcoachai.com
      </p>
    </body>
    </html>
    """
    try:
        resend.Emails.send({
            "from": settings.from_email,
            "to": [to_email],
            "subject": f"{admin_name} te convidou para o FitCoach AI",
            "html": html,
        })
        logger.info("Invite email sent to %s", to_email)
        return True
    except Exception:
        logger.exception("Failed to send invite email to %s", to_email)
        return False


async def send_welcome_email(to_email: str, athlete_name: str) -> bool:
    html = f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head><meta charset="UTF-8"></head>
    <body style="font-family: sans-serif; color: #1a1a1a; max-width: 600px; margin: 0 auto; padding: 24px;">
      <h1 style="color: #0284c7;">Bem-vindo ao FitCoach AI, {athlete_name.split()[0]}!</h1>
      <p>
        Seu onboarding está completo. A partir de amanhã você receberá
        recomendações diárias de treino geradas pela IA com base nos seus dados do Strava
        e no seu histórico de musculação.
      </p>
      <p>Bons treinos! 🚴</p>
    </body>
    </html>
    """
    try:
        resend.Emails.send({
            "from": settings.from_email,
            "to": [to_email],
            "subject": "Bem-vindo ao FitCoach AI!",
            "html": html,
        })
        return True
    except Exception:
        logger.exception("Failed to send welcome email to %s", to_email)
        return False


async def send_alert_email(
    to_email: str,
    admin_name: str,
    athlete_name: str,
    title: str,
    body: str,
    severity: str = "warning",
) -> bool:
    severity_color = {"critical": "#dc2626", "warning": "#d97706", "info": "#0284c7"}.get(severity, "#6b7280")
    severity_label = {"critical": "CRÍTICO", "warning": "ATENÇÃO", "info": "INFO"}.get(severity, severity.upper())

    html = f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head><meta charset="UTF-8"></head>
    <body style="font-family: sans-serif; color: #1a1a1a; max-width: 600px; margin: 0 auto; padding: 24px;">
      <h1 style="color: #0284c7; font-size: 20px; margin-bottom: 4px;">FitCoach AI</h1>
      <p style="color: #6b7280; margin-top: 0; font-size: 13px;">Alerta automático</p>
      <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 20px 0;">

      <div style="border-left: 4px solid {severity_color}; padding: 12px 16px; background: #f9fafb; border-radius: 4px; margin-bottom: 20px;">
        <span style="display: inline-block; background: {severity_color}; color: white; font-size: 11px;
                     font-weight: 700; padding: 2px 8px; border-radius: 4px; margin-bottom: 8px;">
          {severity_label}
        </span>
        <p style="margin: 4px 0; font-weight: 600; font-size: 15px;">{title}</p>
        <p style="margin: 8px 0 0; font-size: 14px; color: #374151;">{body}</p>
      </div>

      <p style="font-size: 13px; color: #6b7280;">
        Olá, <strong>{admin_name}</strong>. Este alerta foi gerado automaticamente para o atleta
        <strong>{athlete_name}</strong>.
        <a href="{settings.frontend_url}/admin/alerts" style="color: #0284c7;">Ver todos os alertas →</a>
      </p>

      <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 20px 0;">
      <p style="font-size: 11px; color: #9ca3af; text-align: center;">
        FitCoach AI · privacidade@fitcoachai.com
      </p>
    </body>
    </html>
    """
    try:
        resend.Emails.send({
            "from": settings.from_email,
            "to": [to_email],
            "subject": f"[FitCoach AI] {title}",
            "html": html,
        })
        logger.info("Alert email sent to %s (severity=%s)", to_email, severity)
        return True
    except Exception:
        logger.exception("Failed to send alert email to %s", to_email)
        return False


async def send_weekly_report_email(
    to_email: str,
    admin_name: str,
    reports: list[dict],
    week_end,
) -> bool:
    def _section(report: dict) -> str:
        ctx = report.get("_context", {})
        name = ctx.get("athlete_name", "Atleta")
        week = ctx.get("week", "")
        summary = report.get("week_summary", "")
        highlights = report.get("highlights", [])
        concerns = report.get("concerns", [])
        next_focus = report.get("next_week_focus", "")
        tss = ctx.get("total_tss", 0)
        workouts = ctx.get("workouts_count", 0)
        load_end = ctx.get("load_end") or {}
        tsb = load_end.get("tsb", None)
        tsb_str = f"TSB {tsb:+.1f}" if tsb is not None else "TSB —"

        hl_html = "".join(f"<li style='margin:2px 0;'>✅ {h}</li>" for h in highlights) if highlights else ""
        c_html = "".join(f"<li style='margin:2px 0;color:#dc2626;'>⚠️ {c}</li>" for c in concerns) if concerns else ""

        return f"""
        <div style="border:1px solid #e5e7eb; border-radius:8px; padding:16px; margin-bottom:16px;">
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <h3 style="margin:0; font-size:16px; color:#111827;">{name}</h3>
            <span style="font-size:12px; color:#6b7280;">{week} · {workouts} treinos · TSS {tss} · {tsb_str}</span>
          </div>
          <p style="margin:10px 0; font-size:14px; color:#374151;">{summary}</p>
          {"<ul style='margin:6px 0; padding-left:20px; font-size:13px;'>" + hl_html + c_html + "</ul>" if hl_html or c_html else ""}
          {"<p style='margin:8px 0; font-size:13px; color:#4b5563;'><strong>Próxima semana:</strong> " + next_focus + "</p>" if next_focus else ""}
        </div>
        """

    athletes_html = "".join(_section(r) for r in reports)

    html = f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head><meta charset="UTF-8"></head>
    <body style="font-family: sans-serif; color: #1a1a1a; max-width: 640px; margin: 0 auto; padding: 24px;">
      <h1 style="color: #0284c7; font-size: 20px; margin-bottom: 4px;">FitCoach AI</h1>
      <p style="color: #6b7280; margin-top: 0; font-size: 13px;">Relatório semanal de treino</p>
      <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 20px 0;">

      <p>Olá, <strong>{admin_name}</strong>! Aqui está o resumo da semana dos seus atletas.</p>

      {athletes_html}

      <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 20px 0;">
      <p style="text-align:center;">
        <a href="{settings.frontend_url}/admin/dashboard"
           style="display:inline-block; background:#0284c7; color:white; text-decoration:none;
                  padding:10px 24px; border-radius:6px; font-weight:600; font-size:14px;">
          Ver painel completo →
        </a>
      </p>
      <p style="font-size:11px; color:#9ca3af; text-align:center; margin-top:16px;">
        FitCoach AI · privacidade@fitcoachai.com
      </p>
    </body>
    </html>
    """
    try:
        resend.Emails.send({
            "from": settings.from_email,
            "to": [to_email],
            "subject": f"[FitCoach AI] Relatório semanal — {len(reports)} atleta(s)",
            "html": html,
        })
        logger.info("Weekly report email sent to %s (%d athletes)", to_email, len(reports))
        return True
    except Exception:
        logger.exception("Failed to send weekly report email to %s", to_email)
        return False


async def send_monthly_report_email(
    to_email: str,
    athlete_name: str,
    year: int,
    month: int,
    pdf_bytes: bytes,
) -> bool:
    import base64
    month_names = ["Janeiro","Fevereiro","Março","Abril","Maio","Junho",
                   "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"]
    month_label = month_names[month - 1]
    filename = f"fitcoach-relatorio-{month:02d}-{year}.pdf"

    html = f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head><meta charset="UTF-8"></head>
    <body style="font-family: sans-serif; color: #1a1a1a; max-width: 600px; margin: 0 auto; padding: 24px;">
      <h1 style="color: #0284c7; font-size: 20px;">FitCoach AI</h1>
      <p style="color: #6b7280; font-size: 13px; margin-top: 0;">Relatório mensal de treino</p>
      <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 20px 0;">
      <p>Olá, <strong>{athlete_name.split()[0]}</strong>!</p>
      <p>
        Seu relatório de desempenho de <strong>{month_label} de {year}</strong> está pronto.
        O arquivo PDF com o resumo completo (treinos, carga CTL/ATL/TSB, métricas de bem-estar
        e aderência às recomendações) está anexado a este e-mail.
      </p>
      <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 20px 0;">
      <p style="font-size: 11px; color: #9ca3af; text-align: center;">
        FitCoach AI · privacidade@fitcoachai.com
      </p>
    </body>
    </html>
    """
    try:
        resend.Emails.send({
            "from": settings.from_email,
            "to": [to_email],
            "subject": f"FitCoach AI — Seu relatório de {month_label} de {year}",
            "html": html,
            "attachments": [
                {
                    "filename": filename,
                    "content": base64.b64encode(pdf_bytes).decode(),
                }
            ],
        })
        logger.info("Monthly report email sent to %s (%d/%d)", to_email, month, year)
        return True
    except Exception:
        logger.exception("Failed to send monthly report email to %s", to_email)
        return False


async def send_lgpd_export_email(to_email: str, athlete_name: str, pdf_bytes: bytes) -> bool:
    import base64
    html = f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head><meta charset="UTF-8"></head>
    <body style="font-family: sans-serif; color: #1a1a1a; max-width: 600px; margin: 0 auto; padding: 24px;">
      <h1 style="color: #0284c7; font-size: 20px;">FitCoach AI</h1>
      <p style="color: #6b7280; font-size: 13px; margin-top: 0;">Exportação de dados pessoais — LGPD</p>
      <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 20px 0;">
      <p>Olá, <strong>{athlete_name.split()[0]}</strong>.</p>
      <p>
        Conforme sua solicitação e em cumprimento à Lei Geral de Proteção de Dados (LGPD),
        segue em anexo o PDF com todos os seus dados pessoais processados pelo FitCoach AI.
      </p>
      <p style="font-size: 13px; color: #6b7280;">
        Para solicitar a exclusão dos seus dados ou exercer outros direitos, acesse
        as configurações do app ou envie e-mail para privacidade@fitcoachai.com.
      </p>
      <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 20px 0;">
      <p style="font-size: 11px; color: #9ca3af; text-align: center;">
        FitCoach AI · privacidade@fitcoachai.com
      </p>
    </body>
    </html>
    """
    try:
        resend.Emails.send({
            "from": settings.from_email,
            "to": [to_email],
            "subject": "FitCoach AI — Exportação dos seus dados pessoais (LGPD)",
            "html": html,
            "attachments": [
                {
                    "filename": "fitcoach-meus-dados.pdf",
                    "content": base64.b64encode(pdf_bytes).decode(),
                }
            ],
        })
        logger.info("LGPD export email sent to %s", to_email)
        return True
    except Exception:
        logger.exception("Failed to send LGPD export email to %s", to_email)
        return False


async def send_lgpd_deletion_confirmation(to_email: str, athlete_name: str, deadline: str) -> bool:
    html = f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head><meta charset="UTF-8"></head>
    <body style="font-family: sans-serif; color: #1a1a1a; max-width: 600px; margin: 0 auto; padding: 24px;">
      <h1 style="color: #dc2626;">Confirmação de exclusão de dados</h1>
      <p>Olá, {athlete_name.split()[0]}.</p>
      <p>
        Recebemos sua solicitação de exclusão de dados pessoais conforme a LGPD.
        Todos os seus dados serão excluídos permanentemente até <strong>{deadline}</strong>.
      </p>
      <p style="font-size: 13px; color: #6b7280;">
        Se você não solicitou esta exclusão, entre em contato imediatamente pelo
        privacidade@fitcoachai.com.
      </p>
    </body>
    </html>
    """
    try:
        resend.Emails.send({
            "from": settings.from_email,
            "to": [to_email],
            "subject": "Solicitação de exclusão de dados recebida — FitCoach AI",
            "html": html,
        })
        return True
    except Exception:
        logger.exception("Failed to send deletion confirmation email to %s", to_email)
        return False
