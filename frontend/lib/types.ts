// ── Enums ─────────────────────────────────────────────────────────────────────

export type SportType =
  | "cycling"
  | "running"
  | "swimming"
  | "triathlon"
  | "strength"
  | "rest"
  | "mobility"
  | "other";

export type WorkoutSource = "strava" | "trainingpeaks" | "garmin" | "manual" | "planned";

export type UserRole = "admin" | "athlete";

export type AIProvider = "anthropic" | "openai";

// ── Auth ──────────────────────────────────────────────────────────────────────

export interface AuthState {
  accessToken: string | null;
  role: UserRole | null;
  profile: AdminProfile | AthleteProfile | null;
}

// ── Admin ─────────────────────────────────────────────────────────────────────

export interface AdminProfile {
  id: string;
  user_id: string;
  name: string;
  email: string;
  crm: string | null;
  stripe_account_id: string | null;
  is_active: boolean;
  created_at: string;
}

// ── Athlete ───────────────────────────────────────────────────────────────────

export interface WeeklyAvailability {
  cycling: string[];
  strength: string[];
  running?: string[];
  swimming?: string[];
}

export interface AthleteProfile {
  id: string;
  user_id: string;
  admin_id: string;
  name: string;
  email: string;
  phone: string | null;
  birth_date: string | null;
  gender: string | null;
  height_cm: number | null;
  weight_kg: number | null;
  sport_modalities: string[];
  primary_modality: string | null;
  fitness_level: string | null;
  ftp_watts: number | null;
  max_hr: number | null;
  resting_hr: number | null;
  goal: string | null;
  weekly_availability: WeeklyAvailability | null;
  onboarding_complete: boolean;
  auto_report_enabled: boolean;
  /** Token do atalho iOS do Apple Health. Retornado por GET /api/auth/me. */
  apple_health_token: string | null;
  is_active: boolean;
  created_at: string;
}

// ── Workouts ──────────────────────────────────────────────────────────────────

export interface Workout {
  id: string;
  athlete_id: string;
  external_id: string | null;
  source: WorkoutSource;
  sport_type: SportType;
  title: string | null;
  description: string | null;
  start_time: string;
  duration_seconds: number | null;
  distance_meters: number | null;
  elevation_gain_meters: number | null;
  avg_heart_rate: number | null;
  max_heart_rate: number | null;
  avg_power_watts: number | null;
  normalized_power_watts: number | null;
  max_power_watts: number | null;
  avg_cadence: number | null;
  calories: number | null;
  tss: number | null;
  if_score: number | null;
  hr_zones: Record<string, number> | null;
  power_zones: Record<string, number> | null;
  is_completed: boolean;
  created_at: string;
}

// ── Strength ──────────────────────────────────────────────────────────────────

export interface StrengthExercise {
  id: string;
  exercise_name: string;
  sets: number;
  reps: number | null;
  duration_seconds: number | null;
  load_kg: number | null;
  rpe: number | null;
  notes: string | null;
  exercise_order: number | null;
}

export interface StrengthSession {
  id: string;
  athlete_id: string;
  session_date: string;
  session_type: string | null;
  duration_minutes: number | null;
  rpe_overall: number | null;
  notes: string | null;
  tss: number | null;
  exercises: StrengthExercise[];
  created_at: string;
}

// ── Daily Metrics ─────────────────────────────────────────────────────────────

export interface DailyMetrics {
  id: string;
  athlete_id: string;
  metric_date: string;
  weight_kg: number | null;
  sleep_hours: number | null;
  sleep_quality: number | null;
  hrv_ms: number | null;
  resting_hr: number | null;
  fatigue_score: number | null;
  muscle_soreness: number | null;
  stress_score: number | null;
  motivation_score: number | null;
  notes: string | null;
  source: string;
}

// ── Training Load ─────────────────────────────────────────────────────────────

