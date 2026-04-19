import React, { useEffect, useMemo, useState } from "react";
import { analyzeSquatVideo } from "../services/squatApi";
import type { SquatApiResponse, SquatAnalysis } from "../types/squat";

const API_BASE_URL = "http://localhost:8000";

export default function DashboardPage() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [result, setResult] = useState<SquatApiResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [selectedRepNumber, setSelectedRepNumber] = useState<number | null>(null);

  const analysis: SquatAnalysis | null = result?.squat_analysis ?? null;
  const supportsRepDetection = analysis?.supported_analysis?.includes("rep_detection") ?? false;
  const supportsDepth = analysis?.supported_analysis?.includes("depth") ?? false;
  const supportsTorsoLean = analysis?.supported_analysis?.includes("torso_lean") ?? false;
  const supportsKneeTracking = analysis?.supported_analysis?.includes("knee_tracking") ?? false;

  const getDisplayFrame = (
    repNumber: number,
    fallbackFrame: number
  ) => {
    const depth = analysis?.rep_depths?.find((d) => d.rep_number === repNumber);
    const torso = analysis?.rep_torso_lean?.find((t) => t.rep_number === repNumber);
    const frame = analysis?.frames?.rep_frames?.find(
      (item) => item.rep_number === repNumber
    );

    return (
      frame?.frame ??
      depth?.evaluated_frame ??
      torso?.evaluated_frame ??
      fallbackFrame
    );
  };

  const repRows = useMemo(() => {
    if (!analysis?.reps?.length) return [];

    return analysis.reps.map((rep) => {
      const depth = analysis.rep_depths?.find((d) => d.rep_number === rep.rep_number);
      const torso = analysis.rep_torso_lean?.find((t) => t.rep_number === rep.rep_number);

      return {
        rep: rep.rep_number,
        depth: formatDepth(depth?.depth_status),
        torso: formatTorso(torso?.torso_lean_status),
        status: getCoachStatus(depth?.depth_status),
        bottomFrame: getDisplayFrame(rep.rep_number, rep.bottom_frame),
      };
    });
  }, [analysis]);

  const primaryIssue =
    analysis?.corrective_recommendations?.[0]?.issue ?? "No major issue detected";

  const secondaryIssue =
    analysis?.corrective_recommendations?.[1]?.issue ?? "No secondary issue";

  const selectedRepSnapshot = useMemo(() => {
    if (!supportsRepDetection) return null;
    if (!analysis?.frames?.rep_frames?.length) return null;
    if (selectedRepNumber == null) return null;

    return (
      analysis.frames.rep_frames.find(
        (frame) => frame.rep_number === selectedRepNumber
      ) ?? null
    );
  }, [analysis, selectedRepNumber, supportsRepDetection]);

  const selectedRepData = useMemo(() => {
    if (!supportsRepDetection) return null;
    if (selectedRepNumber == null) return null;
    if (!analysis) return null;

    const rep = analysis.reps?.find((r) => r.rep_number === selectedRepNumber);
    const depth = analysis.rep_depths?.find((d) => d.rep_number === selectedRepNumber);
    const torso = analysis.rep_torso_lean?.find((t) => t.rep_number === selectedRepNumber);

    if (!rep) return null;

    return { rep, depth, torso };
  }, [analysis, selectedRepNumber, supportsRepDetection]);

  const highlightedFrontSnapshot =
    supportsKneeTracking ? analysis?.frames?.knee_frame ?? null : null;

  useEffect(() => {
    if (!supportsRepDetection) {
      setSelectedRepNumber(null);
      return;
    }
    if (!analysis) {
      setSelectedRepNumber(null);
      return;
    }

    const reps = analysis.reps ?? [];
    if (!reps.length) {
      setSelectedRepNumber(null);
      return;
    }

    const aboveParallelRep = analysis.rep_depths?.find(
      (item) => item.depth_status === "above_parallel"
    );

    if (aboveParallelRep) {
      setSelectedRepNumber(aboveParallelRep.rep_number);
      return;
    }

    const belowParallelRep = analysis.rep_depths?.find(
      (item) => item.depth_status === "below_parallel"
    );

    if (belowParallelRep) {
      setSelectedRepNumber(belowParallelRep.rep_number);
      return;
    }

    setSelectedRepNumber(reps[reps.length - 1].rep_number);
  }, [analysis, supportsRepDetection]);

  async function handleAnalyze() {
    if (!selectedFile) {
      setError("Please choose a video file first.");
      return;
    }

    try {
      setIsLoading(true);
      setError("");
      const data = await analyzeSquatVideo(selectedFile);
      setResult(data);
      setSelectedRepNumber(null);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to analyze squat video.";
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div style={styles.page}>
      <aside style={styles.sidebar}>
        <div style={styles.brandRow}>
          <div style={styles.brandIcon}>V</div>
          <div>
            <div style={styles.brandTitle}>Vectra</div>
            <div style={styles.brandSubtitle}>Trainer Workspace</div>
          </div>
        </div>

        <div style={styles.uploadCard}>
          <div style={styles.uploadTitle}>New review</div>
          <div style={styles.uploadText}>
            Upload athlete squat video and get instant analysis.
          </div>

          <input
            type="file"
            accept="video/*"
            onChange={(e) => {
              const file = e.target.files?.[0] ?? null;
              setSelectedFile(file);
            }}
            style={styles.fileInput}
          />

          <button
            style={styles.primaryLightButton}
            onClick={handleAnalyze}
            disabled={isLoading}
          >
            {isLoading ? "Analyzing..." : "Analyze video"}
          </button>
        </div>

        <div style={styles.navSection}>
          <div style={styles.navItemActive}>Dashboard</div>
          <div style={styles.navItem}>Clients</div>
          <div style={styles.navItem}>Sessions</div>
          <div style={styles.navItem}>Insights</div>
          <div style={styles.navItem}>Settings</div>
        </div>
      </aside>

      <main style={styles.main}>
        <div style={styles.header}>
          <div>
            <h1 style={styles.pageTitle}>Squat review</h1>
            <p style={styles.pageSubtitle}>
              Fast coach workflow: upload, inspect key rep, send cues.
            </p>
          </div>

          <div style={styles.headerButtons}>
            <button style={styles.secondaryButton}>Request front view</button>
            <button style={styles.primaryButton}>Share feedback</button>
          </div>
        </div>

        {error ? <div style={styles.errorBox}>{error}</div> : null}

        {!result ? (
          <div style={styles.emptyState}>
            <div style={styles.emptyTitle}>No analysis loaded yet</div>
            <div style={styles.emptyText}>
              Choose a squat video and click <strong>Analyze video</strong>.
            </div>
          </div>
        ) : (
          <div style={styles.contentGrid}>
            <section style={styles.leftColumn}>
              <div style={styles.panel}>
                <div style={styles.panelHeader}>
                  <div>
                    <div style={styles.panelTitle}>
                      {analysis?.feedback?.summary?.title ?? "Squat analysis"}
                    </div>
                    <div style={styles.panelMeta}>
                      {result.filename} · {formatView(analysis?.video_view)}
                    </div>
                  </div>
                  <div style={styles.badgeRow}>
                    <div style={styles.confidenceBadge}>
                      {formatSuitability(analysis?.view_suitability)} capture
                    </div>
                    <div style={styles.confidenceBadge}>
                      {analysis?.confidence ?? "unknown"} confidence
                    </div>
                  </div>
                </div>

                <div style={styles.heroSection}>
                  <div style={styles.videoMock}>
                    <div style={styles.videoTopRow}>
                      {supportsRepDetection ? (
                        <>
                          <span>
                            {selectedRepData
                              ? `Rep ${selectedRepData.rep.rep_number} · Bottom frame`
                              : "Bottom frame highlight"}
                          </span>
                          <span>
                            {selectedRepData
                              ? `Frame ${getDisplayFrame(
                                  selectedRepData.rep.rep_number,
                                  selectedRepData.rep.bottom_frame
                                )}`
                              : `Rep count ${analysis?.rep_count ?? 0}`}
                          </span>
                        </>
                      ) : supportsKneeTracking ? (
                        <>
                          <span>Knee tracking highlight</span>
                          <span>
                            Frame {analysis?.knee_tracking?.evaluated_frame ?? "-"}
                          </span>
                        </>
                      ) : (
                        <>
                          <span>Capture review</span>
                          <span>Rule-based analysis limited</span>
                        </>
                      )}
                    </div>

                    {supportsRepDetection && selectedRepSnapshot ? (
                      <img
                        src={`${API_BASE_URL}${selectedRepSnapshot.image_path}`}
                        alt={`Rep ${selectedRepSnapshot.rep_number} bottom frame`}
                        style={styles.frameImage}
                      />
                    ) : null}

                    {supportsKneeTracking && highlightedFrontSnapshot ? (
                      <img
                        src={`${API_BASE_URL}${highlightedFrontSnapshot.image_path}`}
                        alt="Front view frame"
                        style={styles.frameImage}
                      />
                    ) : null}

                    {!selectedRepSnapshot && !highlightedFrontSnapshot ? (
                      <div style={styles.videoPlaceholder}>No frame available</div>
                    ) : null}

                    <div style={styles.videoCaption}>
                      {supportsRepDetection && selectedRepData ? (
                        <>
                          <div style={styles.captionLine}>
                            <strong>Depth:</strong>{" "}
                            {supportsDepth
                              ? formatDepth(selectedRepData.depth?.depth_status)
                              : "Skipped for this angle"}
                          </div>
                          <div style={styles.captionLine}>
                            <strong>Torso:</strong>{" "}
                            {supportsTorsoLean
                              ? formatTorso(selectedRepData.torso?.torso_lean_status)
                              : "Skipped for this angle"}
                          </div>
                          <div style={styles.captionLine}>
                            <strong>Frame:</strong>{" "}
                            {getDisplayFrame(
                              selectedRepData.rep.rep_number,
                              selectedRepData.rep.bottom_frame
                            )}
                          </div>
                        </>
                      ) : (
                        analysis?.feedback?.summary?.message ?? analysis?.message
                      )}
                    </div>
                  </div>

                  <div style={styles.summaryColumn}>
                    <div style={styles.metricCard}>
                      <div style={styles.metricLabel}>Detected view</div>
                      <div style={styles.metricText}>
                        {formatView(analysis?.video_view)}
                      </div>
                    </div>

                    <div style={styles.metricCard}>
                      <div style={styles.metricLabel}>Capture quality</div>
                      <div style={styles.metricText}>
                        {formatSuitability(analysis?.view_suitability)}
                      </div>
                    </div>

                    <div style={styles.metricCard}>
                      <div style={styles.metricLabel}>Primary issue</div>
                      <div style={styles.metricText}>{primaryIssue}</div>
                    </div>

                    {supportsRepDetection ? (
                      <div style={styles.metricCard}>
                        <div style={styles.metricLabel}>Rep count</div>
                        <div style={styles.metricValue}>{analysis?.rep_count ?? 0}</div>
                      </div>
                    ) : supportsKneeTracking ? (
                      <div style={styles.metricCard}>
                        <div style={styles.metricLabel}>Knee tracking</div>
                        <div style={styles.metricText}>
                          {formatKneeTracking(analysis?.knee_tracking?.status)}
                        </div>
                      </div>
                    ) : (
                      <div style={styles.metricCard}>
                        <div style={styles.metricLabel}>Secondary issue</div>
                        <div style={styles.metricText}>{secondaryIssue}</div>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {supportsRepDetection && repRows.length > 0 ? (
                <div style={styles.panel}>
                  <div style={styles.panelHeader}>
                    <div style={styles.panelTitle}>Per-rep breakdown</div>
                    <div style={styles.tableTag}>Click “View frame” to inspect a rep</div>
                  </div>

                  <div style={styles.tableWrapper}>
                    <table style={styles.table}>
                      <thead>
                        <tr>
                          <th style={styles.th}>Rep</th>
                          <th style={styles.th}>Depth</th>
                          <th style={styles.th}>Torso</th>
                          <th style={styles.th}>Coach status</th>
                          <th style={styles.th}>Bottom frame</th>
                          <th style={styles.th}>Action</th>
                        </tr>
                      </thead>
                      <tbody>
                        {repRows.map((row) => {
                          const isSelected = row.rep === selectedRepNumber;

                          return (
                            <tr
                              key={row.rep}
                              style={isSelected ? styles.selectedRow : undefined}
                            >
                              <td style={styles.tdStrong}>Rep {row.rep}</td>
                              <td style={styles.td}>{row.depth}</td>
                              <td style={styles.td}>{row.torso}</td>
                              <td style={styles.td}>
                                <span style={styles.statusPill}>{row.status}</span>
                              </td>
                              <td style={styles.td}>{row.bottomFrame}</td>
                              <td style={styles.td}>
                                <button
                                  style={
                                    isSelected
                                      ? styles.smallButtonActive
                                      : styles.smallButton
                                  }
                                  onClick={() => setSelectedRepNumber(row.rep)}
                                >
                                  {isSelected ? "Viewing" : "View frame"}
                                </button>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              ) : null}
            </section>

            <section style={styles.rightColumn}>
              <div style={styles.panel}>
                <div style={styles.panelTitle}>Corrective plan</div>

                {analysis?.corrective_recommendations?.length ? (
                  analysis.corrective_recommendations.map((item, index) => (
                    <div key={index} style={styles.infoCard}>
                      <div style={styles.infoTitle}>{item.issue}</div>
                      <div style={styles.infoText}>
                        <strong>Likely cause:</strong> {item.likely_cause}
                      </div>
                      <div style={styles.infoText}>
                        <strong>Coaching cue:</strong> {item.coaching_cue}
                      </div>
                      <div style={styles.infoText}>
                        <strong>Corrective exercise:</strong> {item.corrective_exercise}
                      </div>
                    </div>
                  ))
                ) : (
                  <div style={styles.infoCard}>No corrective recommendations available yet.</div>
                )}
              </div>

              <div style={styles.panel}>
                <div style={styles.panelTitle}>Recommendations</div>

                {analysis?.feedback?.recommendations?.length ? (
                  analysis.feedback.recommendations.map((item, index) => (
                    <div key={index} style={styles.infoCard}>
                      {item}
                    </div>
                  ))
                ) : (
                  <div style={styles.infoCard}>{analysis?.recommendation}</div>
                )}
              </div>

              <div style={styles.panel}>
                <div style={styles.panelHeader}>
                  <div style={styles.panelTitle}>Send to athlete</div>
                  <div style={styles.draftTag}>Draft mode</div>
                </div>

                <textarea
                  style={styles.textarea}
                  defaultValue={analysis?.feedback?.summary?.message ?? ""}
                />

                <div style={styles.sendButtons}>
                  <button style={styles.secondaryButton}>Save draft</button>
                  <button style={styles.primaryButton}>Copy feedback</button>
                </div>
              </div>
            </section>
          </div>
        )}
      </main>
    </div>
  );
}

function formatView(view?: string) {
  switch (view) {
    case "side_view":
      return "Side view";
    case "front_view":
      return "Front view";
    default:
      return "Unknown";
  }
}

function formatSuitability(suitability?: string) {
  switch (suitability) {
    case "good":
      return "Good";
    case "moderate":
      return "Moderate";
    case "not_sufficient":
      return "Not sufficient";
    default:
      return "Unknown";
  }
}

function formatDepth(status?: string) {
  switch (status) {
    case "below_parallel":
      return "Below parallel";
    case "at_parallel":
      return "At parallel";
    case "above_parallel":
      return "Above parallel";
    default:
      return "Unknown";
  }
}

function formatTorso(status?: string) {
  switch (status) {
    case "upright":
      return "Upright";
    case "moderate_lean":
      return "Moderate lean";
    case "excessive_lean":
      return "Excessive lean";
    default:
      return "Unknown";
  }
}

function formatKneeTracking(status?: string) {
  switch (status) {
    case "tracking_well":
      return "Tracking well";
    case "mild_knee_cave":
      return "Mild inward tracking";
    case "moderate_knee_cave":
      return "Moderate inward tracking";
    case "severe_knee_cave":
      return "Significant inward tracking";
    default:
      return "Unknown";
  }
}

function getCoachStatus(depthStatus?: string) {
  switch (depthStatus) {
    case "below_parallel":
      return "Best rep";
    case "at_parallel":
      return "Solid";
    case "above_parallel":
      return "Needs depth";
    default:
      return "Review";
  }
}

const styles: Record<string, React.CSSProperties> = {
  page: {
    minHeight: "100vh",
    display: "flex",
    backgroundColor: "#f1f5f9",
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
    backgroundColor: "#0f172a",
    color: "#ffffff",
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
  uploadCard: {
    marginTop: "24px",
    backgroundColor: "#0f172a",
    color: "#ffffff",
    borderRadius: "18px",
    padding: "16px",
  },
  uploadTitle: {
    fontSize: "14px",
    fontWeight: 600,
  },
  uploadText: {
    fontSize: "12px",
    color: "#cbd5e1",
    marginTop: "6px",
    marginBottom: "14px",
    lineHeight: 1.5,
  },
  fileInput: {
    width: "100%",
    marginBottom: "12px",
    color: "#ffffff",
  },
  primaryLightButton: {
    width: "100%",
    padding: "10px 12px",
    borderRadius: "12px",
    border: "none",
    backgroundColor: "#ffffff",
    color: "#0f172a",
    fontWeight: 600,
    cursor: "pointer",
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
  },
  navItem: {
    padding: "10px 12px",
    borderRadius: "12px",
    color: "#64748b",
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
  },
  pageSubtitle: {
    margin: "8px 0 0 0",
    color: "#64748b",
  },
  headerButtons: {
    display: "flex",
    gap: "12px",
  },
  primaryButton: {
    padding: "10px 14px",
    borderRadius: "12px",
    border: "none",
    backgroundColor: "#0f172a",
    color: "#ffffff",
    fontWeight: 600,
    cursor: "pointer",
  },
  secondaryButton: {
    padding: "10px 14px",
    borderRadius: "12px",
    border: "1px solid #cbd5e1",
    backgroundColor: "#ffffff",
    color: "#0f172a",
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
    backgroundColor: "#ffffff",
    border: "1px solid #e2e8f0",
    borderRadius: "24px",
    padding: "32px",
  },
  emptyTitle: {
    fontSize: "18px",
    fontWeight: 700,
    marginBottom: "8px",
  },
  emptyText: {
    color: "#64748b",
  },
  contentGrid: {
    display: "grid",
    gridTemplateColumns: "2fr 1fr",
    gap: "24px",
  },
  leftColumn: {
    display: "flex",
    flexDirection: "column",
    gap: "24px",
  },
  rightColumn: {
    display: "flex",
    flexDirection: "column",
    gap: "24px",
  },
  panel: {
    backgroundColor: "#ffffff",
    border: "1px solid #e2e8f0",
    borderRadius: "24px",
    padding: "20px",
    boxShadow: "0 4px 16px rgba(0,0,0,0.04)",
  },
  panelHeader: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: "12px",
    marginBottom: "16px",
  },
  panelTitle: {
    fontSize: "16px",
    fontWeight: 700,
  },
  panelMeta: {
    fontSize: "13px",
    color: "#64748b",
    marginTop: "4px",
  },
  badgeRow: {
    display: "flex",
    gap: "8px",
    flexWrap: "wrap",
    justifyContent: "flex-end",
  },
  confidenceBadge: {
    fontSize: "12px",
    color: "#047857",
    backgroundColor: "#ecfdf5",
    borderRadius: "999px",
    padding: "6px 10px",
    fontWeight: 600,
  },
  heroSection: {
    display: "grid",
    gridTemplateColumns: "1.7fr 1fr",
    gap: "18px",
  },
  videoMock: {
    backgroundColor: "#020617",
    color: "#ffffff",
    borderRadius: "18px",
    padding: "16px",
    minHeight: "360px",
    display: "flex",
    flexDirection: "column",
    justifyContent: "space-between",
  },
  videoTopRow: {
    display: "flex",
    justifyContent: "space-between",
    fontSize: "12px",
    color: "#cbd5e1",
  },
  frameImage: {
    width: "100%",
    maxHeight: "260px",
    objectFit: "contain",
    borderRadius: "14px",
    marginTop: "16px",
    marginBottom: "16px",
    backgroundColor: "#111827",
  },
  videoPlaceholder: {
    marginTop: "16px",
    marginBottom: "16px",
    minHeight: "220px",
    borderRadius: "14px",
    backgroundColor: "rgba(255,255,255,0.06)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    color: "#cbd5e1",
    fontSize: "14px",
  },
  videoCaption: {
    fontSize: "12px",
    color: "#cbd5e1",
    backgroundColor: "rgba(255,255,255,0.06)",
    padding: "10px 12px",
    borderRadius: "14px",
    lineHeight: 1.5,
  },
  captionLine: {
    marginBottom: "4px",
  },
  summaryColumn: {
    display: "flex",
    flexDirection: "column",
    gap: "12px",
  },
  metricCard: {
    backgroundColor: "#f8fafc",
    border: "1px solid #e2e8f0",
    borderRadius: "16px",
    padding: "16px",
  },
  metricLabel: {
    fontSize: "12px",
    color: "#64748b",
    textTransform: "uppercase",
    letterSpacing: "0.05em",
    marginBottom: "8px",
  },
  metricValue: {
    fontSize: "32px",
    fontWeight: 700,
  },
  metricText: {
    fontSize: "14px",
    fontWeight: 600,
  },
  tableTag: {
    fontSize: "12px",
    color: "#475569",
    backgroundColor: "#f8fafc",
    borderRadius: "999px",
    padding: "6px 10px",
  },
  tableWrapper: {
    overflowX: "auto",
  },
  table: {
    width: "100%",
    borderCollapse: "collapse",
  },
  th: {
    textAlign: "left",
    fontSize: "13px",
    color: "#64748b",
    fontWeight: 600,
    padding: "12px 8px",
    borderBottom: "1px solid #e2e8f0",
  },
  td: {
    padding: "14px 8px",
    borderBottom: "1px solid #f1f5f9",
    fontSize: "14px",
    color: "#334155",
  },
  tdStrong: {
    padding: "14px 8px",
    borderBottom: "1px solid #f1f5f9",
    fontSize: "14px",
    fontWeight: 600,
  },
  statusPill: {
    fontSize: "12px",
    color: "#334155",
    backgroundColor: "#f8fafc",
    borderRadius: "999px",
    padding: "6px 10px",
  },
  selectedRow: {
    backgroundColor: "#f8fafc",
  },
  smallButton: {
    padding: "8px 10px",
    borderRadius: "10px",
    border: "1px solid #cbd5e1",
    backgroundColor: "#ffffff",
    cursor: "pointer",
  },
  smallButtonActive: {
    padding: "8px 10px",
    borderRadius: "10px",
    border: "1px solid #0f172a",
    backgroundColor: "#0f172a",
    color: "#ffffff",
    cursor: "pointer",
  },
  infoCard: {
    backgroundColor: "#f8fafc",
    borderRadius: "16px",
    padding: "14px",
    marginTop: "12px",
    color: "#475569",
    lineHeight: 1.6,
  },
  infoTitle: {
    fontSize: "14px",
    fontWeight: 700,
    marginBottom: "6px",
    color: "#0f172a",
  },
  infoText: {
    fontSize: "14px",
    marginTop: "4px",
  },
  draftTag: {
    fontSize: "12px",
    color: "#b45309",
    backgroundColor: "#fffbeb",
    borderRadius: "999px",
    padding: "6px 10px",
    fontWeight: 600,
  },
  textarea: {
    width: "100%",
    minHeight: "160px",
    marginTop: "16px",
    borderRadius: "16px",
    border: "1px solid #e2e8f0",
    padding: "14px",
    boxSizing: "border-box",
    fontSize: "14px",
    resize: "vertical",
  },
  sendButtons: {
    display: "flex",
    gap: "12px",
    marginTop: "14px",
  },
};
