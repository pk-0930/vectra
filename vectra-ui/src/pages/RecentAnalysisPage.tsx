import React, { useEffect, useState } from "react";
import { ClipboardList, RefreshCw } from "lucide-react";
import SideNav from "../components/SideNav";
import { API_BASE_URL } from "../services/apiConfig";
import { listSquatJobs } from "../services/squatApi";
import type { AppTab } from "../types/navigation";
import type { SquatJobResponse } from "../types/squat";
import { THEME } from "../theme";

type RecentAnalysisPageProps = {
  activeTab: AppTab;
  onTabChange: (tab: AppTab) => void;
  onLogout: () => void;
  onOpenAnalysis: (job: SquatJobResponse) => void;
  selectedJobId?: string | null;
};

export default function RecentAnalysisPage({
  activeTab,
  onTabChange,
  onLogout,
  onOpenAnalysis,
  selectedJobId,
}: RecentAnalysisPageProps) {
  const [jobs, setJobs] = useState<SquatJobResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  async function loadJobs() {
    try {
      setIsLoading(true);
      setError("");
      const response = await listSquatJobs(24);
      setJobs(response.analyses);
    } catch (loadError) {
      const message =
        loadError instanceof Error ? loadError.message : "Failed to load recent analyses.";
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    loadJobs();
  }, []);

  return (
    <div style={styles.page}>
      <SideNav activeTab={activeTab} onTabChange={onTabChange} subtitle="Trainer Workspace">
        <div style={styles.infoCard}>
          <div style={styles.infoTitle}>Review library</div>
          <div style={styles.infoText}>
            Browse recent squat analyses, inspect annotated thumbnails, and reopen any
            session in its client workspace.
          </div>
        </div>
      </SideNav>

      <main style={styles.main}>
        <div style={styles.header}>
        <div>
          <h1 style={styles.pageTitle}>Recent Analysis</h1>
          <p style={styles.pageSubtitle}>
            Past squat analyses with annotated snapshots ready for quick reopen.
          </p>
        </div>

        <div style={styles.headerActions}>
          <button style={styles.secondaryButton} onClick={onLogout}>Logout</button>
          <button style={styles.refreshButton} onClick={loadJobs} disabled={isLoading}>
            <RefreshCw size={16} />
            {isLoading ? "Refreshing..." : "Refresh list"}
          </button>
        </div>
      </div>

        {error ? <div style={styles.errorBox}>{error}</div> : null}

        {!jobs.length && !isLoading ? (
          <div style={styles.emptyState}>
            <div style={styles.emptyIcon}><ClipboardList size={20} /></div>
            <div style={styles.emptyTitle}>No analyses yet</div>
            <div style={styles.emptyText}>
              Upload a squat video from a client's Form Analysis tab to start building your review
              history.
            </div>
          </div>
        ) : null}

        <div style={styles.grid}>
          {jobs.map((job) => {
            const thumbnailPath = getThumbnailPath(job);
            const isActive = selectedJobId === job.id;

            return (
              <button
                key={job.id}
                style={isActive ? styles.analysisCardActive : styles.analysisCard}
                onClick={() => onOpenAnalysis(job)}
              >
                <div style={styles.thumbnailFrame}>
                  {thumbnailPath ? (
                    <img
                      src={`${API_BASE_URL}${thumbnailPath}`}
                      alt={`${job.original_filename} annotated frame`}
                      style={styles.thumbnailImage}
                    />
                  ) : (
                    <div style={styles.thumbnailPlaceholder}>
                      {job.status === "completed" ? "No thumbnail" : formatJobStatus(job.status)}
                    </div>
                  )}
                </div>

                <div style={styles.cardTopRow}>
                  <div style={styles.filename}>{job.original_filename}</div>
                  <div style={getJobBadgeStyle(job.status)}>{formatJobStatus(job.status)}</div>
                </div>

                <div style={styles.metaRow}>
                  {formatHistoryTimestamp(job.created_at)} · {formatView(job)}
                </div>

                <div style={styles.summaryText}>{getJobSummary(job)}</div>
              </button>
            );
          })}
        </div>
      </main>
    </div>
  );
}

function getThumbnailPath(job: SquatJobResponse) {
  const analysis = job.result?.squat_analysis;
  return (
    analysis?.frames?.rep_frames?.[0]?.image_path ??
    analysis?.frames?.knee_frame?.image_path ??
    null
  );
}

function getJobSummary(job: SquatJobResponse) {
  if (job.status === "failed") {
    return job.error_message ?? "This analysis failed before completing.";
  }

  if (job.status === "queued") {
    return "Uploaded and waiting for the worker to begin processing.";
  }

  if (job.status === "running") {
    return "Worker is extracting frames, running pose detection, and building feedback.";
  }

  const analysis = job.result?.squat_analysis;
  if (!analysis) {
    return "Completed without a stored summary.";
  }

  return analysis.feedback?.summary?.message ?? analysis.recommendation;
}