export interface TrainingLoad {
  load_date: string;
  ctl: number;
  atl: number;
  tsb: number;
  daily_tss: number;
  weekly_tss: number;
}

// ── AI Recommendations ────────────────────────────────────────────────────────

export interface TrainingSection {
  name: string;
  duration_minutes: number;
  description: string;
  targets: {
    power_pct_ftp?: number;
    hr_zone?: number;
    rpe?: number;
  };
}

export interface ExerciseBlock {
  name: string;
  sets: number;
  reps: string;
  load: string;
  rest_seconds: number;
  notes: string;
}

export interface StructuredPlan {
  duration_minutes: number;
  intensity: "easy" | "moderate" | "hard" | "very_hard";
  sections: TrainingSection[];
  exercises: ExerciseBlock[];
  key_metrics_considered: string[];
  cautions: string[];
}

export interface NutritionPlan {
  calories_target: number | null;
  carbs_g: number | null;
  protein_g: number | null;
  fat_g: number | null;
  hydration_ml: number | null;
  pre_workout: string | null;
  during_workout: string | null;
  post_workout: string | null;
  notes: string | null;
}

export interface AIRecommendation {
  id: string;
  athlete_id: string;
  recommendation_date: string;
  ai_provider: AIProvider;
  ai_model: string | null;
  workout_type: string | null;
  title: string | null;
  recommendation_text: string;
  structured_plan: StructuredPlan | null;
  nutrition_plan: NutritionPlan | null;
  rationale: string | null;
  feedback_rating: number | null;
  feedback_notes: string | null;
  was_followed: boolean | null;
  created_at: string;
}

// ── LGPD ──────────────────────────────────────────────────────────────────────

export interface LGPDConsentStatus {
  has_consent: boolean;
  version: string | null;
  consented_at: string | null;
  revoked_at: string | null;
}

// ── API generic wrappers ──────────────────────────────────────────────────────

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  per_page: number;
}

export interface ApiError {
  detail: string;
}

// ── Admin Alerts ──────────────────────────────────────────────────────────────

export type AlertType = "overreaching" | "no_workout" | "no_metrics" | "sync_failure" | "milestone" | "weekly_report";
export type AlertSeverity = "critical" | "warning" | "info";

export interface AdminAlert {
  id: string;
  athlete_id: string | null;
  athlete_name: string | null;
  alert_type: AlertType;
  severity: AlertSeverity;
  title: string;
  body: string | null;
  is_read: boolean;
  created_at: string;
}

export interface AlertSummary {
  total_unread: number;
  critical: number;
  warning: number;
  info: number;
}

// ── Admin Dashboard ───────────────────────────────────────────────────────────

// ── Billing ───────────────────────────────────────────────────────────────────

export type PlanKey = "trial" | "starter" | "pro" | "elite";
export type SubscriptionStatus = "active" | "trialing" | "past_due" | "canceled" | "incomplete";

export interface CurrentPlan {
  plan: PlanKey;
  label: string;
  status: SubscriptionStatus;
  athlete_limit: number;
  athlete_count: number;
  can_add_athlete: boolean;
  price_brl: number;
  description: string;
  current_period_end: string | null;
  stripe_customer_id: string | null;
}

export interface BillingPlan {
  key: PlanKey;
  label: string;
  athlete_limit: number;
  price_brl: number;
  description: string;
  purchasable: boolean;
}

// ── Admin Dashboard ───────────────────────────────────────────────────────────

export interface AdminDashboardAthlete {
  id: string;
  name: string;
  email: string;
  primary_modality: string | null;
  onboarding_complete: boolean;
  is_active: boolean;
  training_load: {
    ctl: number | null;
    atl: number | null;
    tsb: number | null;
    tsb_status: "good" | "moderate" | "alert" | "critical" | "unknown";
    load_date: string | null;
  };
  days_since_last_workout: number | null;
  no_workout_alert: boolean;
}
