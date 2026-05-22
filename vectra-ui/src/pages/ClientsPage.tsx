import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity,
  Apple,
  Camera,
  ClipboardList,
  Dumbbell,
  FileText,
  ImagePlus,
  Plus,
  RefreshCw,
  Save,
  Sparkles,
  Target,
  UserRound,
  Video,
  X,
  type LucideIcon,
} from "lucide-react";
import SideNav from "../components/SideNav";
import { API_BASE_URL } from "../services/apiConfig";
import {
  addClientGoal,
  createClient,
  fetchClient,
  getClientProgressPhotoUrl,
  listClientProgressPhotos,
  listClients,
  updateClient,
  uploadClientProgressPhoto,
} from "../services/clientApi";
import {
  approvePlanDraft,
  createPlanDraft,
  createNutritionPlan,
  createWorkoutPlan,
  discardPlanDraft,
  getNutritionPlanPdfUrl,
  getWorkoutPlanPdfUrl,
  listPlanDrafts,
  listNutritionPlans,
  listWorkoutPlans,
  updatePlanDraft,
} from "../services/planApi";
import {
  createSquatJob,
  fetchSquatJob,
  getFormAnalysisPdfUrl,
  listClientSquatJobs,
  saveAnalysisFeedback,
} from "../services/squatApi";
import { getStoredAccessToken } from "../services/session";
import { PRIMARY_BORDER, THEME } from "../theme";
import type { Client, ProgressPhoto } from "../types/client";
import type { AppTab } from "../types/navigation";
import type { DietaryPreference, Plan, PlanDraft, PlanKind, PlanPayload, PlanPeriodType } from "../types/plan";
import type { SquatAnalysis, SquatApiResponse, SquatJobResponse } from "../types/squat";

type ClientsPageProps = {
  activeTab: AppTab;
  onTabChange: (tab: AppTab) => void;
  onLogout: () => void;
  selectedClientId: number | null;
  requestedAnalysis?: SquatJobResponse | null;
  onSelectClient: (client: Client) => void;
  onAnalysisLoaded?: (job: SquatJobResponse) => void;
};

type DetailTab = "profile" | "nutrition" | "workout" | "form-analysis";
type DrawerName =
  | "create-client"
  | "edit-profile"
  | "update-goal"
  | "add-progress-photo"
  | "create-nutrition-plan"
  | "create-workout-plan"
  | "ai-nutrition-draft"
  | "ai-workout-draft"
  | null;

type PlanDraftState = {
  title: string;
  period_type: PlanPeriodType;
  period_start: string;
  period_end: string;
  summary: string;
  focus: string;
  meals: string;
  workout_days: string;
  mobility_drills: string;
  stretching_plan: string;
  notes: string;
};

type AiDraftFormState = {
  period_type: PlanPeriodType;
  period_start: string;
  period_end: string;
  dietary_preference: DietaryPreference;
  coach_prompt: string;
};

const initialPlanDraft = (): PlanDraftState => ({
  title: "",
  period_type: "weekly",
  period_start: "",
  period_end: "",
  summary: "",
  focus: "",
  meals: "",
  workout_days: "",
  mobility_drills: "",
  stretching_plan: "",
  notes: "",
});

const initialAiDraftForm = (): AiDraftFormState => ({
  period_type: "weekly",
  period_start: "",
  period_end: "",
  dietary_preference: "no_preference",
  coach_prompt: "",
});

