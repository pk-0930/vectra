import React from "react";
import { Construction } from "lucide-react";
import SideNav from "../components/SideNav";
import type { AppTab } from "../types/navigation";
import { THEME } from "../theme";

type PlaceholderPageProps = {
  activeTab: AppTab;
  onTabChange: (tab: AppTab) => void;
  onLogout: () => void;
};

const pageCopy: Record<Exclude<AppTab, "dashboard" | "recent-analysis">, {
  title: string;
  subtitle: string;
}> = {
  clients: {
    title: "Clients",
    subtitle: "Athlete profiles, grouped movement history, and coach notes will live here.",
  },
  sessions: {
    title: "Sessions",
    subtitle: "Session planning, review queues, and follow-up workflows are coming next.",
  },
  insights: {
    title: "Insights",
    subtitle: "Trend views and aggregated movement insights will be added here.",
  },
  settings: {
    title: "Settings",
    subtitle: "Environment configuration, sharing defaults, and coach preferences will live here.",
  },
};

export default function PlaceholderPage({
  activeTab,
  onTabChange,
  onLogout,
}: PlaceholderPageProps) {
  const copy = pageCopy[activeTab as keyof typeof pageCopy];

  return (
    <div style={styles.page}>
      <SideNav activeTab={activeTab} onTabChange={onTabChange} subtitle="Trainer Workspace">
        <div style={styles.infoCard}>
          <div style={styles.infoTitle}><Construction size={16} /> In progress</div>
          <div style={styles.infoText}>
            This section is intentionally scaffolded so we can keep navigation stable while
            building the production beta feature set.
          </div>
        </div>
      </SideNav>

      <main style={styles.main}>
        <div style={styles.panel}>
          <div style={styles.panelTopRow}>
            <div />
            <button style={styles.secondaryButton} onClick={onLogout}>Logout</button>
          </div>
          <h1 style={styles.pageTitle}>{copy.title}</h1>
          <p style={styles.pageSubtitle}>{copy.subtitle}</p>
          <div style={styles.bodyText}>
            We now have a stable dashboard flow and a dedicated recent-analysis library. This
            tab is ready for the next implementation slice when you want to build it.
          </div>
        </div>
      </main>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: {
    minHeight: "100vh",
    display: "flex",
    background: THEME.gradients.app,
  },
  sidebar: {
    width: "280px",
    backgroundColor: "#ffffff",
    borderRight: "1px solid #e2e8f0",
    padding: "20px",
    boxSizing: "border-box",
  },
  brandRow: {
    display: "flex",
    alignItems: "center",
    gap: "12px",
  },
  brandIcon: {
    width: "40px",
    height: "40px",
    borderRadius: "14px",
    backgroundColor: THEME.colors.primary,
    color: THEME.colors.white,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontWeight: 700,
  },
  brandTitle: {
    fontSize: "18px",
    fontWeight: 700,
  },
  brandSubtitle: {
    fontSize: "12px",
    color: "#64748b",
  },
  infoCard: {
    backgroundColor: "rgba(255,255,255,0.07)",
    color: THEME.colors.white,
    borderRadius: THEME.radii.md,
    padding: "16px",
    border: `1px solid rgba(37,99,235,0.24)`,
  },
  infoTitle: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    fontSize: "14px",
    fontWeight: 700,
    marginBottom: "8px",
  },
  infoText: {
    fontSize: "12px",
    color: "#cbd5e1",
    lineHeight: 1.6,
  },
  navSection: {
    marginTop: "24px",
    display: "flex",
    flexDirection: "column",
    gap: "8px",
  },
  navItemActive: {
    padding: "10px 12px",
    borderRadius: "12px",
    backgroundColor: "#f1f5f9",
    fontWeight: 600,
    border: "none",
    textAlign: "left",
    cursor: "pointer",
  },
  navItem: {
    padding: "10px 12px",
    borderRadius: "12px",
    color: "#64748b",
    border: "none",
    backgroundColor: "transparent",
    textAlign: "left",
    cursor: "pointer",
  },
  main: {
    flex: 1,
    padding: "24px",
    boxSizing: "border-box",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  },
  panel: {
    width: "100%",
    maxWidth: "760px",
    backgroundColor: "rgba(255,255,255,0.88)",
    border: "1px solid #e2e8f0",
    borderRadius: THEME.radii.panel,
    padding: "36px",
    boxShadow: `0 10px 30px ${THEME.shadows.primarySoft}`,
  },
  panelTopRow: {
    display: "flex",
    justifyContent: "space-between",
    marginBottom: "8px",
  },
  pageTitle: {
    margin: 0,
    fontSize: "32px",
    fontWeight: 700,
    color: THEME.colors.ink,
  },
  pageSubtitle: {
    marginTop: "10px",
    color: "#475569",
    fontSize: "16px",
    lineHeight: 1.6,
  },
  bodyText: {
    marginTop: "20px",
    fontSize: "15px",
    color: "#64748b",
    lineHeight: 1.7,
  },
  secondaryButton: {
    display: "inline-flex",
    alignItems: "center",
    gap: 8,
    padding: "10px 14px",
    borderRadius: "12px",
    border: "1px solid #cbd5e1",
    backgroundColor: "rgba(255,255,255,0.82)",
    color: THEME.colors.primaryDeep,
    fontWeight: 600,
    cursor: "pointer",
  },
};
