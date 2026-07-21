"use client";

import { useEffect, useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import api from "@/lib/api";
import { useAuthStore } from "@/lib/store/authStore";
import type { AthleteProfile } from "@/lib/types";

const CONSENT_VERSION = "1.0";

const TERMS_TEXT = `
**Termos de Uso e Política de Privacidade — FitCoach AI**

Em conformidade com a Lei Geral de Proteção de Dados (LGPD — Lei 13.709/2018):

**Dados coletados:** Coletamos dados de saúde e desempenho esportivo (FC, potência, peso, sono, métricas subjetivas) e dados de plataformas conectadas (Strava, Garmin, TrainingPeaks) mediante sua autorização.

**Finalidade:** Os dados são usados exclusivamente para gerar recomendações personalizadas de treino. Nenhum dado é compartilhado com terceiros além das plataformas que você conectar.

**Segurança:** Dados sensíveis são criptografados com AES-256. Tokens OAuth são armazenados cifrados.

**Seus direitos (Art. 18 LGPD):** Acesso, correção, exclusão (atendida em ≤ 72h) e exportação dos seus dados.

**Contato:** privacidade@fitcoachai.com
`.trim();

type Step = "invite" | "set-password" | "lgpd" | "profile" | "done";

function OnboardingContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const inviteToken = searchParams.get("token");
  const { profile, setAuth, role } = useAuthStore();

  const [step, setStep] = useState<Step>(inviteToken ? "invite" : "lgpd");
  const [inviteInfo, setInviteInfo] = useState<{ name: string; email: string } | null>(null);
  const [tokenValid, setTokenValid] = useState<boolean | null>(null);

  // Invite flow state
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  // LGPD state
  const [agreed, setAgreed] = useState(false);

  // Profile state
  const [phone, setPhone] = useState("");
  const [birthDate, setBirthDate] = useState("");
  const [gender, setGender] = useState("");
  const [heightCm, setHeightCm] = useState("");
  const [weightKg, setWeightKg] = useState("");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Validate invite token on mount
  useEffect(() => {
    if (!inviteToken) return;
    api.get(`/api/auth/onboarding/validate?token=${inviteToken}`)
      .then((r) => {
        if (r.data.valid) {
          setInviteInfo({ name: r.data.name, email: r.data.email });
          setTokenValid(true);
          setStep("invite");
        } else {
          setTokenValid(false);
        }
      })
      .catch(() => setTokenValid(false));
  }, [inviteToken]);

  const handleSetPassword = async () => {
    if (password !== confirmPassword) { setError("Senhas não conferem"); return; }
    if (password.length < 8) { setError("Senha deve ter ao menos 8 caracteres"); return; }
    setLoading(true); setError(null);
    try {
      const resp = await api.post("/api/auth/athlete/set-password", {
        invite_token: inviteToken,
        password,
        confirm_password: confirmPassword,
      });
      // Store the token so subsequent calls are authenticated
      const me = await api.get("/api/auth/me");
      setAuth("athlete", me.data as AthleteProfile);
      setStep("lgpd");
    } catch (e: unknown) {
      setError((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Erro ao definir senha.");
    } finally {
      setLoading(false);
    }
  };

  const handleAcceptTerms = async () => {
    if (!agreed) return;
    setLoading(true); setError(null);
    try {
      await api.post("/api/lgpd/consent", { consent_version: CONSENT_VERSION });
      setStep("profile");
    } catch {
      setError("Erro ao registrar consentimento.");
    } finally {
      setLoading(false);
    }
  };

  const handleSaveProfile = async () => {
    setLoading(true); setError(null);
    try {
      const body: Record<string, unknown> = {};
      if (phone) body.phone = phone;
      if (birthDate) body.birth_date = birthDate;
      if (gender) body.gender = gender;
      if (heightCm) body.height_cm = parseFloat(heightCm);
      if (weightKg) body.weight_kg = parseFloat(weightKg);
      if (Object.keys(body).length > 0) await api.put("/api/auth/me", body);
      const me = await api.get("/api/auth/me");
      setAuth(role ?? "athlete", me.data as AthleteProfile);
      setStep("done");
    } catch {
      setError("Erro ao salvar perfil.");
    } finally {
      setLoading(false);
    }
  };

  const steps: Step[] = inviteToken
    ? ["invite", "lgpd", "profile", "done"]
    : ["lgpd", "profile", "done"];

  const stepIndex = steps.indexOf(step);

  if (inviteToken && tokenValid === false) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
        <div className="bg-white rounded-2xl border border-gray-200 p-8 text-center max-w-md w-full">
          <div className="text-4xl mb-4">⚠️</div>
          <h2 className="text-lg font-semibold text-gray-900 mb-2">Link de convite inválido</h2>
          <p className="text-sm text-gray-500">
            Este link expirou (válido por 7 dias) ou já foi utilizado. Solicite um novo convite ao seu treinador.
          </p>
        </div>
      </div>
    );
  }

  if (inviteToken && tokenValid === null) {
    return <div className="min-h-screen bg-gray-50 flex items-center justify-center text-gray-400">Validando convite…</div>;
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-lg">
        {/* Progress */}
        <div className="flex items-center justify-center gap-2 mb-8">
          {steps.filter((s) => s !== "done").map((s, i) => {
            const done = stepIndex > steps.indexOf(s);
            const current = step === s;
            return (
              <div key={s} className="flex items-center gap-2">
                <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-colors ${
                  done ? "bg-green-500 text-white" : current ? "bg-brand-600 text-white" : "bg-gray-200 text-gray-500"
                }`}>
                  {done ? "✓" : i + 1}
                </div>
                {i < steps.filter((s) => s !== "done").length - 1 && (
                  <div className="w-8 h-0.5 bg-gray-200" />
                )}
              </div>
            );
          })}
        </div>

        {/* ── Step: Set password (invite flow) ── */}
        {step === "invite" && (
          <div className="bg-white rounded-2xl border border-gray-200 p-8">
            <h2 className="text-xl font-semibold text-gray-900 mb-1">
              Olá, {inviteInfo?.name.split(" ")[0]}! 👋
            </h2>
            <p className="text-sm text-gray-500 mb-6">
              Crie sua senha para acessar o FitCoach AI.
            </p>
            <p className="text-xs text-gray-400 bg-gray-50 rounded-lg px-3 py-2 mb-5">
              Conta: <strong>{inviteInfo?.email}</strong>
            </p>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Nova senha</label>
                <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-brand-500"
                  placeholder="Mínimo 8 caracteres" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Confirmar senha</label>
                <input type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-brand-500"
                  placeholder="Repita a senha" />
              </div>
            </div>
            {error && <div className="mt-4 text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</div>}
            <button onClick={handleSetPassword} disabled={loading || !password || !confirmPassword}
              className="mt-6 w-full rounded-lg bg-brand-600 py-2.5 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-40 transition-colors">
              {loading ? "Criando conta…" : "Criar conta e continuar"}
            </button>
          </div>
        )}

        {/* ── Step: LGPD ── */}
        {step === "lgpd" && (
          <div className="bg-white rounded-2xl border border-gray-200 p-8">
            <h2 className="text-xl font-semibold text-gray-900 mb-1">
              Bem-vindo, {(profile as AthleteProfile)?.name?.split(" ")[0] ?? "atleta"}!
            </h2>
            <p className="text-sm text-gray-500 mb-5">Leia e aceite os termos antes de continuar.</p>
            <div className="rounded-lg border border-gray-200 bg-gray-50 p-4 h-56 overflow-y-auto text-xs text-gray-600 whitespace-pre-wrap leading-relaxed mb-5">
              {TERMS_TEXT}
            </div>
            <label className="flex items-start gap-3 cursor-pointer mb-6">
              <input type="checkbox" checked={agreed} onChange={(e) => setAgreed(e.target.checked)}
                className="mt-0.5 h-4 w-4 rounded border-gray-300 text-brand-600" />
              <span className="text-sm text-gray-700">
                Li e concordo com os Termos de Uso e autorizo o tratamento dos meus dados conforme a LGPD.
              </span>
            </label>
            {error && <div className="mb-4 text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</div>}
            <button onClick={handleAcceptTerms} disabled={!agreed || loading}
              className="w-full rounded-lg bg-brand-600 py-2.5 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-40 transition-colors">
              {loading ? "Registrando…" : "Aceitar e continuar"}
            </button>
          </div>
        )}

        {/* ── Step: Profile ── */}
        {step === "profile" && (
          <div className="bg-white rounded-2xl border border-gray-200 p-8">
            <h2 className="text-xl font-semibold text-gray-900 mb-1">Complete seu perfil</h2>
            <p className="text-sm text-gray-500 mb-5">Opcional — ajuda a IA a personalizar os treinos.</p>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Data de nascimento</label>
                  <input type="date" value={birthDate} onChange={(e) => setBirthDate(e.target.value)}
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-brand-500" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Sexo</label>
                  <select value={gender} onChange={(e) => setGender(e.target.value)}
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-brand-500">
                    <option value="">Selecione</option>
                    <option value="male">Masculino</option>
                    <option value="female">Feminino</option>
                    <option value="other">Outro</option>
                  </select>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Altura (cm)</label>
                  <input type="number" value={heightCm} onChange={(e) => setHeightCm(e.target.value)}
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-brand-500" placeholder="175" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Peso (kg)</label>
                  <input type="number" step="0.1" value={weightKg} onChange={(e) => setWeightKg(e.target.value)}
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-brand-500" placeholder="70.0" />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Telefone</label>
                <input type="tel" value={phone} onChange={(e) => setPhone(e.target.value)}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-brand-500" placeholder="+55 11 99999-9999" />
              </div>
            </div>
            {error && <div className="mt-4 text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</div>}
            <div className="mt-6 flex gap-3">
              <button onClick={handleSaveProfile} disabled={loading}
                className="flex-1 rounded-lg bg-brand-600 py-2.5 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-40 transition-colors">
                {loading ? "Salvando…" : "Salvar e continuar"}
              </button>
              <button onClick={() => setStep("done")}
                className="px-4 rounded-lg border border-gray-300 text-sm text-gray-600 hover:bg-gray-50">
                Pular
              </button>
            </div>
          </div>
        )}

        {/* ── Step: Done ── */}
        {step === "done" && (
          <div className="bg-white rounded-2xl border border-gray-200 p-8 text-center">
            <div className="w-16 h-16 rounded-full bg-green-100 flex items-center justify-center mx-auto mb-4 text-3xl">🎯</div>
            <h2 className="text-xl font-semibold text-gray-900 mb-2">Tudo pronto!</h2>
            <p className="text-sm text-gray-500 mb-2">
              Seu perfil está configurado. Conecte o Strava para que a IA comece a gerar recomendações personalizadas.
            </p>
            <p className="text-xs text-gray-400 mb-6">Você pode conectar plataformas depois em Configurações → Integrações.</p>
            <div className="flex flex-col gap-3">
              <button onClick={() => router.push("/auth/callback/strava")}
                className="w-full rounded-lg border-2 border-orange-500 text-orange-600 py-2.5 text-sm font-semibold hover:bg-orange-50 transition-colors">
                Conectar Strava agora
              </button>
              <button onClick={() => router.push("/dashboard")}
                className="w-full rounded-lg bg-brand-600 py-2.5 text-sm font-semibold text-white hover:bg-brand-700 transition-colors">
                Ir para o dashboard
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function OnboardingPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-gray-50 flex items-center justify-center text-gray-400">Carregando…</div>}>
      <OnboardingContent />
    </Suspense>
  );
}