export default function ClientsPage({
  activeTab,
  onTabChange,
  onLogout,
  selectedClientId,
  requestedAnalysis,
  onSelectClient,
  onAnalysisLoaded,
}: ClientsPageProps) {
  const [detailTab, setDetailTab] = useState<DetailTab>("profile");
  const [drawer, setDrawer] = useState<DrawerName>(null);
  const [clients, setClients] = useState<Client[]>([]);
  const [selectedClient, setSelectedClient] = useState<Client | null>(null);
  const [nutritionPlans, setNutritionPlans] = useState<Plan[]>([]);
  const [workoutPlans, setWorkoutPlans] = useState<Plan[]>([]);
  const [nutritionAiDrafts, setNutritionAiDrafts] = useState<PlanDraft[]>([]);
  const [workoutAiDrafts, setWorkoutAiDrafts] = useState<PlanDraft[]>([]);
  const [analysisHistory, setAnalysisHistory] = useState<SquatJobResponse[]>([]);
  const [progressPhotos, setProgressPhotos] = useState<ProgressPhoto[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isDetailLoading, setIsDetailLoading] = useState(false);
  const [isHistoryLoading, setIsHistoryLoading] = useState(false);
  const [error, setError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [createClientForm, setCreateClientForm] = useState({ first_name: "", last_name: "" });
  const [profileForm, setProfileForm] = useState({
    first_name: "",
    last_name: "",
    dob: "",
    gender: "",
    height_cm: "",
    weight_kg: "",
    is_active: true,
  });
  const [goalForm, setGoalForm] = useState({
    goal_type: "weight_loss",
    notes: "",
    start_date: "",
    end_date: "",
  });
  const [nutritionDraft, setNutritionDraft] = useState<PlanDraftState>(initialPlanDraft);
  const [workoutDraft, setWorkoutDraft] = useState<PlanDraftState>(initialPlanDraft);
  const [nutritionAiDraftForm, setNutritionAiDraftForm] = useState<AiDraftFormState>(initialAiDraftForm);
  const [workoutAiDraftForm, setWorkoutAiDraftForm] = useState<AiDraftFormState>(initialAiDraftForm);
  const [nutritionAiDraftEdit, setNutritionAiDraftEdit] = useState<PlanDraftState>(initialPlanDraft);
  const [workoutAiDraftEdit, setWorkoutAiDraftEdit] = useState<PlanDraftState>(initialPlanDraft);
  const [progressPhotoFile, setProgressPhotoFile] = useState<File | null>(null);
  const [progressPhotoForm, setProgressPhotoForm] = useState({
    timeline_type: "weekly",
    captured_on: "",
    caption: "",
  });
  const [analysisFile, setAnalysisFile] = useState<File | null>(null);
  const [selectedAnalysisJob, setSelectedAnalysisJob] = useState<SquatJobResponse | null>(null);
  const [analysisResult, setAnalysisResult] = useState<SquatApiResponse | null>(null);
  const [feedbackNote, setFeedbackNote] = useState("");
  const [selectedRepNumber, setSelectedRepNumber] = useState<number | null>(null);
  const [isSavingProfile, setIsSavingProfile] = useState(false);
  const [isSavingGoal, setIsSavingGoal] = useState(false);
  const [isSavingNutrition, setIsSavingNutrition] = useState(false);
  const [isSavingWorkout, setIsSavingWorkout] = useState(false);
  const [isGeneratingAiDraft, setIsGeneratingAiDraft] = useState(false);
  const [isSavingAiDraft, setIsSavingAiDraft] = useState(false);
  const [isApprovingAiDraft, setIsApprovingAiDraft] = useState(false);
  const [isDiscardingAiDraft, setIsDiscardingAiDraft] = useState(false);
  const [isSavingProgressPhoto, setIsSavingProgressPhoto] = useState(false);
  const [isCreatingAnalysis, setIsCreatingAnalysis] = useState(false);
  const [isSavingFeedback, setIsSavingFeedback] = useState(false);
  const [handledRequestedAnalysisId, setHandledRequestedAnalysisId] = useState<string | null>(null);

  const analysis: SquatAnalysis | null = analysisResult?.squat_analysis ?? null;
  const isPollingJob = selectedAnalysisJob?.status === "queued" || selectedAnalysisJob?.status === "running";
  const supportsRepDetection = analysis?.supported_analysis?.includes("rep_detection") ?? false;
  const supportsDepth = analysis?.supported_analysis?.includes("depth") ?? false;
  const supportsTorsoLean = analysis?.supported_analysis?.includes("torso_lean") ?? false;
  const supportsKneeTracking = analysis?.supported_analysis?.includes("knee_tracking") ?? false;
  const activeNutritionAiDraft = useMemo(() => getActiveAiDraft(nutritionAiDrafts), [nutritionAiDrafts]);
  const activeWorkoutAiDraft = useMemo(() => getActiveAiDraft(workoutAiDrafts), [workoutAiDrafts]);

  const repRows = useMemo(() => {
    if (!analysis?.reps?.length) return [];
    return analysis.reps.map((rep) => {
      const depth = analysis.rep_depths?.find((item) => item.rep_number === rep.rep_number);
      const torso = analysis.rep_torso_lean?.find((item) => item.rep_number === rep.rep_number);
      return {
        rep: rep.rep_number,
        depth: formatDepth(depth?.depth_status),
        torso: formatTorso(torso?.torso_lean_status),
        status: getCoachStatus(depth?.depth_status),
        frame: getDisplayFrame(analysis, rep.rep_number, rep.bottom_frame),
      };
    });
  }, [analysis]);

  const selectedRepSnapshot = useMemo(() => {
    if (!supportsRepDetection || selectedRepNumber == null) return null;
    return analysis?.frames?.rep_frames?.find((frame) => frame.rep_number === selectedRepNumber) ?? null;
  }, [analysis, selectedRepNumber, supportsRepDetection]);

  const selectedRepData = useMemo(() => {
    if (!supportsRepDetection || selectedRepNumber == null || !analysis) return null;
    const rep = analysis.reps?.find((item) => item.rep_number === selectedRepNumber);
    const depth = analysis.rep_depths?.find((item) => item.rep_number === selectedRepNumber);
    const torso = analysis.rep_torso_lean?.find((item) => item.rep_number === selectedRepNumber);
    return rep ? { rep, depth, torso } : null;
  }, [analysis, selectedRepNumber, supportsRepDetection]);

  async function loadClients() {
    try {
      setIsLoading(true);
      setError("");
      setClients(await listClients());
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Failed to load clients.");
    } finally {
      setIsLoading(false);
    }
  }

  const loadClientWorkspace = useCallback(async (clientId: number) => {
    try {
      setIsDetailLoading(true);
      setError("");
      const [
        client,
        fetchedNutritionPlans,
        fetchedWorkoutPlans,
        fetchedNutritionDrafts,
        fetchedWorkoutDrafts,
        fetchedProgressPhotos,
        fetchedAnalyses,
      ] =
        await Promise.all([
          fetchClient(clientId),
          listNutritionPlans(clientId),
          listWorkoutPlans(clientId),
          listPlanDrafts(clientId, "nutrition"),
          listPlanDrafts(clientId, "workout"),
          listClientProgressPhotos(clientId),
          listClientSquatJobs(clientId, 24),
        ]);

      setSelectedClient(client);
      onSelectClient(client);
      setNutritionPlans(fetchedNutritionPlans);
      setWorkoutPlans(fetchedWorkoutPlans);
      setNutritionAiDrafts(fetchedNutritionDrafts);
      setWorkoutAiDrafts(fetchedWorkoutDrafts);
      setProgressPhotos(fetchedProgressPhotos);
      setAnalysisHistory(fetchedAnalyses.analyses);
      setProfileForm({
        first_name: client.first_name,
        last_name: client.last_name,
        dob: client.dob ?? "",
        gender: client.gender ?? "",
        height_cm: client.height_cm != null ? String(client.height_cm) : "",
        weight_kg: client.weight_kg != null ? String(client.weight_kg) : "",
        is_active: client.is_active,
      });
      setGoalForm((current) => ({
        ...current,
        goal_type: client.current_goal_type ?? current.goal_type,
        notes: client.current_goal_notes ?? "",
      }));
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Failed to load client workspace.");
    } finally {
      setIsDetailLoading(false);
    }
  }, [onSelectClient]);

  const loadAnalysisHistory = useCallback(async (clientId: number) => {
    try {
      setIsHistoryLoading(true);
      setError("");
      const response = await listClientSquatJobs(clientId, 24);
      setAnalysisHistory(response.analyses);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Failed to load client analysis history.");
    } finally {
      setIsHistoryLoading(false);
    }
  }, []);

  const openAnalysisJob = useCallback(async (job: SquatJobResponse) => {
    try {
      setError("");
      setDetailTab("form-analysis");
      setSelectedRepNumber(null);
      const freshJob = await fetchSquatJob(job.id);
      setSelectedAnalysisJob(freshJob);
      onAnalysisLoaded?.(freshJob);

      if (freshJob.status === "completed" && freshJob.result) {
        setAnalysisResult(freshJob.result);
        setFeedbackNote(freshJob.coach_feedback_note ?? "");
      } else {
        setAnalysisResult(null);
        setFeedbackNote(freshJob.coach_feedback_note ?? "");
        if (freshJob.status === "failed") {
          setError(freshJob.error_message ?? "Form analysis failed.");
        }
      }
    } catch (openError) {
      setError(openError instanceof Error ? openError.message : "Failed to open form analysis.");
    }
  }, [onAnalysisLoaded]);

  useEffect(() => {
    loadClients();
  }, []);

  useEffect(() => {
    if (!selectedClientId) {
      setSelectedClient(null);
      setNutritionPlans([]);
      setWorkoutPlans([]);
      setNutritionAiDrafts([]);
      setWorkoutAiDrafts([]);
      setProgressPhotos([]);
      setAnalysisHistory([]);
      setSelectedAnalysisJob(null);
      setAnalysisResult(null);
      return;
    }

    loadClientWorkspace(selectedClientId);
  }, [selectedClientId, loadClientWorkspace]);

  useEffect(() => {
    if (!requestedAnalysis?.id || handledRequestedAnalysisId === requestedAnalysis.id) return;
    setHandledRequestedAnalysisId(requestedAnalysis.id);
    openAnalysisJob(requestedAnalysis);
  }, [requestedAnalysis, handledRequestedAnalysisId, openAnalysisJob]);

  useEffect(() => {
    if (!selectedAnalysisJob?.id || !isPollingJob) return;
    let isCancelled = false;

    const pollJob = async () => {
      try {
        const nextJob = await fetchSquatJob(selectedAnalysisJob.id);
        if (isCancelled) return;
        setSelectedAnalysisJob(nextJob);
        onAnalysisLoaded?.(nextJob);

        if (nextJob.status === "completed" && nextJob.result) {
          setAnalysisResult(nextJob.result);
          setFeedbackNote(nextJob.coach_feedback_note ?? "");
          await loadAnalysisHistory(nextJob.client_id ?? selectedClientId ?? 0);
        }

        if (nextJob.status === "failed") {
          setAnalysisResult(null);
          setError(nextJob.error_message ?? "Form analysis failed.");
        }
      } catch (pollError) {
        if (!isCancelled) {
          setError(pollError instanceof Error ? pollError.message : "Failed to refresh form analysis.");
        }
      }
    };

    pollJob();
    const intervalId = window.setInterval(pollJob, 2000);
    return () => {
      isCancelled = true;
      window.clearInterval(intervalId);
    };
  }, [isPollingJob, selectedAnalysisJob?.id, loadAnalysisHistory, onAnalysisLoaded, selectedClientId]);

  useEffect(() => {
    if (!supportsRepDetection || !analysis?.reps?.length) {
      setSelectedRepNumber(null);
      return;
    }
    const aboveParallelRep = analysis.rep_depths?.find((item) => item.depth_status === "above_parallel");
    setSelectedRepNumber(aboveParallelRep?.rep_number ?? analysis.reps[0].rep_number);
  }, [analysis, supportsRepDetection]);

  async function handleCreateClient(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    try {
      setError("");
      const created = await createClient(createClientForm);
      setClients((current) => [created, ...current]);
      setCreateClientForm({ first_name: "", last_name: "" });
      setDrawer(null);
      setDetailTab("profile");
      onSelectClient(created);
      setSuccessMessage("Client created and selected.");
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : "Failed to create client.");
    }
  }

  async function handleUpdateProfile(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!selectedClient) return;
    try {
      setIsSavingProfile(true);
      setError("");
      const updated = await updateClient(selectedClient.id, {
        first_name: profileForm.first_name,
        last_name: profileForm.last_name,
        dob: profileForm.dob || undefined,
        gender: profileForm.gender || undefined,
        height_cm: profileForm.height_cm ? Number(profileForm.height_cm) : undefined,
        weight_kg: profileForm.weight_kg ? Number(profileForm.weight_kg) : undefined,
        is_active: profileForm.is_active,
      });
      setSelectedClient(updated);
      setClients((current) => current.map((client) => (client.id === updated.id ? updated : client)));
      onSelectClient(updated);
      setDrawer(null);
      setSuccessMessage("Client profile updated.");
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Failed to update client profile.");
    } finally {
      setIsSavingProfile(false);
    }
  }

  async function handleSaveGoal(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!selectedClient) return;
    try {
      setIsSavingGoal(true);
      setError("");
      await addClientGoal(selectedClient.id, {
        goal_type: goalForm.goal_type,
        notes: goalForm.notes || undefined,
        start_date: goalForm.start_date || undefined,
        end_date: goalForm.end_date || undefined,
      });
      await loadClientWorkspace(selectedClient.id);
      setDrawer(null);
      setSuccessMessage("Client goal saved.");
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Failed to save client goal.");
    } finally {
      setIsSavingGoal(false);
    }
  }

  async function handleCreateNutritionPlan(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!selectedClient) return;
    try {
      setIsSavingNutrition(true);
      setError("");
      const plan = await createNutritionPlan(selectedClient.id, buildPlanPayload(nutritionDraft));
      setNutritionPlans((current) => [plan, ...current]);
      setNutritionDraft(initialPlanDraft());
      setDrawer(null);
      setSuccessMessage("Nutrition plan created.");
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Failed to create nutrition plan.");
    } finally {
      setIsSavingNutrition(false);
    }
  }

  async function handleCreateWorkoutPlan(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!selectedClient) return;
    try {
      setIsSavingWorkout(true);
      setError("");
      const plan = await createWorkoutPlan(selectedClient.id, buildPlanPayload(workoutDraft));
      setWorkoutPlans((current) => [plan, ...current]);
      setWorkoutDraft(initialPlanDraft());
      setDrawer(null);
      setSuccessMessage("Workout plan created.");
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Failed to create workout plan.");
    } finally {
      setIsSavingWorkout(false);
    }
  }

  function openAiDraftDrawer(planKind: PlanKind) {
    const activeDraft = planKind === "nutrition" ? activeNutritionAiDraft : activeWorkoutAiDraft;
    if (activeDraft) {
      setAiDraftEdit(planKind, planDraftToEditState(activeDraft));
      setAiDraftForm(planKind, aiFormFromDraft(activeDraft));
    }
    setDrawer(planKind === "nutrition" ? "ai-nutrition-draft" : "ai-workout-draft");
  }

  async function handleGenerateAiDraft(planKind: PlanKind, e?: React.FormEvent<HTMLFormElement>) {
    e?.preventDefault();
    if (!selectedClient) return;
    const form = planKind === "nutrition" ? nutritionAiDraftForm : workoutAiDraftForm;
    try {
      setIsGeneratingAiDraft(true);
      setError("");
      const draft = await createPlanDraft(selectedClient.id, {
        plan_kind: planKind,
        period_type: form.period_type,
        period_start: form.period_start,
        period_end: form.period_end,
        dietary_preference: planKind === "nutrition" ? form.dietary_preference : undefined,
        coach_prompt: form.coach_prompt || undefined,
      });
      upsertAiDraft(planKind, draft);
      setAiDraftEdit(planKind, planDraftToEditState(draft));
      setSuccessMessage("AI draft generated. Review before approving.");
    } catch (draftError) {
      setError(draftError instanceof Error ? draftError.message : "Failed to generate AI draft.");
    } finally {
      setIsGeneratingAiDraft(false);
    }
  }

  async function handleSaveAiDraft(planKind: PlanKind) {
    const draft = planKind === "nutrition" ? activeNutritionAiDraft : activeWorkoutAiDraft;
    if (!draft) return null;
    const edit = planKind === "nutrition" ? nutritionAiDraftEdit : workoutAiDraftEdit;
    const form = planKind === "nutrition" ? nutritionAiDraftForm : workoutAiDraftForm;
    try {
      setIsSavingAiDraft(true);
      setError("");
      const saved = await updatePlanDraft(draft.id, {
        period_type: edit.period_type,
        period_start: edit.period_start,
        period_end: edit.period_end,
        title: edit.title,
        content: buildPlanPayload(edit).content,
        coach_prompt: form.coach_prompt || undefined,
      });
      upsertAiDraft(planKind, saved);
      setSuccessMessage("AI draft saved.");
      return saved;
    } catch (draftError) {
      setError(draftError instanceof Error ? draftError.message : "Failed to save AI draft.");
      return null;
    } finally {
      setIsSavingAiDraft(false);
    }
  }

  async function handleApproveAiDraft(planKind: PlanKind) {
    const draft = planKind === "nutrition" ? activeNutritionAiDraft : activeWorkoutAiDraft;
    if (!draft) return;
    try {
      setIsApprovingAiDraft(true);
      setError("");
      const savedDraft = await handleSaveAiDraft(planKind);
      if (!savedDraft) return;
      const approval = await approvePlanDraft(savedDraft.id);
      upsertAiDraft(planKind, approval.draft);
      if (planKind === "nutrition") {
        setNutritionPlans((current) => [approval.plan, ...current]);
      } else {
        setWorkoutPlans((current) => [approval.plan, ...current]);
      }
      setDrawer(null);
      setSuccessMessage("AI draft approved and saved as a final plan.");
    } catch (draftError) {
      setError(draftError instanceof Error ? draftError.message : "Failed to approve AI draft.");
    } finally {
      setIsApprovingAiDraft(false);
    }
  }

  async function handleDiscardAiDraft(planKind: PlanKind) {
    const draft = planKind === "nutrition" ? activeNutritionAiDraft : activeWorkoutAiDraft;
    if (!draft) return;
    try {
      setIsDiscardingAiDraft(true);
      setError("");
      const discarded = await discardPlanDraft(draft.id);
      upsertAiDraft(planKind, discarded);
      setAiDraftEdit(planKind, initialPlanDraft());
      setSuccessMessage("AI draft discarded.");
    } catch (draftError) {
      setError(draftError instanceof Error ? draftError.message : "Failed to discard AI draft.");
    } finally {
      setIsDiscardingAiDraft(false);
    }
  }

  function upsertAiDraft(planKind: PlanKind, draft: PlanDraft) {
    const setter = planKind === "nutrition" ? setNutritionAiDrafts : setWorkoutAiDrafts;
    setter((current) => [draft, ...current.filter((item) => item.id !== draft.id)]);
  }

  function setAiDraftEdit(planKind: PlanKind, edit: PlanDraftState) {
    if (planKind === "nutrition") {
      setNutritionAiDraftEdit(edit);
    } else {
      setWorkoutAiDraftEdit(edit);
    }
  }

  function setAiDraftForm(planKind: PlanKind, form: AiDraftFormState) {
    if (planKind === "nutrition") {
      setNutritionAiDraftForm(form);
    } else {
      setWorkoutAiDraftForm(form);
    }
  }

  async function handleUploadProgressPhoto(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!selectedClient) return;
    if (!progressPhotoFile) {
      setError("Choose a progress photo to upload.");
      return;
    }
    if (!progressPhotoForm.captured_on) {
      setError("Select the capture date for the progress photo.");
      return;
    }
    try {
      setIsSavingProgressPhoto(true);
      setError("");
      const uploaded = await uploadClientProgressPhoto(selectedClient.id, {
        file: progressPhotoFile,
        timeline_type: progressPhotoForm.timeline_type,
        captured_on: progressPhotoForm.captured_on,
        caption: progressPhotoForm.caption || undefined,
      });
      setProgressPhotos((current) => [uploaded, ...current]);
      setProgressPhotoFile(null);
      setProgressPhotoForm({ timeline_type: "weekly", captured_on: "", caption: "" });
      setDrawer(null);
      setSuccessMessage("Progress photo uploaded.");
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : "Failed to upload progress photo.");
    } finally {
      setIsSavingProgressPhoto(false);
    }
  }

  async function handleCreateAnalysis(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!selectedClient) return;
    if (!analysisFile) {
      setError("Choose a squat video before starting form analysis.");
      return;
    }
    try {
      setIsCreatingAnalysis(true);
      setError("");
      setAnalysisResult(null);
      const created = await createSquatJob(analysisFile, selectedClient.id);
      setSelectedAnalysisJob(created);
      setAnalysisHistory((current) => [created, ...current]);
      setAnalysisFile(null);
      onAnalysisLoaded?.(created);
      setSuccessMessage("Form analysis queued.");
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : "Failed to create form analysis.");
    } finally {
      setIsCreatingAnalysis(false);
    }
  }

  async function handleSaveFeedback() {
    if (!selectedAnalysisJob) {
      setError("Open an analysis before saving coach feedback.");
      return;
    }
    try {
      setIsSavingFeedback(true);
      setError("");
      const updated = await saveAnalysisFeedback(selectedAnalysisJob.id, feedbackNote);
      setSelectedAnalysisJob(updated);
      setAnalysisHistory((current) => current.map((job) => (job.id === updated.id ? updated : job)));
      onAnalysisLoaded?.(updated);
      setSuccessMessage("Coach feedback saved.");
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Failed to save coach feedback.");
    } finally {
      setIsSavingFeedback(false);
    }
  }

  return (
    <div style={styles.page}>
      <SideNav activeTab={activeTab} onTabChange={onTabChange} />

      <main style={styles.main}>
        <div style={styles.header}>
          <div>
            <h1 style={styles.pageTitle}>Clients</h1>
            <p style={styles.pageSubtitle}>
              Open a client-owned workspace for profile, nutrition, workout, and form analysis workflows.
            </p>
          </div>
          <div style={styles.headerActions}>
            <button style={styles.primaryButton} onClick={() => setDrawer("create-client")}><Plus size={16} />Create client</button>
            <button style={styles.secondaryButton} onClick={onLogout}>Logout</button>
          </div>
        </div>

        {error ? <div style={styles.errorBox}>{error}</div> : null}
        {successMessage ? <div style={styles.successBox}>{successMessage}</div> : null}

        <div style={styles.layout}>
          <section style={styles.clientRail}>
            <div style={styles.panelHeader}>
              <div style={styles.panelTitle}>Client list</div>
              <button style={styles.secondaryButton} onClick={loadClients} disabled={isLoading}>
                <RefreshCw size={16} />
                {isLoading ? "Refreshing..." : "Refresh"}
              </button>
            </div>

            {!clients.length && !isLoading ? (
              <EmptyState title="No clients yet" text="Create a client to start profile tracking, planning, and form analysis." />
            ) : null}

            <div style={styles.clientList}>
              {clients.map((client) => {
                const isSelected = client.id === selectedClientId;
                return (
                  <button
                    key={client.id}
                    style={isSelected ? styles.clientCardActive : styles.clientCard}
                    onClick={() => onSelectClient(client)}
                  >
                    <div style={styles.clientName}>{client.first_name} {client.last_name}</div>
                    <div style={styles.clientMeta}>
                      {client.current_goal_type ? formatGoal(client.current_goal_type) : "Goal not set"} · {client.is_active ? "Active" : "Inactive"}
                    </div>
                  </button>
                );
              })}
            </div>
          </section>

          <section style={styles.workspace}>
            {!selectedClientId ? (
              <EmptyPanel
                title="Choose a client"
                text="Select a client to open their profile, nutrition, workout, and form analysis workspace."
              />
            ) : isDetailLoading ? (
              <EmptyPanel title="Loading client workspace" text="Pulling profile, plans, progress photos, and analysis history." />
            ) : selectedClient ? (
              <>
                <div style={styles.panel}>
                  <div style={styles.workspaceHeader}>
                    <div>
                      <div style={styles.detailTitle}>{selectedClient.first_name} {selectedClient.last_name}</div>
                      <div style={styles.clientMeta}>
                        {selectedClient.current_goal_type ? formatGoal(selectedClient.current_goal_type) : "No current goal"} · {selectedClient.is_active ? "Active client" : "Inactive client"}
                      </div>
                    </div>
                    <button style={styles.secondaryButton} onClick={() => loadClientWorkspace(selectedClient.id)}>
                      Refresh detail
                    </button>
                  </div>

                  <div style={styles.detailTabRow}>
                    {renderDetailTab("profile", "Profile", UserRound, detailTab, setDetailTab)}
                    {renderDetailTab("nutrition", "Nutrition", Apple, detailTab, setDetailTab)}
                    {renderDetailTab("workout", "Workout", Dumbbell, detailTab, setDetailTab)}
                    {renderDetailTab("form-analysis", "Form Analysis", Video, detailTab, setDetailTab)}
                  </div>
                </div>

                {detailTab === "profile" ? (
                  <ProfileTab
                    client={selectedClient}
                    photos={progressPhotos}
                    onEditProfile={() => setDrawer("edit-profile")}
                    onUpdateGoal={() => setDrawer("update-goal")}
                    onAddPhoto={() => setDrawer("add-progress-photo")}
                  />
                ) : null}

                {detailTab === "nutrition" ? (
                  <PlanTab
                    typeLabel="Nutrition"
                    helper="Meal structure, calorie targets, and nutrition coaching notes stay separate from training work."
                    plans={nutritionPlans}
                    latestPlan={nutritionPlans[0] ?? null}
                    activeDraft={activeNutritionAiDraft}
                    onCreate={() => setDrawer("create-nutrition-plan")}
                    onAiDraft={() => openAiDraftDrawer("nutrition")}
                    getPdfUrl={getNutritionPlanPdfUrl}
                  />
                ) : null}

                {detailTab === "workout" ? (
                  <PlanTab
                    typeLabel="Workout"
                    helper="Training days, strength focus, and session structure are managed independently from nutrition."
                    plans={workoutPlans}
                    latestPlan={workoutPlans[0] ?? null}
                    activeDraft={activeWorkoutAiDraft}
                    onCreate={() => setDrawer("create-workout-plan")}
                    onAiDraft={() => openAiDraftDrawer("workout")}
                    getPdfUrl={getWorkoutPlanPdfUrl}
                  />
                ) : null}

                {detailTab === "form-analysis" ? (
                  <FormAnalysisTab
                    selectedClient={selectedClient}
                    analysisFile={analysisFile}
                    setAnalysisFile={setAnalysisFile}
                    isCreatingAnalysis={isCreatingAnalysis}
                    history={analysisHistory}
                    isHistoryLoading={isHistoryLoading}
                    selectedJob={selectedAnalysisJob}
                    analysis={analysis}
                    selectedRepSnapshot={selectedRepSnapshot}
                    selectedRepData={selectedRepData}
                    repRows={repRows}
                    selectedRepNumber={selectedRepNumber}
                    setSelectedRepNumber={setSelectedRepNumber}
                    supportsRepDetection={supportsRepDetection}
                    supportsDepth={supportsDepth}
                    supportsTorsoLean={supportsTorsoLean}
                    supportsKneeTracking={supportsKneeTracking}
                    feedbackNote={feedbackNote}
                    setFeedbackNote={setFeedbackNote}
                    isSavingFeedback={isSavingFeedback}
                    onCreateAnalysis={handleCreateAnalysis}
                    onOpenAnalysis={openAnalysisJob}
                    onRefreshHistory={() => selectedClientId && loadAnalysisHistory(selectedClientId)}
                    onSaveFeedback={handleSaveFeedback}
                  />
                ) : null}
              </>
            ) : (
              <EmptyPanel title="Client unavailable" text="The selected client could not be loaded." />
            )}
          </section>
        </div>
      </main>

      <Drawer title={getDrawerTitle(drawer)} isOpen={drawer !== null} onClose={() => setDrawer(null)}>
        {drawer === "create-client" ? (
          <form onSubmit={handleCreateClient} style={styles.form}>
            <LabeledField label="First name">
              <input value={createClientForm.first_name} onChange={(e) => setCreateClientForm((current) => ({ ...current, first_name: e.target.value }))} style={styles.input} required />
            </LabeledField>
            <LabeledField label="Last name">
              <input value={createClientForm.last_name} onChange={(e) => setCreateClientForm((current) => ({ ...current, last_name: e.target.value }))} style={styles.input} required />
            </LabeledField>
            <button type="submit" style={styles.primaryButton}><Plus size={16} />Create client</button>
          </form>
        ) : null}

        {drawer === "edit-profile" ? (
          <form onSubmit={handleUpdateProfile} style={styles.form}>
            <SectionEyebrow title="Identity" />
            <LabeledField label="First name"><input value={profileForm.first_name} onChange={(e) => setProfileForm((current) => ({ ...current, first_name: e.target.value }))} style={styles.input} required /></LabeledField>
            <LabeledField label="Last name"><input value={profileForm.last_name} onChange={(e) => setProfileForm((current) => ({ ...current, last_name: e.target.value }))} style={styles.input} required /></LabeledField>
            <LabeledField label="Date of birth"><input type="date" value={profileForm.dob} onChange={(e) => setProfileForm((current) => ({ ...current, dob: e.target.value }))} style={styles.input} /></LabeledField>
            <LabeledField label="Gender">
              <select value={profileForm.gender} onChange={(e) => setProfileForm((current) => ({ ...current, gender: e.target.value }))} style={styles.input}>
                <option value="">Not specified</option>
                <option value="male">Male</option>
                <option value="female">Female</option>
                <option value="other">Other</option>
              </select>
            </LabeledField>
            <SectionEyebrow title="Body metrics" />
            <LabeledField label="Height (cm)"><input type="number" value={profileForm.height_cm} onChange={(e) => setProfileForm((current) => ({ ...current, height_cm: e.target.value }))} style={styles.input} /></LabeledField>
            <LabeledField label="Weight (kg)"><input type="number" value={profileForm.weight_kg} onChange={(e) => setProfileForm((current) => ({ ...current, weight_kg: e.target.value }))} style={styles.input} /></LabeledField>
            <label style={styles.checkboxRow}>
              <input type="checkbox" checked={profileForm.is_active} onChange={(e) => setProfileForm((current) => ({ ...current, is_active: e.target.checked }))} />
              Active client
            </label>
            <button type="submit" style={styles.primaryButton} disabled={isSavingProfile}><Save size={16} />{isSavingProfile ? "Saving..." : "Save profile"}</button>
          </form>
        ) : null}

        {drawer === "update-goal" ? (
          <form onSubmit={handleSaveGoal} style={styles.form}>
            <SectionEyebrow title="Goal details" />
            <LabeledField label="Goal type">
              <select value={goalForm.goal_type} onChange={(e) => setGoalForm((current) => ({ ...current, goal_type: e.target.value }))} style={styles.input}>
                <option value="weight_gain">Weight gain</option>
                <option value="weight_loss">Weight loss</option>
                <option value="strength_training">Strength training</option>
                <option value="performance_improvement">Performance improvement</option>
              </select>
            </LabeledField>
            <LabeledField label="Start date"><input type="date" value={goalForm.start_date} onChange={(e) => setGoalForm((current) => ({ ...current, start_date: e.target.value }))} style={styles.input} /></LabeledField>
            <LabeledField label="End date"><input type="date" value={goalForm.end_date} onChange={(e) => setGoalForm((current) => ({ ...current, end_date: e.target.value }))} style={styles.input} /></LabeledField>
            <LabeledField label="Goal notes"><textarea value={goalForm.notes} onChange={(e) => setGoalForm((current) => ({ ...current, notes: e.target.value }))} style={styles.textarea} /></LabeledField>
            <button type="submit" style={styles.primaryButton} disabled={isSavingGoal}><Target size={16} />{isSavingGoal ? "Saving..." : "Save goal"}</button>
          </form>
        ) : null}

        {drawer === "add-progress-photo" ? (
          <form onSubmit={handleUploadProgressPhoto} style={styles.form}>
            <SectionEyebrow title="Photo check-in" />
            <LabeledField label="Timeline type">
              <select value={progressPhotoForm.timeline_type} onChange={(e) => setProgressPhotoForm((current) => ({ ...current, timeline_type: e.target.value }))} style={styles.input}>
                <option value="weekly">Weekly</option>
                <option value="monthly">Monthly</option>
              </select>
            </LabeledField>
            <LabeledField label="Capture date"><input type="date" value={progressPhotoForm.captured_on} onChange={(e) => setProgressPhotoForm((current) => ({ ...current, captured_on: e.target.value }))} style={styles.input} /></LabeledField>
            <LabeledField label="Progress photo" helper={progressPhotoFile ? `Selected: ${progressPhotoFile.name}` : "Upload a front, side, or check-in image."}>
              <input type="file" accept="image/*" onChange={(e) => setProgressPhotoFile(e.target.files?.[0] ?? null)} style={styles.input} />
            </LabeledField>
            <LabeledField label="Caption"><textarea value={progressPhotoForm.caption} onChange={(e) => setProgressPhotoForm((current) => ({ ...current, caption: e.target.value }))} style={styles.textarea} /></LabeledField>
            <button type="submit" style={styles.primaryButton} disabled={isSavingProgressPhoto}><ImagePlus size={16} />{isSavingProgressPhoto ? "Uploading..." : "Upload progress photo"}</button>
          </form>
        ) : null}

        {drawer === "create-nutrition-plan" ? (
          <PlanForm title="Nutrition plan" draft={nutritionDraft} isSaving={isSavingNutrition} onDraftChange={setNutritionDraft} onSubmit={handleCreateNutritionPlan} />
        ) : null}

        {drawer === "create-workout-plan" ? (
          <PlanForm title="Workout plan" draft={workoutDraft} isSaving={isSavingWorkout} onDraftChange={setWorkoutDraft} onSubmit={handleCreateWorkoutPlan} />
        ) : null}

        {drawer === "ai-nutrition-draft" ? (
          <AiPlanDraftForm
            planKind="nutrition"
            form={nutritionAiDraftForm}
            edit={nutritionAiDraftEdit}
            activeDraft={activeNutritionAiDraft}
            isGenerating={isGeneratingAiDraft}
            isSaving={isSavingAiDraft}
            isApproving={isApprovingAiDraft}
            isDiscarding={isDiscardingAiDraft}
            onFormChange={setNutritionAiDraftForm}
            onEditChange={setNutritionAiDraftEdit}
            onGenerate={(event) => handleGenerateAiDraft("nutrition", event)}
            onRegenerate={() => handleGenerateAiDraft("nutrition")}
            onSave={() => handleSaveAiDraft("nutrition")}
            onApprove={() => handleApproveAiDraft("nutrition")}
            onDiscard={() => handleDiscardAiDraft("nutrition")}
          />
        ) : null}

        {drawer === "ai-workout-draft" ? (
          <AiPlanDraftForm
            planKind="workout"
            form={workoutAiDraftForm}
            edit={workoutAiDraftEdit}
            activeDraft={activeWorkoutAiDraft}
            isGenerating={isGeneratingAiDraft}
            isSaving={isSavingAiDraft}
            isApproving={isApprovingAiDraft}
            isDiscarding={isDiscardingAiDraft}
            onFormChange={setWorkoutAiDraftForm}
            onEditChange={setWorkoutAiDraftEdit}
            onGenerate={(event) => handleGenerateAiDraft("workout", event)}
            onRegenerate={() => handleGenerateAiDraft("workout")}
            onSave={() => handleSaveAiDraft("workout")}
            onApprove={() => handleApproveAiDraft("workout")}
            onDiscard={() => handleDiscardAiDraft("workout")}
          />
        ) : null}
      </Drawer>
    </div>
  );
}

