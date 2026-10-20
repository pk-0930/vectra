import { Skeleton } from '../design-system/components'
import ProtectedImage from '../components/ProtectedImage'
import React, { useEffect, useState } from "react";
import { ClipboardList, RefreshCw } from "lucide-react";
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
    <div>

      <main className="page-content">
        <div className="flow-header" style={styles.header}>
        <div>
          <h1 style={styles.pageTitle}>Recent Analysis</h1>
          <p style={styles.pageSubtitle}>
            Past squat analyses with annotated snapshots ready for quick reopen.
          </p>
        </div>

        <div className="header-actions">
          <button style={styles.refreshButton} onClick={loadJobs} disabled={isLoading}>
            <RefreshCw size={16} />
            {isLoading ? "Refreshing..." : "Refresh list"}
          </button>
        </div>
      </div>

        {error ? <div role="alert" style={styles.errorBox}>{error}</div> : null}

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

        {isLoading && <Skeleton label="Loading analysis history…" />}
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
                    <ProtectedImage
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
        backgroundColor: THEME.colors.warningSurface,
        color: THEME.colors.warning,
      };
    case "running":
      return {
        ...styles.badge,
        backgroundColor: THEME.colors.infoSurface,
        color: THEME.colors.info,
      };
    case "completed":
      return {
        ...styles.badge,
        backgroundColor: THEME.colors.successSurface,
        color: THEME.colors.success,
      };
    case "failed":
      return {
        ...styles.badge,
        backgroundColor: THEME.colors.dangerSurface,
        color: THEME.colors.danger,
      };
    default:
      return styles.badge;
  }
}

const styles: Record<string, React.CSSProperties> = {
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
    color: THEME.colors.textMuted,
  },
  refreshButton: {
    display: "inline-flex",
    alignItems: "center",
    gap: "8px",
    padding: "10px 14px",
    borderRadius: "12px",
    border: `1px solid ${THEME.colors.borderStrong}`,
    backgroundColor: THEME.colors.surface,
    color: THEME.colors.primaryDeep,
    fontWeight: 600,
    cursor: "pointer",
  },
  errorBox: {
    marginBottom: "18px",
    backgroundColor: THEME.colors.dangerSurface,
    color: THEME.colors.danger,
    border: `1px solid ${THEME.colors.danger}`,
    borderRadius: "14px",
    padding: "14px 16px",
  },
  emptyState: {
    display: "flex",
    alignItems: "flex-start",
    gap: "12px",
    backgroundColor: THEME.colors.surface,
    border: `1px solid ${THEME.colors.border}`,
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
    color: THEME.colors.textMuted,
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
    gridTemplateColumns: "repeat(auto-fill, minmax(min(100%, 280px), 1fr))",
    gap: "20px",
  },
  analysisCard: {
    border: `1px solid ${THEME.colors.border}`,
    backgroundColor: THEME.colors.surface,
    borderRadius: "22px",
    padding: "14px",
    cursor: "pointer",
    textAlign: "left",
    boxShadow: THEME.shadows.card,
  },
  analysisCardActive: {
    border: `1px solid ${THEME.colors.borderStrong}`,
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
    backgroundColor: THEME.colors.border,
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
    color: THEME.colors.textSoft,
    fontSize: "13px",
    fontWeight: 600,
    background:
      THEME.colors.surfaceMuted,
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
    color: THEME.colors.primaryDeep,
    wordBreak: "break-word",
  },
  metaRow: {
    fontSize: "12px",
    color: THEME.colors.textMuted,
    marginBottom: "8px",
  },
  summaryText: {
    fontSize: "13px",
    color: THEME.colors.text,
    lineHeight: 1.5,
  },
  badge: {
    borderRadius: "999px",
    padding: "6px 10px",
    fontSize: "12px",
    fontWeight: 700,
    overflowWrap: "anywhere",
  },
};