function formatView(job: SquatJobResponse) {
  switch (job.result?.squat_analysis.video_view) {
    case "side_view":
      return "Side view";
    case "front_view":
      return "Front view";
    default:
      return "View pending";
  }
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

function formatHistoryTimestamp(timestamp: string) {
  const date = new Date(timestamp);

  if (Number.isNaN(date.getTime())) {
    return "Unknown time";
  }

  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function getJobBadgeStyle(status: string): React.CSSProperties {
  switch (status) {
    case "queued":
      return {
        ...styles.badge,
        backgroundColor: "#fff7ed",
        color: "#c2410c",
      };
    case "running":
      return {
        ...styles.badge,
        backgroundColor: "#eff6ff",
        color: "#1d4ed8",
      };
    case "completed":
      return {
        ...styles.badge,
        backgroundColor: "#ecfdf5",
        color: "#047857",
      };
    case "failed":
      return {
        ...styles.badge,
        backgroundColor: "#fef2f2",
        color: "#b91c1c",
      };
    default:
      return styles.badge;
  }
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
  },
  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: "16px",
    marginBottom: "24px",
  },
  pageTitle: {
    margin: 0,
    fontSize: "28px",
    fontWeight: 700,
    color: THEME.colors.ink,
  },
  pageSubtitle: {
    margin: "8px 0 0 0",
    color: "#64748b",
  },
  refreshButton: {
    display: "inline-flex",
    alignItems: "center",
    gap: "8px",
    padding: "10px 14px",
    borderRadius: "12px",
    border: "1px solid #cbd5e1",
    backgroundColor: "rgba(255,255,255,0.82)",
    color: THEME.colors.primaryDeep,
    fontWeight: 600,
    cursor: "pointer",
  },
  headerActions: {
    display: "flex",
    gap: "12px",
  },
  secondaryButton: {
    display: "inline-flex",
    alignItems: "center",
    gap: "8px",
    padding: "10px 14px",
    borderRadius: "12px",
    border: "1px solid #cbd5e1",
    backgroundColor: "rgba(255,255,255,0.82)",
    color: THEME.colors.primaryDeep,
    fontWeight: 600,
    cursor: "pointer",
  },
  errorBox: {
    marginBottom: "18px",
    backgroundColor: "#fef2f2",
    color: "#b91c1c",
    border: "1px solid #fecaca",
    borderRadius: "14px",
    padding: "14px 16px",
  },
  emptyState: {
    display: "flex",
    alignItems: "flex-start",
    gap: "12px",
    backgroundColor: "rgba(255,255,255,0.86)",
    border: "1px solid #e2e8f0",
    borderRadius: "24px",
    padding: "32px",
    marginBottom: "20px",
  },
  emptyTitle: {
    fontSize: "18px",
    fontWeight: 700,
    marginBottom: "8px",
  },
  emptyText: {
    color: "#64748b",
  },
  emptyIcon: {
    width: "40px",
    height: "40px",
    borderRadius: THEME.radii.md,
    backgroundColor: THEME.colors.energyMuted,
    color: THEME.colors.accentDeep,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
  },
  grid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
    gap: "20px",
  },
  analysisCard: {
    border: "1px solid #e2e8f0",
    backgroundColor: "rgba(255,255,255,0.88)",
    borderRadius: "22px",
    padding: "14px",
    cursor: "pointer",
    textAlign: "left",
    boxShadow: THEME.shadows.card,
  },
  analysisCardActive: {
    border: "1px solid #93c5fd",
    background: THEME.gradients.card,
    borderRadius: "22px",
    padding: "14px",
    cursor: "pointer",
    textAlign: "left",
    boxShadow: THEME.shadows.cardHover,
  },
  thumbnailFrame: {
    width: "100%",
    aspectRatio: "16 / 10",
    borderRadius: "18px",
    backgroundColor: "#e2e8f0",
    overflow: "hidden",
    marginBottom: "14px",
  },
  thumbnailImage: {
    width: "100%",
    height: "100%",
    objectFit: "cover",
    display: "block",
  },
  thumbnailPlaceholder: {
    width: "100%",
    height: "100%",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    color: "#475569",
    fontSize: "13px",
    fontWeight: 600,
    background:
      "linear-gradient(135deg, rgba(226,232,240,1) 0%, rgba(203,213,225,1) 100%)",
  },
  cardTopRow: {
    display: "flex",
    alignItems: "flex-start",
    justifyContent: "space-between",
    gap: "12px",
    marginBottom: "8px",
  },
  filename: {
    fontSize: "14px",
    fontWeight: 700,
    color: THEME.colors.primary,
    wordBreak: "break-word",
  },
  metaRow: {
    fontSize: "12px",
    color: "#64748b",
    marginBottom: "8px",
  },
  summaryText: {
    fontSize: "13px",
    color: "#334155",
    lineHeight: 1.5,
  },
  badge: {
    borderRadius: "999px",
    padding: "6px 10px",
    fontSize: "12px",
    fontWeight: 700,
    whiteSpace: "nowrap",
  },
};