function ProfileTab({
  client,
  photos,
  onEditProfile,
  onUpdateGoal,
  onAddPhoto,
}: {
  client: Client;
  photos: ProgressPhoto[];
  onEditProfile: () => void;
  onUpdateGoal: () => void;
  onAddPhoto: () => void;
}) {
  return (
    <>
      <div style={styles.twoColumnGrid}>
        <div style={styles.panel}>
          <SectionHeader icon={UserRound} title="Profile summary" actionLabel="Edit profile" onAction={onEditProfile} />
          <div style={styles.snapshotGrid}>
            <Snapshot label="Name" value={`${client.first_name} ${client.last_name}`} />
            <Snapshot label="Status" value={client.is_active ? "Active" : "Inactive"} />
            <Snapshot label="Date of birth" value={client.dob ? new Date(client.dob).toLocaleDateString() : "Not set"} />
            <Snapshot label="Gender" value={client.gender ?? "Not set"} />
            <Snapshot label="Height" value={client.height_cm ? `${client.height_cm} cm` : "Not set"} />
            <Snapshot label="Weight" value={client.weight_kg ? `${client.weight_kg} kg` : "Not set"} />
          </div>
        </div>
        <div style={styles.panel}>
          <SectionHeader icon={Target} title="Current goal" actionLabel="Update goal" onAction={onUpdateGoal} />
          <div style={styles.goalTitle}>{client.current_goal_type ? formatGoal(client.current_goal_type) : "No goal set"}</div>
          <p style={styles.panelText}>{client.current_goal_notes || "Add a current goal to keep coaching decisions anchored."}</p>
        </div>
      </div>

      <div style={styles.panel}>
        <SectionHeader icon={Camera} title="Progress photo timeline" meta={`${photos.length} ${photos.length === 1 ? "entry" : "entries"}`} actionLabel="Add photo" onAction={onAddPhoto} />
        {!photos.length ? <EmptyState title="No progress photos" text="Add weekly or monthly check-ins to track visual progress." /> : null}
        <div style={styles.progressTimeline}>
          {photos.map((photo) => (
            <div key={photo.id} style={styles.progressCard}>
              <img src={getClientProgressPhotoUrl(photo.blob_name)} alt={photo.caption ?? "Client progress photo"} style={styles.progressImage} />
              <div style={styles.progressBody}>
                <div style={styles.historyTitle}>{formatTimelineType(photo.timeline_type)} check-in</div>
                <div style={styles.historyMeta}>{new Date(photo.captured_on).toLocaleDateString()} · uploaded {new Date(photo.created_at).toLocaleDateString()}</div>
                <div style={styles.historySummary}>{photo.caption ?? "No caption added."}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

function PlanTab({
  typeLabel,
  helper,
  plans,
  latestPlan,
  activeDraft,
  onCreate,
  onAiDraft,
  getPdfUrl,
}: {
  typeLabel: "Nutrition" | "Workout";
  helper: string;
  plans: Plan[];
  latestPlan: Plan | null;
  activeDraft: PlanDraft | null;
  onCreate: () => void;
  onAiDraft: () => void;
  getPdfUrl: (planId: number) => string;
}) {
  return (
    <>
      <div style={styles.panel}>
        <SectionHeader
          icon={typeLabel === "Nutrition" ? Apple : Dumbbell}
          title={`${typeLabel} workspace`}
          meta={`${plans.length} ${plans.length === 1 ? "plan" : "plans"}`}
          actions={[
            { label: "AI Draft", icon: Sparkles, onAction: onAiDraft, title: "Create an AI-assisted draft for coach review" },
            { label: `Create ${typeLabel.toLowerCase()} plan`, icon: Plus, onAction: onCreate },
          ]}
        />
        <p style={styles.panelText}>{helper}</p>
      </div>

      <div style={styles.twoColumnGrid}>
        <div style={styles.panel}>
          <SectionHeader icon={FileText} title="Latest plan snapshot" />
          {latestPlan ? <PlanHistoryCard plan={latestPlan} getPdfUrl={getPdfUrl} /> : <EmptyState title={`No ${typeLabel.toLowerCase()} plan yet`} text={`Create the first ${typeLabel.toLowerCase()} plan for this client.`} />}
          {activeDraft ? <PlanDraftCard draft={activeDraft} onOpen={onAiDraft} /> : null}
        </div>
        <div style={styles.panel}>
          <SectionHeader icon={ClipboardList} title="Plan history" />
          {!plans.length ? <EmptyState title="History is empty" text="Saved plans will appear here with PDF export actions." /> : null}
          <div style={styles.historyList}>
            {plans.map((plan) => <PlanHistoryCard key={plan.id} plan={plan} getPdfUrl={getPdfUrl} />)}
          </div>
        </div>
      </div>
    </>
  );
}

function FormAnalysisTab({
  selectedClient,
  analysisFile,
  setAnalysisFile,
  isCreatingAnalysis,
  history,
  isHistoryLoading,
  selectedJob,
  analysis,
  selectedRepSnapshot,
  selectedRepData,
  repRows,
  selectedRepNumber,
  setSelectedRepNumber,
  supportsRepDetection,
  supportsDepth,
  supportsTorsoLean,
  supportsKneeTracking,
  feedbackNote,
  setFeedbackNote,
  isSavingFeedback,
  onCreateAnalysis,
  onOpenAnalysis,
  onRefreshHistory,
  onSaveFeedback,
}: {
  selectedClient: Client;
  analysisFile: File | null;
  setAnalysisFile: React.Dispatch<React.SetStateAction<File | null>>;
  isCreatingAnalysis: boolean;
  history: SquatJobResponse[];
  isHistoryLoading: boolean;
  selectedJob: SquatJobResponse | null;
  analysis: SquatAnalysis | null;
  selectedRepSnapshot: { rep_number: number; frame: number; image_path: string } | null;
  selectedRepData: {
    rep: { rep_number: number; start_frame: number; bottom_frame: number; end_frame: number };
    depth?: { depth_status: string; evaluated_frame: number | null };
    torso?: { torso_lean_status: string; evaluated_frame: number | null };
  } | null;
  repRows: Array<{ rep: number; depth: string; torso: string; status: string; frame: number }>;
  selectedRepNumber: number | null;
  setSelectedRepNumber: React.Dispatch<React.SetStateAction<number | null>>;
  supportsRepDetection: boolean;
  supportsDepth: boolean;
  supportsTorsoLean: boolean;
  supportsKneeTracking: boolean;
  feedbackNote: string;
  setFeedbackNote: React.Dispatch<React.SetStateAction<string>>;
  isSavingFeedback: boolean;
  onCreateAnalysis: (e: React.FormEvent<HTMLFormElement>) => void;
  onOpenAnalysis: (job: SquatJobResponse) => void;
  onRefreshHistory: () => void;
  onSaveFeedback: () => void;
}) {
  const highlightedFrontSnapshot = supportsKneeTracking ? analysis?.frames?.knee_frame ?? null : null;

  return (
    <div style={styles.formAnalysisGrid}>
      <section style={styles.analysisMain}>
        <div style={styles.panel}>
          <SectionHeader icon={Video} title="Upload squat video" meta={selectedClient.first_name} />
          <form onSubmit={onCreateAnalysis} style={styles.form}>
            <LabeledField label="Squat video" helper={analysisFile ? `Selected: ${analysisFile.name}` : "Upload a side or front view squat video for this client."}>
              <input type="file" accept="video/*" onChange={(e) => setAnalysisFile(e.target.files?.[0] ?? null)} style={styles.input} />
            </LabeledField>
            <button type="submit" style={styles.primaryButton} disabled={isCreatingAnalysis}>
              <Activity size={16} />
              {isCreatingAnalysis ? "Queueing..." : "Start form analysis"}
            </button>
          </form>
        </div>

        <div style={styles.panel}>
          <SectionHeader icon={FileText} title="Analysis summary" meta={selectedJob ? formatAnalysisStatus(selectedJob.status) : "No analysis selected"} />
          {selectedJob ? (
            <div style={styles.jobStatusCard}>
              <div style={styles.historyTitle}>{selectedJob.original_filename}</div>
              <div style={styles.historyMeta}>Job {selectedJob.id.slice(0, 8)} · {new Date(selectedJob.created_at).toLocaleString()}</div>
              <p style={styles.panelText}>{getAnalysisSummary(selectedJob)}</p>
            </div>
          ) : (
            <EmptyState title="No analysis loaded" text="Open a saved analysis or upload a new squat video for this client." />
          )}
        </div>

        {analysis ? (
          <>
            <div style={styles.panel}>
              <SectionHeader icon={Activity} title="Frame and rep inspection" meta={formatView(analysis.video_view)} />
              <div style={styles.heroSection}>
                <div style={styles.videoFrame}>
                  {supportsRepDetection && selectedRepSnapshot ? (
                    <img src={`${API_BASE_URL}${selectedRepSnapshot.image_path}`} alt={`Rep ${selectedRepSnapshot.rep_number} bottom frame`} style={styles.frameImage} />
                  ) : null}
                  {supportsKneeTracking && highlightedFrontSnapshot ? (
                    <img src={`${API_BASE_URL}${highlightedFrontSnapshot.image_path}`} alt="Knee tracking frame" style={styles.frameImage} />
                  ) : null}
                  {!selectedRepSnapshot && !highlightedFrontSnapshot ? <div style={styles.videoPlaceholder}>No frame available</div> : null}
                  <div style={styles.frameCaption}>
                    {selectedRepData
                      ? `Rep ${selectedRepData.rep.rep_number}: depth ${supportsDepth ? formatDepth(selectedRepData.depth?.depth_status) : "skipped"}, torso ${supportsTorsoLean ? formatTorso(selectedRepData.torso?.torso_lean_status) : "skipped"}.`
                      : analysis.feedback?.summary?.message ?? analysis.message}
                  </div>
                </div>
                <div style={styles.summaryColumn}>
                  <Metric label="Detected view" value={formatView(analysis.video_view)} />
                  <Metric label="Capture quality" value={formatSuitability(analysis.view_suitability)} />
                  <Metric label="Rep count" value={String(analysis.rep_count ?? 0)} />
                </div>
              </div>

              {supportsRepDetection && repRows.length ? (
                <div style={styles.tableWrapper}>
                  <table style={styles.table}>
                    <thead>
                      <tr>
                        <th style={styles.th}>Rep</th>
                        <th style={styles.th}>Depth</th>
                        <th style={styles.th}>Torso</th>
                        <th style={styles.th}>Status</th>
                        <th style={styles.th}>Frame</th>
                        <th style={styles.th}>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {repRows.map((row) => (
                        <tr key={row.rep} style={row.rep === selectedRepNumber ? styles.selectedRow : undefined}>
                          <td style={styles.tdStrong}>Rep {row.rep}</td>
                          <td style={styles.td}>{row.depth}</td>
                          <td style={styles.td}>{row.torso}</td>
                          <td style={styles.td}>{row.status}</td>
                          <td style={styles.td}>{row.frame}</td>
                          <td style={styles.td}>
                            <button style={row.rep === selectedRepNumber ? styles.smallButtonActive : styles.smallButton} onClick={() => setSelectedRepNumber(row.rep)}>
                              {row.rep === selectedRepNumber ? "Viewing" : "View frame"}
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : null}
            </div>

            <div style={styles.panel}>
              <SectionHeader icon={Target} title="Corrective recommendations" />
              {analysis.corrective_recommendations?.length ? (
                analysis.corrective_recommendations.map((item, index) => (
                  <div key={index} style={styles.infoCard}>
                    <div style={styles.infoTitle}>{item.issue}</div>
                    <div><strong>Likely cause:</strong> {item.likely_cause}</div>
                    <div><strong>Coaching cue:</strong> {item.coaching_cue}</div>
                    <div><strong>Corrective exercise:</strong> {item.corrective_exercise}</div>
                  </div>
                ))
              ) : (
                <EmptyState title="No recommendations" text="This analysis did not return corrective recommendations." />
              )}
            </div>

            <div style={styles.panel}>
              <SectionHeader icon={Save} title="Coach note and export" />
              <LabeledField label="Coach feedback note">
                <textarea value={feedbackNote} onChange={(e) => setFeedbackNote(e.target.value)} style={styles.textareaLarge} />
              </LabeledField>
              <div style={styles.actionRow}>
                <button style={styles.primaryButton} onClick={onSaveFeedback} disabled={isSavingFeedback}><Save size={16} />{isSavingFeedback ? "Saving..." : "Save coach note"}</button>
                {selectedJob ? <PdfLink href={getFormAnalysisPdfUrl(selectedJob.id)} label="Export PDF" /> : null}
              </div>
            </div>
          </>
        ) : null}
      </section>

      <aside style={styles.analysisAside}>
        <div style={styles.panel}>
          <SectionHeader icon={ClipboardList} title="Analysis history" actionLabel={isHistoryLoading ? "Refreshing..." : "Refresh"} onAction={onRefreshHistory} />
          {!history.length && !isHistoryLoading ? <EmptyState title="No form analyses" text="Uploaded videos and processing statuses will appear here." /> : null}
          <div style={styles.historyList}>
            {history.map((job) => (
              <button key={job.id} style={selectedJob?.id === job.id ? styles.historyButtonActive : styles.historyButton} onClick={() => onOpenAnalysis(job)}>
                <div style={styles.historyTopRow}>
                  <div>
                    <div style={styles.historyTitle}>{job.original_filename}</div>
                    <div style={styles.historyMeta}>{formatAnalysisStatus(job.status)} · {new Date(job.created_at).toLocaleString()}</div>
                  </div>
                  <span style={getStatusBadgeStyle(job.status)}>{formatAnalysisStatus(job.status)}</span>
                </div>
                <div style={styles.historySummary}>{getAnalysisSummary(job)}</div>
              </button>
            ))}
          </div>
        </div>
      </aside>
    </div>
  );
}

function PlanForm({
  title,
  draft,
  isSaving,
  onDraftChange,
  onSubmit,
}: {
  title: string;
  draft: PlanDraftState;
  isSaving: boolean;
  onDraftChange: React.Dispatch<React.SetStateAction<PlanDraftState>>;
  onSubmit: (e: React.FormEvent<HTMLFormElement>) => void;
}) {
  return (
    <form onSubmit={onSubmit} style={styles.form}>
      <SectionEyebrow title="Plan window" />
      <LabeledField label={`${title} title`}><input value={draft.title} onChange={(e) => onDraftChange((current) => ({ ...current, title: e.target.value }))} style={styles.input} required /></LabeledField>
      <LabeledField label="Period type">
        <select value={draft.period_type} onChange={(e) => onDraftChange((current) => ({ ...current, period_type: e.target.value as PlanPeriodType }))} style={styles.input}>
          <option value="weekly">Weekly</option>
          <option value="monthly">Monthly</option>
        </select>
      </LabeledField>
      <LabeledField label="Period start"><input type="date" value={draft.period_start} onChange={(e) => onDraftChange((current) => ({ ...current, period_start: e.target.value }))} style={styles.input} required /></LabeledField>
      <LabeledField label="Period end"><input type="date" value={draft.period_end} onChange={(e) => onDraftChange((current) => ({ ...current, period_end: e.target.value }))} style={styles.input} required /></LabeledField>
      <SectionEyebrow title="Coaching content" />
      <LabeledField label="Primary focus"><input value={draft.focus} onChange={(e) => onDraftChange((current) => ({ ...current, focus: e.target.value }))} style={styles.input} /></LabeledField>
      <LabeledField label="Summary"><textarea value={draft.summary} onChange={(e) => onDraftChange((current) => ({ ...current, summary: e.target.value }))} style={styles.textarea} /></LabeledField>
      <LabeledField label="Meals or daily structure"><textarea value={draft.meals} onChange={(e) => onDraftChange((current) => ({ ...current, meals: e.target.value }))} style={styles.textarea} /></LabeledField>
      <LabeledField label="Training split or workout days"><textarea value={draft.workout_days} onChange={(e) => onDraftChange((current) => ({ ...current, workout_days: e.target.value }))} style={styles.textarea} /></LabeledField>
      <LabeledField label="Coach notes"><textarea value={draft.notes} onChange={(e) => onDraftChange((current) => ({ ...current, notes: e.target.value }))} style={styles.textarea} /></LabeledField>
      <button type="submit" style={styles.primaryButton} disabled={isSaving}><Plus size={16} />{isSaving ? "Saving..." : `Create ${title.toLowerCase()}`}</button>
    </form>
  );
}

function AiPlanDraftForm({
  planKind,
  form,
  edit,
  activeDraft,
  isGenerating,
  isSaving,
  isApproving,
  isDiscarding,
  onFormChange,
  onEditChange,
  onGenerate,
  onRegenerate,
  onSave,
  onApprove,
  onDiscard,
}: {
  planKind: PlanKind;
  form: AiDraftFormState;
  edit: PlanDraftState;
  activeDraft: PlanDraft | null;
  isGenerating: boolean;
  isSaving: boolean;
  isApproving: boolean;
  isDiscarding: boolean;
  onFormChange: React.Dispatch<React.SetStateAction<AiDraftFormState>>;
  onEditChange: React.Dispatch<React.SetStateAction<PlanDraftState>>;
  onGenerate: (e: React.FormEvent<HTMLFormElement>) => void;
  onRegenerate: () => void;
  onSave: () => void;
  onApprove: () => void;
  onDiscard: () => void;
}) {
  return (
    <form onSubmit={onGenerate} style={styles.form}>
      <div style={styles.noticeBox}>
        <strong>AI draft</strong>
        <span>Review before approving. Coach approval required before this becomes a final plan.</span>
      </div>
      <SectionEyebrow title="Generation inputs" />
      <LabeledField label="Period type">
        <select value={form.period_type} onChange={(e) => onFormChange((current) => ({ ...current, period_type: e.target.value as PlanPeriodType }))} style={styles.input}>
          <option value="weekly">Weekly</option>
          <option value="monthly">Monthly</option>
        </select>
      </LabeledField>
      <LabeledField label="Period start"><input type="date" value={form.period_start} onChange={(e) => onFormChange((current) => ({ ...current, period_start: e.target.value }))} style={styles.input} required /></LabeledField>
      <LabeledField label="Period end"><input type="date" value={form.period_end} onChange={(e) => onFormChange((current) => ({ ...current, period_end: e.target.value }))} style={styles.input} required /></LabeledField>
      {planKind === "nutrition" ? (
        <LabeledField label="Dietary preference">
          <select value={form.dietary_preference} onChange={(e) => onFormChange((current) => ({ ...current, dietary_preference: e.target.value as DietaryPreference }))} style={styles.input}>
            <option value="no_preference">No preference</option>
            <option value="vegetarian">Vegetarian</option>
            <option value="non_vegetarian">Non vegetarian</option>
            <option value="eggetarian">Eggetarian</option>
            <option value="vegan">Vegan</option>
          </select>
        </LabeledField>
      ) : null}
      <LabeledField label="Coach instructions"><textarea value={form.coach_prompt} onChange={(e) => onFormChange((current) => ({ ...current, coach_prompt: e.target.value }))} style={styles.textarea} placeholder="Optional guidance for this draft" /></LabeledField>

      {!activeDraft ? (
        <button type="submit" style={styles.secondaryButton} disabled={isGenerating}><Sparkles size={16} />{isGenerating ? "Generating..." : "Generate AI draft"}</button>
      ) : (
        <>
          <SectionEyebrow title="Editable draft" />
          <LabeledField label="Draft title"><input value={edit.title} onChange={(e) => onEditChange((current) => ({ ...current, title: e.target.value }))} style={styles.input} required /></LabeledField>
          <LabeledField label="Primary focus"><input value={edit.focus} onChange={(e) => onEditChange((current) => ({ ...current, focus: e.target.value }))} style={styles.input} /></LabeledField>
          <LabeledField label="Summary"><textarea value={edit.summary} onChange={(e) => onEditChange((current) => ({ ...current, summary: e.target.value }))} style={styles.textarea} /></LabeledField>
          {planKind === "nutrition" ? (
            <LabeledField label="Meals or daily structure"><textarea value={edit.meals} onChange={(e) => onEditChange((current) => ({ ...current, meals: e.target.value }))} style={styles.textarea} /></LabeledField>
          ) : (
            <>
              <LabeledField label="Training split or workout days"><textarea value={edit.workout_days} onChange={(e) => onEditChange((current) => ({ ...current, workout_days: e.target.value }))} style={styles.textarea} /></LabeledField>
              <LabeledField label="Mobility drills"><textarea value={edit.mobility_drills} onChange={(e) => onEditChange((current) => ({ ...current, mobility_drills: e.target.value }))} style={styles.textarea} /></LabeledField>
              <LabeledField label="Stretching plan"><textarea value={edit.stretching_plan} onChange={(e) => onEditChange((current) => ({ ...current, stretching_plan: e.target.value }))} style={styles.textarea} /></LabeledField>
            </>
          )}
          <LabeledField label="Coach notes"><textarea value={edit.notes} onChange={(e) => onEditChange((current) => ({ ...current, notes: e.target.value }))} style={styles.textarea} /></LabeledField>
          <div style={styles.actionRow}>
            <button type="button" style={styles.secondaryButton} onClick={onRegenerate} disabled={isGenerating}><RefreshCw size={16} />{isGenerating ? "Regenerating..." : "Regenerate"}</button>
            <button type="button" style={styles.secondaryButton} onClick={onSave} disabled={isSaving}><Save size={16} />{isSaving ? "Saving..." : "Save draft"}</button>
          </div>
          <div style={styles.actionRow}>
            <button type="button" style={styles.secondaryButton} onClick={onDiscard} disabled={isDiscarding}>{isDiscarding ? "Discarding..." : "Discard"}</button>
            <button type="button" style={styles.primaryButton} onClick={onApprove} disabled={isApproving}><Sparkles size={16} />{isApproving ? "Approving..." : "Approve as plan"}</button>
          </div>
        </>
      )}
    </form>
  );
}

function Drawer({ title, isOpen, onClose, children }: { title: string; isOpen: boolean; onClose: () => void; children: React.ReactNode }) {
  if (!isOpen) return null;
  return (
    <div style={styles.drawerBackdrop}>
      <aside style={styles.drawer}>
        <div style={styles.drawerHeader}>
          <div style={styles.drawerTitle}>{title}</div>
          <button type="button" style={styles.iconButton} onClick={onClose} aria-label="Close drawer"><X size={18} /></button>
        </div>
        {children}
      </aside>
    </div>
  );
}

type SectionAction = {
  label: string;
  icon?: LucideIcon;
  onAction: () => void;
  title?: string;
};

function SectionHeader({
  icon: Icon,
  title,
  meta,
  actionLabel,
  onAction,
  actions,
}: {
  icon?: LucideIcon;
  title: string;
  meta?: string;
  actionLabel?: string;
  onAction?: () => void;
  actions?: SectionAction[];
}) {
  const headerActions = actions ?? (actionLabel && onAction ? [{ label: actionLabel, onAction }] : []);
  return (
    <div style={styles.panelHeader}>
      <div style={styles.panelTitleWrap}>
        {Icon ? <div style={styles.panelIcon}><Icon size={18} /></div> : null}
        <div>
          <div style={styles.panelTitle}>{title}</div>
          {meta ? <div style={styles.historyMeta}>{meta}</div> : null}
        </div>
      </div>
      {headerActions.length ? (
        <div style={styles.headerButtonGroup}>
          {headerActions.map((action) => {
            const ActionIcon = action.icon ?? (action.label.includes("Refresh") ? RefreshCw : Plus);
            return (
              <button key={action.label} type="button" style={styles.secondaryButton} onClick={action.onAction} title={action.title}>
                <ActionIcon size={16} />
                {action.label}
              </button>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}

function LabeledField({ label, helper, children }: { label: string; helper?: string; children: React.ReactNode }) {
  return (
    <label style={styles.fieldGroup}>
      <span style={styles.fieldLabel}>{label}</span>
      {children}
      {helper ? <span style={styles.helperText}>{helper}</span> : null}
    </label>
  );
}

function EmptyPanel({ title, text }: { title: string; text: string }) {
  return <div style={styles.panel}><EmptyState title={title} text={text} /></div>;
}

function EmptyState({ title, text }: { title: string; text: string }) {
  return (
    <div style={styles.emptyState}>
      <div style={styles.emptyIcon}><SparkleIcon /></div>
      <div>
        <div style={styles.emptyTitle}>{title}</div>
        <div style={styles.emptyText}>{text}</div>
      </div>
    </div>
  );
}

function SparkleIcon() {
  return <Target size={18} />;
}

function Snapshot({ label, value }: { label: string; value: string }) {
  return <div style={styles.snapshotRow}><span style={styles.snapshotLabel}>{label}</span><span>{value}</span></div>;
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div style={styles.metricCard}><div style={styles.metricLabel}>{label}</div><div style={styles.metricText}>{value}</div></div>;
}

function SectionEyebrow({ title }: { title: string }) {
  return <div style={styles.sectionEyebrow}>{title}</div>;
}

function PdfLink({ href, label }: { href: string; label: string }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      style={styles.linkButton}
      onClick={(event) => {
        event.preventDefault();
        const token = getStoredAccessToken();
        window.open(`${href}?token=${encodeURIComponent(token)}`, "_blank", "noopener,noreferrer");
      }}
    >
      <FileText size={15} />
      {label}
    </a>
  );
}

function PlanHistoryCard({ plan, getPdfUrl }: { plan: Plan; getPdfUrl: (planId: number) => string }) {
  return (
    <div style={styles.historyCard}>
      <div style={styles.historyTopRow}>
        <div>
          <div style={styles.historyTitle}>{plan.title}</div>
          <div style={styles.historyMeta}>{plan.period_type} · {plan.period_start} to {plan.period_end}</div>
        </div>
        <PdfLink href={getPdfUrl(plan.id)} label="PDF" />
      </div>
      <div style={styles.historySummary}>{plan.content.summary || plan.content.focus || "No summary added."}</div>
    </div>
  );
}

function PlanDraftCard({ draft, onOpen }: { draft: PlanDraft; onOpen: () => void }) {
  return (
    <button type="button" style={styles.draftCardButton} onClick={onOpen}>
      <div style={styles.historyTopRow}>
        <div>
          <div style={styles.historyTitle}>AI draft: {draft.title}</div>
          <div style={styles.historyMeta}>Review before approving · {draft.period_start} to {draft.period_end}</div>
        </div>
        <span style={styles.statusBadge}>Coach approval required</span>
      </div>
      <div style={styles.historySummary}>{draft.content.summary || draft.content.focus || "AI draft ready for coach review."}</div>
    </button>
  );
}

function renderDetailTab(
  tab: DetailTab,
  label: string,
  Icon: LucideIcon,
  activeTab: DetailTab,
  onChange: React.Dispatch<React.SetStateAction<DetailTab>>
) {
  return (
    <button type="button" style={activeTab === tab ? styles.detailTabActive : styles.detailTab} onClick={() => onChange(tab)}>
      <Icon size={16} />
      {label}
    </button>
  );
}

function buildPlanPayload(draft: PlanDraftState): PlanPayload {
  return {
    title: draft.title,
    period_type: draft.period_type,
    period_start: draft.period_start,
    period_end: draft.period_end,
    content: {
      summary: draft.summary,
      focus: draft.focus,
      meals: draft.meals,
      workout_days: draft.workout_days,
      mobility_drills: draft.mobility_drills,
      stretching_plan: draft.stretching_plan,
      notes: draft.notes,
    },
  };
}

function getActiveAiDraft(drafts: PlanDraft[]) {
  return drafts.find((draft) => draft.status === "draft") ?? null;
}

function planDraftToEditState(draft: PlanDraft): PlanDraftState {
  return {
    title: draft.title,
    period_type: draft.period_type,
    period_start: draft.period_start,
    period_end: draft.period_end,
    summary: draft.content.summary ?? "",
    focus: draft.content.focus ?? "",
    meals: draft.content.meals ?? "",
    workout_days: draft.content.workout_days ?? "",
    mobility_drills: draft.content.mobility_drills ?? "",
    stretching_plan: draft.content.stretching_plan ?? "",
    notes: draft.content.notes ?? "",
  };
}

function aiFormFromDraft(draft: PlanDraft): AiDraftFormState {
  return {
    period_type: draft.period_type,
    period_start: draft.period_start,
    period_end: draft.period_end,
    dietary_preference: (draft.generation_preferences.dietary_preference as DietaryPreference | undefined) ?? "no_preference",
    coach_prompt: draft.coach_prompt ?? "",
  };
}

function getDrawerTitle(drawer: DrawerName) {
  switch (drawer) {
    case "create-client": return "Create client";
    case "edit-profile": return "Edit profile";
    case "update-goal": return "Update goal";
    case "add-progress-photo": return "Add progress photo";
    case "create-nutrition-plan": return "Create nutrition plan";
    case "create-workout-plan": return "Create workout plan";
    case "ai-nutrition-draft": return "AI nutrition draft";
    case "ai-workout-draft": return "AI workout draft";
    default: return "";
  }
}

function getDisplayFrame(analysis: SquatAnalysis, repNumber: number, fallbackFrame: number) {
  const depth = analysis.rep_depths?.find((item) => item.rep_number === repNumber);
  const torso = analysis.rep_torso_lean?.find((item) => item.rep_number === repNumber);
  const frame = analysis.frames?.rep_frames?.find((item) => item.rep_number === repNumber);
  return frame?.frame ?? depth?.evaluated_frame ?? torso?.evaluated_frame ?? fallbackFrame;
}

function getAnalysisSummary(job: SquatJobResponse) {
  if (job.status === "failed") return job.error_message ?? "This analysis failed before completing.";
  if (job.status === "queued") return "Uploaded and waiting for the worker to begin processing.";
  if (job.status === "running") return "Worker is processing frames and building feedback.";
  return job.coach_feedback_note ?? job.result?.squat_analysis?.feedback?.summary?.message ?? job.result?.squat_analysis?.recommendation ?? "Analysis completed.";
}

function formatGoal(goal: string) {
  return goal.replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatAnalysisStatus(status: string) {
  switch (status) {
    case "queued": return "Queued";
    case "running": return "Running";
    case "completed": return "Completed";
    case "failed": return "Failed";
    default: return "Unknown";
  }
}

function formatTimelineType(timelineType: string) {
  return timelineType === "monthly" ? "Monthly" : "Weekly";
}

function formatView(view?: string) {
  switch (view) {
    case "side_view": return "Side view";
    case "front_view": return "Front view";
    default: return "Unknown";
  }
}

function formatSuitability(suitability?: string) {
  switch (suitability) {
    case "good": return "Good";
    case "moderate": return "Moderate";
    case "not_sufficient": return "Not sufficient";
    default: return "Unknown";
  }
}

function formatDepth(status?: string) {
  switch (status) {
    case "below_parallel": return "Below parallel";
    case "at_parallel": return "At parallel";
    case "above_parallel": return "Above parallel";
    default: return "Unknown";
  }
}

function formatTorso(status?: string) {
  switch (status) {
    case "upright": return "Upright";
    case "moderate_lean": return "Moderate lean";
    case "excessive_lean": return "Excessive lean";
    default: return "Unknown";
  }
}

function getCoachStatus(depthStatus?: string) {
  switch (depthStatus) {
    case "below_parallel": return "Best rep";
    case "at_parallel": return "Solid";
    case "above_parallel": return "Needs depth";
    default: return "Review";
  }
}

function getStatusBadgeStyle(status: string): React.CSSProperties {
  switch (status) {
    case "queued": return { ...styles.statusBadge, backgroundColor: THEME.colors.warningSurface, color: THEME.colors.warning };
    case "running": return { ...styles.statusBadge, backgroundColor: THEME.colors.primaryMuted, color: THEME.colors.primary };
    case "completed": return { ...styles.statusBadge, backgroundColor: THEME.colors.successSurface, color: THEME.colors.success };
    case "failed": return { ...styles.statusBadge, backgroundColor: THEME.colors.dangerSurface, color: THEME.colors.danger };
    default: return styles.statusBadge;
  }
}

const styles: Record<string, React.CSSProperties> = {
  page: { minHeight: "100vh", display: "flex", background: THEME.gradients.app },
  main: { flex: 1, padding: 24, boxSizing: "border-box" },
  header: { display: "flex", justifyContent: "space-between", alignItems: "start", gap: 16, marginBottom: 24 },
  headerActions: { display: "flex", gap: 12 },
  pageTitle: { margin: 0, fontSize: THEME.typography.pageTitle, color: THEME.colors.ink },
  pageSubtitle: { margin: "10px 0 0", color: THEME.colors.textSoft, lineHeight: 1.5 },
  layout: { display: "grid", gridTemplateColumns: "280px 1fr", gap: 20, alignItems: "start" },
  clientRail: { backgroundColor: "rgba(255,255,255,0.82)", border: `1px solid ${THEME.colors.border}`, borderRadius: THEME.radii.panel, padding: 16, boxShadow: THEME.shadows.card },
  workspace: { display: "flex", flexDirection: "column", gap: 20 },
  panel: { backgroundColor: "rgba(255,255,255,0.88)", border: `1px solid ${THEME.colors.border}`, borderRadius: THEME.radii.panel, padding: 20, boxShadow: THEME.shadows.card },
  panelHeader: { display: "flex", justifyContent: "space-between", alignItems: "start", gap: 12, marginBottom: 16 },
  headerButtonGroup: { display: "flex", flexWrap: "wrap", justifyContent: "flex-end", gap: 10 },
  panelTitle: { fontSize: 18, fontWeight: 800, color: THEME.colors.text },
  panelTitleWrap: { display: "flex", alignItems: "center", gap: 10 },
  panelIcon: { width: 34, height: 34, borderRadius: THEME.radii.md, backgroundColor: THEME.colors.accentMuted, color: THEME.colors.accentDeep, display: "flex", alignItems: "center", justifyContent: "center" },
  panelText: { color: THEME.colors.textSoft, lineHeight: 1.6, margin: "8px 0 0" },
  primaryButton: { display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 8, padding: "11px 14px", borderRadius: THEME.radii.sm, border: "none", backgroundColor: THEME.colors.indigo, color: THEME.colors.white, fontWeight: 700, cursor: "pointer", boxShadow: `0 10px 22px ${THEME.shadows.primarySoft}` },
  secondaryButton: { display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 8, padding: "10px 14px", borderRadius: THEME.radii.sm, border: `1px solid ${THEME.colors.borderStrong}`, backgroundColor: "rgba(255,255,255,0.78)", color: THEME.colors.primaryDeep, fontWeight: 700, cursor: "pointer" },
  errorBox: { backgroundColor: THEME.colors.dangerSurface, color: THEME.colors.danger, border: "1px solid #fecaca", borderRadius: THEME.radii.sm, padding: 14, marginBottom: 16 },
  successBox: { backgroundColor: THEME.colors.successSurface, color: "#166534", border: "1px solid #bbf7d0", borderRadius: THEME.radii.sm, padding: 14, marginBottom: 16 },
  clientList: { display: "flex", flexDirection: "column", gap: 10 },
  clientCard: { width: "100%", padding: 12, borderRadius: THEME.radii.sm, border: `1px solid ${THEME.colors.border}`, backgroundColor: THEME.colors.surface, textAlign: "left", cursor: "pointer", boxShadow: "0 4px 12px rgba(15,23,42,0.04)" },
  clientCardActive: { width: "100%", padding: 12, borderRadius: THEME.radii.sm, border: PRIMARY_BORDER, background: THEME.gradients.card, textAlign: "left", cursor: "pointer", boxShadow: THEME.shadows.card },
  clientName: { fontWeight: 800, color: THEME.colors.text },
  clientMeta: { marginTop: 6, color: THEME.colors.textMuted, fontSize: 13 },
  workspaceHeader: { display: "flex", justifyContent: "space-between", gap: 12, alignItems: "start", marginBottom: 18 },
  detailTitle: { fontWeight: 800, fontSize: 24, color: THEME.colors.ink },
  detailTabRow: { display: "flex", gap: 10, flexWrap: "wrap" },
  detailTab: { display: "inline-flex", alignItems: "center", gap: 8, padding: "10px 14px", borderRadius: THEME.radii.pill, border: `1px solid ${THEME.colors.borderStrong}`, backgroundColor: "rgba(255,255,255,0.82)", color: THEME.colors.textSoft, cursor: "pointer", fontWeight: 700 },
  detailTabActive: { display: "inline-flex", alignItems: "center", gap: 8, padding: "10px 14px", borderRadius: THEME.radii.pill, border: PRIMARY_BORDER, backgroundColor: THEME.colors.indigo, color: THEME.colors.white, cursor: "pointer", fontWeight: 700 },
  twoColumnGrid: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 },
  snapshotGrid: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 },
  snapshotRow: { color: THEME.colors.textSoft, lineHeight: 1.5 },
  snapshotLabel: { display: "block", color: THEME.colors.textMuted, fontSize: 12, fontWeight: 800, marginBottom: 3 },
  goalTitle: { fontSize: 22, fontWeight: 800, color: THEME.colors.primary },
  emptyState: { display: "flex", alignItems: "flex-start", gap: 12, color: THEME.colors.textSoft, lineHeight: 1.5 },
  emptyIcon: { width: 36, height: 36, borderRadius: THEME.radii.md, backgroundColor: THEME.colors.energyMuted, color: THEME.colors.accentDeep, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 },
  emptyTitle: { fontWeight: 800, fontSize: 18, color: THEME.colors.text, marginBottom: 6 },
  emptyText: { color: THEME.colors.textMuted },
  progressTimeline: { display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: 14 },
  progressCard: { borderRadius: THEME.radii.sm, overflow: "hidden", border: `1px solid ${THEME.colors.border}`, backgroundColor: THEME.colors.surfaceMuted },
  progressImage: { width: "100%", aspectRatio: "4 / 5", objectFit: "cover", display: "block", backgroundColor: THEME.colors.border },
  progressBody: { padding: 14 },
  historyList: { display: "flex", flexDirection: "column", gap: 12 },
  historyCard: { borderRadius: THEME.radii.sm, border: `1px solid ${THEME.colors.border}`, padding: 14, backgroundColor: THEME.colors.surfaceMuted },
  draftCardButton: { width: "100%", marginTop: 12, borderRadius: THEME.radii.sm, border: PRIMARY_BORDER, padding: 14, background: THEME.gradients.card, textAlign: "left", cursor: "pointer" },
  historyButton: { borderRadius: THEME.radii.sm, border: `1px solid ${THEME.colors.border}`, padding: 14, backgroundColor: THEME.colors.surfaceMuted, textAlign: "left", cursor: "pointer" },
  historyButtonActive: { borderRadius: THEME.radii.sm, border: PRIMARY_BORDER, padding: 14, background: THEME.gradients.card, textAlign: "left", cursor: "pointer" },
  historyTopRow: { display: "flex", justifyContent: "space-between", gap: 12, alignItems: "start" },
  historyTitle: { fontWeight: 800, color: THEME.colors.text },
  historyMeta: { color: THEME.colors.textMuted, fontSize: 13, marginTop: 4 },
  historySummary: { color: THEME.colors.textSoft, marginTop: 10, lineHeight: 1.5, whiteSpace: "pre-wrap" },
  linkButton: { display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 6, padding: "8px 12px", borderRadius: THEME.radii.sm, backgroundColor: THEME.colors.indigo, color: THEME.colors.white, textDecoration: "none", fontSize: 14, fontWeight: 700 },
  fieldGroup: { display: "flex", flexDirection: "column", gap: 6 },
  fieldLabel: { color: THEME.colors.text, fontSize: 13, fontWeight: 800 },
  helperText: { color: THEME.colors.textMuted, fontSize: 12, lineHeight: 1.4 },
  input: { minHeight: THEME.fields.height, padding: "10px 12px", borderRadius: THEME.radii.sm, border: `1px solid ${THEME.colors.borderStrong}`, width: "100%", boxSizing: "border-box", backgroundColor: THEME.colors.surface, font: "inherit" },
  textarea: { minHeight: 92, padding: "10px 12px", borderRadius: THEME.radii.sm, border: `1px solid ${THEME.colors.borderStrong}`, resize: "vertical", fontFamily: "inherit", boxSizing: "border-box" },
  textareaLarge: { minHeight: 150, padding: "10px 12px", borderRadius: THEME.radii.sm, border: `1px solid ${THEME.colors.borderStrong}`, resize: "vertical", fontFamily: "inherit", boxSizing: "border-box" },
  form: { display: "flex", flexDirection: "column", gap: 14 },
  noticeBox: { display: "flex", flexDirection: "column", gap: 4, borderRadius: THEME.radii.sm, border: PRIMARY_BORDER, backgroundColor: THEME.colors.primaryMuted, color: THEME.colors.primaryDeep, padding: 14, lineHeight: 1.5 },
  checkboxRow: { display: "flex", alignItems: "center", gap: 8, color: THEME.colors.textSoft, fontWeight: 700 },
  sectionEyebrow: { marginTop: 4, paddingTop: 4, color: THEME.colors.primary, fontSize: 12, fontWeight: 800, textTransform: "uppercase", letterSpacing: 0 },
  drawerBackdrop: { position: "fixed", inset: 0, backgroundColor: "rgba(15,23,42,0.32)", display: "flex", justifyContent: "flex-end", zIndex: 20 },
  drawer: { width: 440, maxWidth: "100vw", minHeight: "100vh", overflowY: "auto", background: THEME.gradients.app, padding: 24, boxSizing: "border-box", boxShadow: THEME.shadows.drawer },
  drawerHeader: { display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 },
  drawerTitle: { fontSize: 22, fontWeight: 800, color: THEME.colors.text },
  iconButton: { width: 36, height: 36, borderRadius: THEME.radii.sm, border: `1px solid ${THEME.colors.borderStrong}`, backgroundColor: THEME.colors.surface, cursor: "pointer", display: "inline-flex", alignItems: "center", justifyContent: "center" },
  formAnalysisGrid: { display: "grid", gridTemplateColumns: "minmax(0, 1.8fr) minmax(300px, 0.9fr)", gap: 20, alignItems: "start" },
  analysisMain: { display: "flex", flexDirection: "column", gap: 20 },
  analysisAside: { position: "sticky", top: 20 },
  jobStatusCard: { borderRadius: THEME.radii.sm, border: `1px solid ${THEME.colors.border}`, backgroundColor: THEME.colors.surfaceMuted, padding: 14 },
  heroSection: { display: "grid", gridTemplateColumns: "1.7fr 1fr", gap: 16 },
  videoFrame: { backgroundColor: "#020617", color: THEME.colors.white, borderRadius: THEME.radii.sm, padding: 14 },
  frameImage: { width: "100%", maxHeight: 320, objectFit: "contain", display: "block", borderRadius: THEME.radii.sm, backgroundColor: "#111827" },
  videoPlaceholder: { minHeight: 240, display: "flex", alignItems: "center", justifyContent: "center", color: "#cbd5e1", backgroundColor: "rgba(255,255,255,0.06)", borderRadius: THEME.radii.sm },
  frameCaption: { marginTop: 12, color: "#cbd5e1", fontSize: 13, lineHeight: 1.5 },
  summaryColumn: { display: "flex", flexDirection: "column", gap: 12 },
  metricCard: { backgroundColor: THEME.colors.surfaceMuted, border: `1px solid ${THEME.colors.border}`, borderRadius: THEME.radii.sm, padding: 14 },
  metricLabel: { fontSize: 12, color: THEME.colors.textMuted, fontWeight: 800, marginBottom: 8 },
  metricText: { fontSize: 16, fontWeight: 800, color: THEME.colors.text },
  tableWrapper: { overflowX: "auto", marginTop: 16 },
  table: { width: "100%", borderCollapse: "collapse" },
  th: { textAlign: "left", fontSize: 13, color: THEME.colors.textMuted, fontWeight: 800, padding: "12px 8px", borderBottom: `1px solid ${THEME.colors.border}` },
  td: { padding: "12px 8px", borderBottom: "1px solid #f1f5f9", fontSize: 14, color: THEME.colors.textSoft },
  tdStrong: { padding: "12px 8px", borderBottom: "1px solid #f1f5f9", fontSize: 14, fontWeight: 800, color: THEME.colors.text },
  selectedRow: { backgroundColor: THEME.colors.surfaceMuted },
  smallButton: { padding: "8px 10px", borderRadius: THEME.radii.sm, border: `1px solid ${THEME.colors.borderStrong}`, backgroundColor: THEME.colors.surface, cursor: "pointer" },
  smallButtonActive: { padding: "8px 10px", borderRadius: THEME.radii.sm, border: PRIMARY_BORDER, backgroundColor: THEME.colors.primary, color: THEME.colors.white, cursor: "pointer" },
  infoCard: { backgroundColor: THEME.colors.surfaceMuted, borderRadius: THEME.radii.sm, padding: 14, marginTop: 12, color: THEME.colors.textSoft, lineHeight: 1.6 },
  infoTitle: { fontWeight: 800, marginBottom: 6, color: THEME.colors.primary },
  actionRow: { display: "flex", gap: 12, alignItems: "center", marginTop: 14 },
  statusBadge: { borderRadius: THEME.radii.pill, padding: "6px 10px", fontSize: 12, fontWeight: 800, whiteSpace: "nowrap" },
};
