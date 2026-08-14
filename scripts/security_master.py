"""Security Master: evidence-oriented checks for common AI-generated app risks.

This module deliberately separates deterministic evidence collection from human
security judgment.  Its static rules are conservative heuristics: a finding is
an item to verify, never proof that an application is exploitable.  External
scanners are opt-in and their raw output is not copied into the consolidated
report, which prevents accidental persistence of secrets or request payloads.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse, urlunparse


SCHEMA_VERSION = "1.0.0"
SEVERITY_RANK = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
DEFAULT_EXCLUDED_DIRECTORIES = {
    ".git",
    ".next",
    ".nuxt",
    ".pytest_cache",
    ".pytest-tmp",
    ".venv",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "security-artifacts",
    "vendor",
}
TEXT_SUFFIXES = {
    ".c",
    ".cs",
    ".css",
    ".env",
    ".go",
    ".graphql",
    ".html",
    ".java",
    ".js",
    ".json",
    ".jsx",
    ".mjs",
    ".php",
    ".py",
    ".rb",
    ".rs",
    ".rules",
    ".sh",
    ".sql",
    ".svelte",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".vue",
    ".yaml",
    ".yml",
}
CLIENT_SUFFIXES = {".html", ".js", ".jsx", ".mjs", ".svelte", ".ts", ".tsx", ".vue"}
SERVER_PATH_TOKENS = {"api", "backend", "functions", "server", "servers", "route", "routes"}
CLIENT_PATH_TOKENS = {"app", "assets", "client", "components", "pages", "public", "src", "web"}


@dataclass(frozen=True, slots=True)
class Finding:
    rule_id: str
    category: str
    severity: str
    confidence: str
    title: str
    path: str | None
    line: int | None
    evidence: str
    remediation: str


@dataclass(frozen=True, slots=True)
class ToolExecution:
    tool: str
    status: str
    finding_count: int
    detail: str


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name


def _is_text_candidate(path: Path) -> bool:
    return path.name.startswith(".env") or path.suffix.casefold() in TEXT_SUFFIXES


def iter_text_files(root: Path) -> Iterable[Path]:
    """Yield bounded, regular, text-like files without following symlinks."""

    for path in sorted(root.rglob("*")):
        try:
            relative_parts = path.relative_to(root).parts
        except ValueError:
            continue
        if any(part in DEFAULT_EXCLUDED_DIRECTORIES for part in relative_parts):
            continue
        if path.is_symlink() or not path.is_file() or not _is_text_candidate(path):
            continue
        try:
            if path.stat().st_size > 2_000_000:
                continue
        except OSError:
            continue
        yield path


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _line_for_match(text: str, match: re.Match[str]) -> int:
    return text.count("\n", 0, match.start()) + 1


def _path_tokens(path: Path, root: Path) -> set[str]:
    return {part.casefold() for part in path.relative_to(root).parts[:-1]}


def _is_client_file(path: Path, root: Path) -> bool:
    tokens = _path_tokens(path, root)
    if tokens & SERVER_PATH_TOKENS:
        return False
    return path.suffix.casefold() in CLIENT_SUFFIXES and bool(tokens & CLIENT_PATH_TOKENS)


def _is_server_or_route_file(path: Path, root: Path) -> bool:
    tokens = _path_tokens(path, root)
    name = path.name.casefold()
    return bool(tokens & SERVER_PATH_TOKENS) or name.startswith("route.") or name.endswith("controller.py")


def _make_finding(
    rule_id: str,
    category: str,
    severity: str,
    confidence: str,
    title: str,
    path: Path | None,
    root: Path,
    line: int | None,
    evidence: str,
    remediation: str,
) -> Finding:
    return Finding(
        rule_id=rule_id,
        category=category,
        severity=severity,
        confidence=confidence,
        title=title,
        path=_relative(path, root) if path else None,
        line=line,
        evidence=evidence,
        remediation=remediation,
    )


def _git_tracks(root: Path, relative_path: str) -> bool:
    if shutil.which("git") is None:
        return False
    completed = subprocess.run(
        ["git", "-C", str(root), "ls-files", "--error-unmatch", relative_path],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    return completed.returncode == 0


def _contains_any(text: str, terms: Iterable[str]) -> bool:
    folded = text.casefold()
    return any(term.casefold() in folded for term in terms)


def _is_sensitive_dotenv(path: Path) -> bool:
    """Return true for a local environment file, never for a safe template."""

    name = path.name.casefold()
    if not name.startswith(".env"):
        return False
    return not any(marker in name for marker in ("example", "sample", "template"))


def _find_secret_controls(root: Path, files: list[Path]) -> list[Finding]:
    findings: list[Finding] = []
    gitignore = _read(root / ".gitignore")
    has_env_file = False
    public_name = re.compile(
        r"\b(?:NEXT_PUBLIC|VITE|REACT_APP|PUBLIC)_[A-Z0-9_]*(?:SERVICE_ROLE|SECRET|PRIVATE|ADMIN)[A-Z0-9_]*\b",
        re.IGNORECASE,
    )
    service_role = re.compile(r"\b(?:SUPABASE_)?SERVICE_ROLE(?:_KEY)?\b", re.IGNORECASE)

    for path in files:
        text = _read(path)
        if _is_sensitive_dotenv(path):
            has_env_file = True
            relative = _relative(path, root)
            if _git_tracks(root, relative):
                findings.append(
                    _make_finding(
                        "SM-004-TRACKED-DOTENV",
                        "segredos",
                        "critical",
                        "high",
                        "Arquivo de ambiente versionado",
                        path,
                        root,
                        None,
                        "O arquivo de ambiente está rastreado pelo Git; valores foram omitidos do relatório.",
                        "Revogue os segredos presentes, remova o arquivo do histórico com procedimento aprovado e mantenha somente um .env.example sem valores reais.",
                    )
                )
        if _is_client_file(path, root):
            for match in public_name.finditer(text):
                findings.append(
                    _make_finding(
                        "SM-004-PUBLIC-SECRET-NAME",
                        "segredos",
                        "high",
                        "medium",
                        "Nome de variável pública sugere segredo",
                        path,
                        root,
                        _line_for_match(text, match),
                        "Prefixo público de build detectado; o valor foi deliberadamente omitido.",
                        "Não exponha credenciais privilegiadas no bundle. Mova a integração para um backend/BFF e deixe no cliente apenas chaves explicitamente públicas do provedor.",
                    )
                )
        if _is_client_file(path, root):
            for match in service_role.finditer(text):
                findings.append(
                    _make_finding(
                        "SM-004-SERVICE-ROLE-CLIENT",
                        "segredos",
                        "critical",
                        "medium",
                        "Referência a service_role em código potencialmente cliente",
                        path,
                        root,
                        _line_for_match(text, match),
                        "Identificador de credencial privilegiada localizado em árvore de cliente; nenhum valor foi registrado.",
                        "Garanta que service_role/admin SDK exista somente em código server-side e revogue a chave se ela já tiver integrado qualquer bundle publicado.",
                    )
                )

    ignores_env = bool(re.search(r"(?m)^\s*\.env(?:\*|/|\s|$)", gitignore))
    if has_env_file and not ignores_env:
        findings.append(
            _make_finding(
                "SM-004-ENV-NOT-IGNORED",
                "segredos",
                "medium",
                "high",
                ".env presente sem regra explícita no .gitignore",
                root / ".gitignore",
                root,
                None,
                "Há arquivo .env no projeto, mas não foi encontrada regra explícita para ignorá-lo.",
                "Inclua .env e variantes locais no .gitignore antes do primeiro commit; use um cofre/secret manager para credenciais de produção.",
            )
        )
    return findings


def _find_data_access_controls(root: Path, files: list[Path]) -> list[Finding]:
    findings: list[Finding] = []
    sql_files = [
        path
        for path in files
        if path.suffix.casefold() == ".sql"
        and any(token in _path_tokens(path, root) for token in {"migration", "migrations", "supabase", "schema", "schemas"})
    ]
    all_sql = "\n".join(_read(path) for path in sql_files)
    table_pattern = re.compile(
        r"\bcreate\s+table\s+(?:if\s+not\s+exists\s+)?(?:(public)\.)?[\"']?([a-zA-Z_][\w$]*)[\"']?",
        re.IGNORECASE,
    )
    rls_pattern_template = r"\balter\s+table\s+(?:public\.)?[\"']?{table}[\"']?\s+enable\s+row\s+level\s+security\b"
    for path in sql_files:
        text = _read(path)
        for match in table_pattern.finditer(text):
            table = match.group(2)
            if re.search(rls_pattern_template.format(table=re.escape(table)), all_sql, re.IGNORECASE):
                continue
            findings.append(
                _make_finding(
                    "SM-001-SUPABASE-RLS-UNVERIFIED",
                    "acesso-a-dados",
                    "high",
                    "medium",
                    "Tabela criada sem evidência de RLS nas migrations",
                    path,
                    root,
                    _line_for_match(text, match),
                    f"A migration cria a tabela '{table}', mas não há ALTER TABLE ... ENABLE ROW LEVEL SECURITY correspondente no conjunto analisado.",
                    "Confirme o estado no ambiente implantado. Para tabelas expostas pela Data API, habilite RLS e escreva policies mínimas por operação e por locatário/usuário; cubra-as com testes negativos.",
                )
            )

    firebase_rules = [path for path in files if path.name in {"firestore.rules", "storage.rules"} or path.suffix == ".rules"]
    insecure_rule = re.compile(r"\ballow\s+(?:read\s*,\s*write|write\s*,\s*read|read|write)\s*:\s*if\s+true\s*;", re.IGNORECASE)
    for path in firebase_rules:
        text = _read(path)
        for match in insecure_rule.finditer(text):
            findings.append(
                _make_finding(
                    "SM-001-FIREBASE-OPEN-RULE",
                    "acesso-a-dados",
                    "critical",
                    "high",
                    "Regra Firebase permite acesso irrestrito",
                    path,
                    root,
                    _line_for_match(text, match),
                    "Regra allow ... if true detectada.",
                    "Substitua por regras deny-by-default que validem request.auth, ownership, campos permitidos, tipo e limites. Teste-as no Emulator antes do deploy.",
                )
            )
    if (root / "firebase.json").is_file() and not firebase_rules:
        findings.append(
            _make_finding(
                "SM-001-FIREBASE-RULES-NOT-FOUND",
                "acesso-a-dados",
                "medium",
                "medium",
                "Projeto Firebase sem regras locais localizadas",
                root / "firebase.json",
                root,
                None,
                "firebase.json foi localizado, porém arquivos de regras Firestore/Storage não foram encontrados no repositório.",
                "Verifique a configuração implantada no Firebase Console/CLI, versione as regras e adicione testes de autorização. Clientes server/admin não são protegidos pelas Security Rules; revise IAM separadamente.",
            )
        )
    return findings


def _find_client_authorization(root: Path, files: list[Path]) -> list[Finding]:
    findings: list[Finding] = []
    role_check = re.compile(
        r"(?:isAdmin|is_admin|\.role|\[\s*[\"']role[\"']\s*\])[^\n]{0,100}(?:admin|administrator)|(?:admin|administrator)[^\n]{0,100}(?:isAdmin|is_admin|\.role)",
        re.IGNORECASE,
    )
    for path in files:
        if not _is_client_file(path, root):
            continue
        text = _read(path)
        for match in role_check.finditer(text):
            findings.append(
                _make_finding(
                    "SM-002-CLIENT-ADMIN-CHECK",
                    "autorizacao-servidor",
                    "medium",
                    "medium",
                    "Controle de administrador encontrado no cliente",
                    path,
                    root,
                    _line_for_match(text, match),
                    "A checagem pode ser somente de interface; o scanner não consegue comprovar a autorização no servidor.",
                    "Trate essa condição como UX. Em cada endpoint, função serverless ou policy, valide identidade, papel, tenant e ação no lado confiável antes de ler ou alterar dados.",
                )
            )
    return findings


def _has_local_authorization(lines: list[str], line_index: int) -> bool:
    start = max(0, line_index - 24)
    end = min(len(lines), line_index + 25)
    context = "\n".join(lines[start:end]).casefold()
    return any(
        term in context
        for term in (
            "authorization",
            "current_user",
            "get_current_user",
            "owner_id",
            "require_auth",
            "session.user",
            "tenant_id",
            "user_id",
            "verify_token",
        )
    )


def _find_idor_candidates(root: Path, files: list[Path]) -> list[Finding]:
    findings: list[Finding] = []
    object_lookup = re.compile(
        r"(?:findUnique|findById|find_one|findOne|get_by_id|\.get)\s*\(|(?:req\.params|params|path_params)\s*\.?\s*\[?[\"']?id",
        re.IGNORECASE,
    )
    for path in files:
        if not _is_server_or_route_file(path, root):
            continue
        text = _read(path)
        lines = text.splitlines()
        for match in object_lookup.finditer(text):
            line = _line_for_match(text, match)
            if _has_local_authorization(lines, line - 1):
                continue
            findings.append(
                _make_finding(
                    "SM-003-IDOR-MANUAL-REVIEW",
                    "idor-bola",
                    "high",
                    "low",
                    "Busca de objeto por identificador sem evidência local de autorização",
                    path,
                    root,
                    line,
                    "Heurística localizou uso de ID controlado pelo cliente; ela não comprova vulnerabilidade nem a ausência de middleware global.",
                    "Teste BOLA/IDOR com dois usuários e dois tenants: cada rota que recebe um ID deve consultar pelo ID junto da propriedade/tenant autorizados ou delegar a uma policy comprovadamente equivalente.",
                )
            )
    return findings


def _has_validation(text: str) -> bool:
    return _contains_any(
        text,
        (
            "basemodel",
            "filefilter",
            "get_validated_json",
            "joi.",
            "pydantic",
            "safeparse",
            "schema.parse",
            "validate(",
            "validator",
            "zod",
        ),
    )


def _find_untrusted_input_controls(root: Path, files: list[Path]) -> list[Finding]:
    findings: list[Finding] = []
    input_pattern = re.compile(
        r"(?:req\.body|request\.body|request\.json\s*\(|get_json\s*\(|request\.form|formdata\s*\()",
        re.IGNORECASE,
    )
    upload_pattern = re.compile(
        r"(?:multer|upload\.any\s*\(|request\.files|uploadfile|fileupload|request\.file)",
        re.IGNORECASE,
    )
    auth_route = re.compile(r"(?:login|sign-?in|password|reset|verify|otp|auth)", re.IGNORECASE)
    rate_limit_terms = ("express-rate-limit", "limiter", "rate_limit", "ratelimit", "slowapi", "throttle")
    upload_controls = ("content_type", "filefilter", "magic", "mimetype", "size", "upload_max", "validate_file")

    for path in files:
        if not _is_server_or_route_file(path, root):
            continue
        text = _read(path)
        if not _has_validation(text):
            for match in input_pattern.finditer(text):
                findings.append(
                    _make_finding(
                        "SM-005-BODY-WITHOUT-VALIDATION",
                        "entrada-nao-confiavel",
                        "medium",
                        "medium",
                        "Entrada de requisição sem biblioteca/regra de validação localizada",
                        path,
                        root,
                        _line_for_match(text, match),
                        "A validação pode estar em middleware compartilhado; o achado exige confirmação manual.",
                        "Valide esquema, tipo, tamanho, limites e campos permitidos no servidor antes de usar input. Para conteúdo HTML, aplique encoding/sanitização contextual na saída.",
                    )
                )
                break
        for match in upload_pattern.finditer(text):
            if _contains_any(text, upload_controls):
                continue
            findings.append(
                _make_finding(
                    "SM-005-UPLOAD-WITHOUT-CONTROLS",
                    "entrada-nao-confiavel",
                    "high",
                    "medium",
                    "Upload sem controles de tipo/tamanho localizados",
                    path,
                    root,
                    _line_for_match(text, match),
                    "Endpoint de upload detectado; não foram encontradas verificações locais de tipo/tamanho.",
                    "Restrinja extensão e MIME, valide assinatura/magic bytes quando aplicável, imponha tamanho e quantidade, armazene fora da raiz pública e execute tratamento antimalware conforme o risco.",
                )
            )
        route_name = _relative(path, root)
        if auth_route.search(route_name) and not _contains_any(text, rate_limit_terms):
            findings.append(
                _make_finding(
                    "SM-005-AUTH-WITHOUT-RATE-LIMIT",
                    "entrada-nao-confiavel",
                    "medium",
                    "low",
                    "Rota sensível sem rate limit local localizado",
                    path,
                    root,
                    None,
                    "A proteção pode existir no proxy, WAF ou middleware global; este achado requer confirmação de configuração efetiva.",
                    "Aplique limitação por conta, IP e sinal de abuso em login, recuperação de senha, OTP, verificação e endpoints que geram custo. Registre eventos sem gravar segredos.",
                )
            )
    return findings


def static_findings(target: Path) -> list[Finding]:
    root = target.resolve()
    if not root.is_dir():
        raise ValueError(f"Diretório alvo inexistente: {target}")
    files = list(iter_text_files(root))
    findings: list[Finding] = []
    findings.extend(_find_data_access_controls(root, files))
    findings.extend(_find_client_authorization(root, files))
    findings.extend(_find_idor_candidates(root, files))
    findings.extend(_find_secret_controls(root, files))
    findings.extend(_find_untrusted_input_controls(root, files))
    return sorted(findings, key=lambda item: (-SEVERITY_RANK[item.severity], item.path or "", item.line or 0, item.rule_id))


def _normalize_gitleaks(payload: Any, root: Path) -> list[Finding]:
    if not isinstance(payload, list):
        return []
    findings: list[Finding] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        file_name = item.get("File") if isinstance(item.get("File"), str) else None
        line = item.get("StartLine") if isinstance(item.get("StartLine"), int) else None
        rule = item.get("RuleID") if isinstance(item.get("RuleID"), str) else "unknown"
        findings.append(
            Finding(
                rule_id=f"GITLEAKS-{rule}",
                category="segredos",
                severity="critical",
                confidence="high",
                title="Segredo detectado pelo Gitleaks",
                path=file_name,
                line=line,
                evidence="Gitleaks reportou um possível segredo; o valor e a descrição original foram omitidos do relatório consolidado.",
                remediation="Considere a credencial exposta: revogue/rotacione-a, investigue uso indevido e remova-a de código, histórico e logs conforme o procedimento de resposta a incidente.",
            )
        )
    return findings


def _normalize_bandit(payload: Any) -> list[Finding]:
    results = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(results, list):
        return []
    findings: list[Finding] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        confidence = str(item.get("issue_confidence", "MEDIUM")).casefold()
        severity = str(item.get("issue_severity", "MEDIUM")).casefold()
        if severity not in SEVERITY_RANK:
            severity = "medium"
        findings.append(
            Finding(
                rule_id=f"BANDIT-{item.get('test_id', 'unknown')}",
                category="analise-estatica",
                severity=severity,
                confidence=confidence if confidence in {"low", "medium", "high"} else "medium",
                title="Padrão perigoso detectado pelo Bandit",
                path=item.get("filename") if isinstance(item.get("filename"), str) else None,
                line=item.get("line_number") if isinstance(item.get("line_number"), int) else None,
                evidence="Bandit reportou o padrão; trecho de código foi omitido do relatório consolidado.",
                remediation="Revise a regra do Bandit no contexto do fluxo de dados e aplique a correção segura recomendada ou documente uma exceção justificada e testada.",
            )
        )
    return findings


def _normalize_opengrep_sarif(payload: Any) -> list[Finding]:
    runs = payload.get("runs") if isinstance(payload, dict) else None
    if not isinstance(runs, list):
        return []
    findings: list[Finding] = []
    for run in runs:
        if not isinstance(run, dict):
            continue
        for item in run.get("results", []):
            if not isinstance(item, dict):
                continue
            location = None
            locations = item.get("locations")
            if isinstance(locations, list) and locations and isinstance(locations[0], dict):
                physical = locations[0].get("physicalLocation")
                if isinstance(physical, dict):
                    location = physical
            artifact = location.get("artifactLocation", {}) if isinstance(location, dict) else {}
            region = location.get("region", {}) if isinstance(location, dict) else {}
            level = str(item.get("level", "warning")).casefold()
            severity = {"error": "high", "warning": "medium", "note": "low"}.get(level, "medium")
            findings.append(
                Finding(
                    rule_id=f"OPENGREP-{item.get('ruleId', 'unknown')}",
                    category="analise-estatica",
                    severity=severity,
                    confidence="medium",
                    title="Regra SAST detectada pelo Opengrep",
                    path=artifact.get("uri") if isinstance(artifact.get("uri"), str) else None,
                    line=region.get("startLine") if isinstance(region.get("startLine"), int) else None,
                    evidence="Opengrep reportou a regra; snippet e valores foram omitidos do relatório consolidado.",
                    remediation="Revise o fluxo no arquivo indicado. Corrija o padrão ou mantenha uma exceção documentada, limitada e coberta por teste de segurança.",
                )
            )
    return findings


def _sanitize_target_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("A URL do ZAP deve usar http(s) e possuir host.")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Não inclua credenciais, query string ou fragmento na URL do ZAP.")
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path or "/", "", "", ""))


def _normalize_zap(payload: Any) -> list[Finding]:
    sites = payload.get("site") if isinstance(payload, dict) else None
    if not isinstance(sites, list):
        return []
    findings: list[Finding] = []
    for site in sites:
        if not isinstance(site, dict):
            continue
        alerts = site.get("alerts", [])
        if not isinstance(alerts, list):
            continue
        for alert in alerts:
            if not isinstance(alert, dict):
                continue
            risk = str(alert.get("riskcode", "2"))
            severity = {"3": "high", "2": "medium", "1": "low", "0": "info"}.get(risk, "medium")
            instances = alert.get("instances") if isinstance(alert.get("instances"), list) else []
            uri = None
            if instances and isinstance(instances[0], dict):
                uri = instances[0].get("uri") if isinstance(instances[0].get("uri"), str) else None
            findings.append(
                Finding(
                    rule_id=f"ZAP-{alert.get('pluginid', 'unknown')}",
                    category="analise-dinamica",
                    severity=severity,
                    confidence="medium",
                    title="Alerta de varredura passiva do ZAP",
                    path=uri,
                    line=None,
                    evidence="ZAP baseline identificou o alerta; evidência HTTP bruta foi omitida do relatório consolidado.",
                    remediation="Reproduza no ambiente autorizado, revise configuração e resposta HTTP, e valide a correção com uma nova execução de baseline.",
                )
            )
    return findings


def _execute(command: list[str], *, cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(cwd),
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _tool_unavailable(name: str) -> ToolExecution:
    return ToolExecution(name, "unavailable", 0, "Executável não encontrado; nenhuma instalação automática foi realizada.")


def run_external_scanners(
    target: Path,
    *,
    opengrep_rules: Path,
    zap_baseline_url: str | None = None,
    zap_authorization: str | None = None,
    zap_image: str | None = None,
) -> tuple[list[Finding], list[ToolExecution]]:
    """Run opt-in scanners and return normalized, non-sensitive evidence only."""

    root = target.resolve()
    findings: list[Finding] = []
    tools: list[ToolExecution] = []
    with tempfile.TemporaryDirectory(prefix="security-master-") as temporary:
        workspace = Path(temporary)
        if shutil.which("gitleaks") is None:
            tools.append(_tool_unavailable("gitleaks"))
        else:
            report = workspace / "gitleaks.json"
            command = [
                "gitleaks",
                "git" if (root / ".git").exists() else "dir",
                "--redact=100",
                "--report-format",
                "json",
                "--report-path",
                str(report),
                str(root),
            ]
            try:
                completed = _execute(command, cwd=root, timeout=180)
                payload = json.loads(report.read_text(encoding="utf-8")) if report.exists() else []
                normalized = _normalize_gitleaks(payload, root)
                findings.extend(normalized)
                status = "completed" if completed.returncode in {0, 1} else "failed"
                tools.append(ToolExecution("gitleaks", status, len(normalized), "Histórico/diretório analisado; valores de segredos não foram preservados."))
            except (OSError, ValueError, json.JSONDecodeError, subprocess.TimeoutExpired):
                tools.append(ToolExecution("gitleaks", "failed", 0, "Execução ou leitura do relatório falhou; saída bruta foi descartada."))

        python_files = any(path.suffix.casefold() == ".py" for path in iter_text_files(root))
        if not python_files:
            tools.append(ToolExecution("bandit", "not_applicable", 0, "Nenhum arquivo Python elegível foi localizado."))
        elif shutil.which("bandit") is None:
            tools.append(_tool_unavailable("bandit"))
        else:
            report = workspace / "bandit.json"
            try:
                completed = _execute(["bandit", "-r", str(root), "-f", "json", "-o", str(report), "-q"], cwd=root, timeout=180)
                payload = json.loads(report.read_text(encoding="utf-8")) if report.exists() else {}
                normalized = _normalize_bandit(payload)
                findings.extend(normalized)
                status = "completed" if completed.returncode in {0, 1} else "failed"
                tools.append(ToolExecution("bandit", status, len(normalized), "Código Python analisado; snippets foram descartados."))
            except (OSError, ValueError, json.JSONDecodeError, subprocess.TimeoutExpired):
                tools.append(ToolExecution("bandit", "failed", 0, "Execução ou leitura do relatório falhou; saída bruta foi descartada."))

        if shutil.which("opengrep") is None:
            tools.append(_tool_unavailable("opengrep"))
        elif not opengrep_rules.is_file():
            tools.append(ToolExecution("opengrep", "failed", 0, "Arquivo de regras informado não existe."))
        else:
            report = workspace / "opengrep.sarif"
            try:
                completed = _execute(
                    ["opengrep", "scan", f"--sarif-output={report}", "-f", str(opengrep_rules), str(root)],
                    cwd=root,
                    timeout=240,
                )
                payload = json.loads(report.read_text(encoding="utf-8")) if report.exists() else {}
                normalized = _normalize_opengrep_sarif(payload)
                findings.extend(normalized)
                status = "completed" if completed.returncode in {0, 1} else "failed"
                tools.append(ToolExecution("opengrep", status, len(normalized), "SAST concluído; snippets foram descartados."))
            except (OSError, ValueError, json.JSONDecodeError, subprocess.TimeoutExpired):
                tools.append(ToolExecution("opengrep", "failed", 0, "Execução ou leitura do relatório falhou; saída bruta foi descartada."))

        if zap_baseline_url is None:
            tools.append(ToolExecution("zap-baseline", "not_requested", 0, "ZAP é opt-in; nenhuma requisição dinâmica foi enviada."))
        elif zap_authorization != "I_AUTHORIZE_BASELINE_SCAN":
            tools.append(ToolExecution("zap-baseline", "blocked", 0, "Execute somente com --zap-authorization I_AUTHORIZE_BASELINE_SCAN."))
        elif not zap_image or "@sha256:" not in zap_image:
            tools.append(ToolExecution("zap-baseline", "blocked", 0, "Informe uma imagem ZAP aprovada e fixada por digest SHA-256."))
        elif shutil.which("docker") is None:
            tools.append(_tool_unavailable("zap-baseline (docker)"))
        else:
            safe_url = _sanitize_target_url(zap_baseline_url)
            report = workspace / "zap.json"
            command = [
                "docker",
                "run",
                "--rm",
                "-v",
                f"{workspace}:/zap/wrk:rw",
                zap_image,
                "zap-baseline.py",
                "-t",
                safe_url,
                "-J",
                "/zap/wrk/zap.json",
            ]
            try:
                completed = _execute(command, cwd=root, timeout=420)
                payload = json.loads(report.read_text(encoding="utf-8")) if report.exists() else {}
                normalized = _normalize_zap(payload)
                findings.extend(normalized)
                status = "completed" if completed.returncode in {0, 1, 2, 3} else "failed"
                tools.append(ToolExecution("zap-baseline", status, len(normalized), "Somente baseline passivo executado em alvo explicitamente autorizado."))
            except (OSError, ValueError, json.JSONDecodeError, subprocess.TimeoutExpired):
                tools.append(ToolExecution("zap-baseline", "failed", 0, "Execução ou leitura do relatório falhou; tráfego e saída bruta não foram registrados aqui."))
    return findings, tools


def build_report(
    target: Path,
    *,
    run_tools: bool = False,
    opengrep_rules: Path | None = None,
    zap_baseline_url: str | None = None,
    zap_authorization: str | None = None,
    zap_image: str | None = None,
) -> dict[str, Any]:
    root = target.resolve()
    findings = static_findings(root)
    tool_executions: list[ToolExecution] = [
        ToolExecution("static-security-master", "completed", len(findings), "Heurísticas locais concluídas; resultados exigem revisão humana.")
    ]
    if run_tools:
        requested_rules = opengrep_rules or Path("security/opengrep-security-master.yml")
        rules = requested_rules if requested_rules.is_absolute() else root / requested_rules
        if not rules.is_file():
            rules = requested_rules.resolve()
        external_findings, external_tools = run_external_scanners(
            root,
            opengrep_rules=rules,
            zap_baseline_url=zap_baseline_url,
            zap_authorization=zap_authorization,
            zap_image=zap_image,
        )
        findings.extend(external_findings)
        tool_executions.extend(external_tools)
    else:
        tool_executions.extend(
            [
                ToolExecution("gitleaks", "not_requested", 0, "Use --run-tools para executar scanners externos."),
                ToolExecution("bandit", "not_requested", 0, "Use --run-tools para executar scanners externos."),
                ToolExecution("opengrep", "not_requested", 0, "Use --run-tools para executar scanners externos."),
                ToolExecution("zap-baseline", "not_requested", 0, "Use --run-tools e parâmetros explícitos de autorização para ZAP baseline."),
            ]
        )
    findings = sorted(findings, key=lambda item: (-SEVERITY_RANK[item.severity], item.path or "", item.line or 0, item.rule_id))
    counts = {severity: sum(item.severity == severity for item in findings) for severity in SEVERITY_RANK}
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "target": str(root),
        "limitations": [
            "Heurísticas estáticas e SAST não provam explorabilidade nem substituem pentest, revisão de arquitetura ou testes de autorização.",
            "O relatório consolidado omite valores de segredos, snippets de código e evidência HTTP bruta.",
            "ZAP, quando solicitado, executa somente baseline passivo; varredura ativa requer escopo, ambiente e autorização separados.",
        ],
        "counts": counts,
        "tools": [asdict(item) for item in tool_executions],
        "findings": [asdict(item) for item in findings],
    }


def write_report(report: dict[str, Any], destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, destination)


def _has_blocking_finding(report: dict[str, Any], threshold: str) -> bool:
    if threshold == "none":
        return False
    limit = SEVERITY_RANK[threshold]
    return any(SEVERITY_RANK.get(str(item.get("severity")), 0) >= limit for item in report.get("findings", []))


def add_arguments(parser: argparse.ArgumentParser) -> None:
    """Attach Security Master arguments to a standalone or parent parser."""

    parser.add_argument("--target", default=".", help="Diretório do repositório a auditar.")
    parser.add_argument("--output", default="security-artifacts/security-master-report.json")
    parser.add_argument("--run-tools", action="store_true", help="Executa Gitleaks, Bandit e Opengrep se já estiverem instalados.")
    parser.add_argument("--require-tools", action="store_true", help="Retorna código 2 se algum scanner aplicável não estiver disponível/concluído.")
    parser.add_argument("--opengrep-rules", default="security/opengrep-security-master.yml")
    parser.add_argument("--fail-on", choices=["critical", "high", "medium", "low", "info", "none"], default="high")
    parser.add_argument("--zap-baseline-url", help="URL de staging explicitamente autorizada para baseline passivo do ZAP.")
    parser.add_argument("--zap-authorization", help="Confirmação literal exigida: I_AUTHORIZE_BASELINE_SCAN.")
    parser.add_argument("--zap-image", help="Imagem ZAP aprovada, fixada por digest (@sha256:...).")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python scripts/security_master.py")
    add_arguments(parser)
    return parser


def run_parsed_args(args: argparse.Namespace) -> int:
    try:
        target = Path(args.target).resolve()
        report = build_report(
            target,
            run_tools=args.run_tools,
            opengrep_rules=Path(args.opengrep_rules),
            zap_baseline_url=args.zap_baseline_url,
            zap_authorization=args.zap_authorization,
            zap_image=args.zap_image,
        )
        output = Path(args.output)
        if not output.is_absolute():
            output = target / output
        write_report(report, output)
        print(json.dumps({"report": str(output), "counts": report["counts"], "tools": report["tools"]}, ensure_ascii=False, indent=2))
        if args.require_tools:
            required = {"gitleaks", "bandit", "opengrep"}
            acceptable = {"completed", "not_applicable"}
            if any(
                item["tool"] in required and item["status"] not in acceptable
                for item in report["tools"]
            ):
                return 2
        return 1 if _has_blocking_finding(report, args.fail_on) else 0
    except (OSError, ValueError) as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 2


def main(argv: list[str] | None = None) -> int:
    return run_parsed_args(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
