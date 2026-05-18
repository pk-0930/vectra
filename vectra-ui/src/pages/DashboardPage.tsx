import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity,
  ArrowRight,
  ClipboardList,
  FileBarChart,
  RefreshCw,
  Target,
  UserPlus,
  UsersRound,
  type LucideIcon,
} from "lucide-react";
import SideNav from "../components/SideNav";
import { listClients } from "../services/clientApi";
import { listNutritionPlans, listWorkoutPlans } from "../services/planApi";
import { listSquatJobs } from "../services/squatApi";
import type { CoachProfile } from "../types/auth";
import type { Client } from "../types/client";
import type { AppTab } from "../types/navigation";
import type { Plan } from "../types/plan";
import type { SquatJobResponse } from "../types/squat";
import { THEME } from "../theme";

type DashboardPageProps = {
  activeTab: AppTab;
  onTabChange: (tab: AppTab) => void;
  onLogout: () => void;
  requestedJob?: SquatJobResponse | null;
  onJobLoaded?: (job: SquatJobResponse) => void;
  selectedClient?: Client | null;
  selectedClientId?: number | null;
  coach?: CoachProfile | null;
};

export default function DashboardPage({
  activeTab,
  onTabChange,
  onLogout,
  selectedClient,
  selectedClientId,
  coach,
}: DashboardPageProps) {
  const [clients, setClients] = useState<Client[]>([]);
  const [analyses, setAnalyses] = useState<SquatJobResponse[]>([]);
  const [nutritionPlans, setNutritionPlans] = useState<Plan[]>([]);
  const [workoutPlans, setWorkoutPlans] = useState<Plan[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  const loadDashboard = useCallback(async () => {
    try {
      setIsLoading(true);
      setError("");
      const [clientResponse, analysisResponse] = await Promise.all([
        listClients(),
        listSquatJobs(12),
      ]);

      setClients(clientResponse);
      setAnalyses(analysisResponse.analyses);

      if (selectedClientId) {
        const [nutritionResponse, workoutResponse] = await Promise.all([
          listNutritionPlans(selectedClientId),
          listWorkoutPlans(selectedClientId),
        ]);
        setNutritionPlans(nutritionResponse);
        setWorkoutPlans(workoutResponse);
      } else {
        setNutritionPlans([]);
        setWorkoutPlans([]);
      }
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Failed to load dashboard.");
    } finally {
      setIsLoading(false);
    }
  }, [selectedClientId]);

  useEffect(() => {
    loadDashboard();
  }, [loadDashboard]);

  const activeClients = clients.filter((client) => client.is_active).length;
  const clientsWithGoals = clients.filter((client) => client.current_goal_type).length;
  const latestAnalysis = analyses[0] ?? null;
  const latestPlan = useMemo(() => {
    return [...nutritionPlans, ...workoutPlans].sort(
      (left, right) => new Date(right.created_at).getTime() - new Date(left.created_at).getTime()
    )[0] ?? null;
  }, [nutritionPlans, workoutPlans]);

  const completedAnalyses = analyses.filter((analysis) => analysis.status === "completed").length;
  const activeAnalyses = analyses.filter(
    (analysis) => analysis.status === "queued" || analysis.status === "running"
  ).length;

  return (
    <div style={styles.page}>
      <SideNav activeTab={activeTab} onTabChange={onTabChange} />

      <main style={styles.main}>
        <div style={styles.header}>
          <div>
            <h1 style={styles.pageTitle}>Dashboard</h1>
            <p style={styles.pageSubtitle}>
              {coach
                ? `Welcome ${coach.first_name}. Your coaching workspace is ready for today's client work.`
                : "A calm overview of clients, goals, analyses, and recent planning activity."}
            </p>
          </div>
          <div style={styles.headerActions}>
            <button style={styles.secondaryButton} onClick={loadDashboard} disabled={isLoading}>
              <RefreshCw size={16} />
              {isLoading ? "Refreshing..." : "Refresh"}
            </button>
            <button style={styles.secondaryButton} onClick={onLogout}>Logout</button>
          </div>
        </div>

        {error ? <div style={styles.errorBox}>{error}</div> : null}

        <section style={styles.kpiGrid}>
          <KpiCard icon={UsersRound} label="Total clients" value={clients.length} helper="All client records" />
          <KpiCard icon={Activity} label="Active clients" value={activeClients} helper="Currently in coaching flow" />
          <KpiCard icon={Target} label="Clients with goals" value={clientsWithGoals} helper="Current goal assigned" />
          <KpiCard
            icon={FileBarChart}
            label="Recent analyses"
            value={analyses.length}
            helper={`${completedAnalyses} complete, ${activeAnalyses} in progress`}
          />
        </section>

        <section style={styles.navigationGrid}>
          <div style={styles.panel}>
            <SectionHeader
              icon={UsersRound}
              title="Client workspace"
              meta={selectedClient ? `${selectedClient.first_name} ${selectedClient.last_name}` : "No client selected"}
            />
            <p style={styles.panelText}>
              Profile updates, nutrition planning, workout planning, progress photos, and form analysis now live inside each client workspace.
            </p>
            <button style={styles.primaryButton} onClick={() => onTabChange("clients")}>
              Open client workspace
              <ArrowRight size={16} />
            </button>
          </div>

          <div style={styles.panel}>
            <SectionHeader icon={FileBarChart} title="Recent analysis snapshot" meta={latestAnalysis ? formatJobStatus(latestAnalysis.status) : "Empty"} />
            <p style={styles.panelText}>
              {latestAnalysis
                ? `${latestAnalysis.original_filename} · ${formatDate(latestAnalysis.created_at)}`
                : "No form analysis jobs have been created yet."}
            </p>
            <button style={styles.secondaryButton} onClick={() => onTabChange("recent-analysis")}>
              <ClipboardList size={16} />
              Review recent analyses
            </button>
          </div>

          <div style={styles.panel}>
            <SectionHeader
              icon={ClipboardList}
              title="Recent plan activity"
              meta={selectedClient ? `${nutritionPlans.length + workoutPlans.length} plans` : "Select a client"}
            />
            <p style={styles.panelText}>
              {latestPlan
                ? `${latestPlan.title} · ${latestPlan.period_type} plan updated ${formatDate(latestPlan.updated_at)}`
                : selectedClient
                  ? "No nutrition or workout plans have been created for the selected client."
                  : "Choose a client to see their latest nutrition and workout planning activity."}
            </p>
            <button style={styles.secondaryButton} onClick={() => onTabChange("clients")}>
              <UserPlus size={16} />
              Create client
            </button>
          </div>
        </section>
      </main>
    </div>
  );
}

function KpiCard({ icon: Icon, label, value, helper }: { icon: LucideIcon; label: string; value: number; helper: string }) {
  return (
    <div style={styles.kpiCard}>
      <div style={styles.kpiTopRow}>
        <div style={styles.kpiIcon}><Icon size={20} /></div>
        <div style={styles.kpiLabel}>{label}</div>
      </div>
      <div style={styles.kpiValue}>{value}</div>
      <div style={styles.kpiHelper}>{helper}</div>
    </div>
  );
}

function SectionHeader({ icon: Icon, title, meta }: { icon?: LucideIcon; title: string; meta?: string }) {
  return (
    <div style={styles.panelHeader}>
      <div style={styles.panelTitleRow}>
        {Icon ? <div style={styles.panelIcon}><Icon size={18} /></div> : null}
        <div style={styles.panelTitle}>{title}</div>
      </div>
      {meta ? <div style={styles.metaPill}>{meta}</div> : null}
    </div>
  );
}

function formatJobStatus(status: string) {
  switch (status) {
    case "queued":
      return "Queued";
    case "running":
      return "Running";
    case "completed":
      return "Completed";
    case "failed":
      return "Failed";
    default:
      return "Unknown";
  }
}

function formatDate(value: string) {
  return new Date(value).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

const styles: Record<string, React.CSSProperties> = {
  page: { minHeight: "100vh", display: "flex", background: THEME.gradients.app },
  main: { flex: 1, padding: 24, boxSizing: "border-box" },
  header: { display: "flex", justifyContent: "space-between", alignItems: "start", gap: 16, marginBottom: 24 },
  headerActions: { display: "flex", gap: 12 },
  pageTitle: { margin: 0, fontSize: THEME.typography.pageTitle, color: THEME.colors.ink },
  pageSubtitle: { margin: "10px 0 0", color: THEME.colors.textSoft, lineHeight: 1.5 },
  kpiGrid: { display: "grid", gridTemplateColumns: "repeat(4, minmax(0, 1fr))", gap: 16, marginBottom: 20 },
  kpiCard: { background: THEME.colors.surface, border: `1px solid ${THEME.colors.border}`, borderRadius: THEME.radii.panel, padding: 20, boxShadow: THEME.shadows.card, position: "relative", overflow: "hidden" },
  kpiTopRow: { display: "flex", alignItems: "center", gap: 10 },
  kpiIcon: { width: 38, height: 38, borderRadius: THEME.radii.md, backgroundColor: THEME.colors.primaryMuted, color: THEME.colors.primaryDeep, display: "flex", alignItems: "center", justifyContent: "center", boxShadow: "0 8px 18px rgba(37,99,235,0.14)" },
  kpiLabel: { color: THEME.colors.textMuted, fontSize: 13, fontWeight: 700 },
  kpiValue: { marginTop: 12, color: THEME.colors.text, fontSize: 36, lineHeight: 1, fontWeight: 800 },
  kpiHelper: { marginTop: 10, color: THEME.colors.textSoft, fontSize: 13 },
  navigationGrid: { display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 16 },
  panel: { background: THEME.colors.surface, border: `1px solid ${THEME.colors.border}`, borderRadius: THEME.radii.panel, padding: 20, boxShadow: THEME.shadows.card },
  panelHeader: { display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, marginBottom: 14 },
  panelTitle: { fontSize: 18, fontWeight: 800, color: THEME.colors.text },
  panelTitleRow: { display: "flex", alignItems: "center", gap: 10 },
  panelIcon: { width: 34, height: 34, borderRadius: THEME.radii.md, backgroundColor: THEME.colors.accentMuted, color: THEME.colors.accentDeep, display: "flex", alignItems: "center", justifyContent: "center" },
  panelText: { color: THEME.colors.textSoft, lineHeight: 1.6, minHeight: 78 },
  metaPill: { borderRadius: THEME.radii.pill, backgroundColor: THEME.colors.surfaceMuted, color: THEME.colors.textMuted, padding: "6px 10px", fontSize: 12, fontWeight: 700, whiteSpace: "nowrap" },
  primaryButton: { display: "inline-flex", alignItems: "center", gap: 8, padding: "11px 14px", borderRadius: THEME.radii.sm, border: "none", backgroundColor: THEME.colors.indigo, color: THEME.colors.white, fontWeight: 700, cursor: "pointer", boxShadow: `0 10px 22px ${THEME.shadows.primarySoft}` },
  secondaryButton: { display: "inline-flex", alignItems: "center", gap: 8, padding: "10px 14px", borderRadius: THEME.radii.sm, border: `1px solid ${THEME.colors.borderStrong}`, backgroundColor: "rgba(255,255,255,0.78)", color: THEME.colors.primaryDeep, fontWeight: 700, cursor: "pointer" },
  errorBox: { backgroundColor: THEME.colors.dangerSurface, color: THEME.colors.danger, border: "1px solid #fecaca", borderRadius: THEME.radii.sm, padding: 14, marginBottom: 16 },
};
