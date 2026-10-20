import { features } from '../services/features'
import { useBusiness } from '../components/BusinessContext'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { ArrowRight, RefreshCw, UsersRound, Activity, Target, ScanLine } from 'lucide-react'
import { Button, Card, PageHeader, StatusBadge, Skeleton, EmptyState } from '../design-system/components'
import { listClients } from '../services/clientApi'
import { listNutritionPlans, listWorkoutPlans } from '../services/planApi'
import { listSquatJobs } from '../services/squatApi'
import type { CoachProfile } from '../types/auth'
import type { Client } from '../types/client'
import type { AppTab } from '../types/navigation'
import type { Plan } from '../types/plan'
import type { SquatJobResponse } from '../types/squat'

type Props = { activeTab: AppTab; onTabChange: (tab: AppTab) => void; onLogout: () => void; requestedJob?: SquatJobResponse | null; onJobLoaded?: (job: SquatJobResponse) => void; selectedClient?: Client | null; selectedClientId?: number | null; coach?: CoachProfile | null }
export default function DashboardPage({ onTabChange, selectedClient, selectedClientId, coach }: Props) {
  const business = useBusiness()
  const canCreate = business?.staff_roles.some(role => role === 'owner' || role === 'admin')
  const [clients, setClients] = useState<Client[]>([])
  const [analyses, setAnalyses] = useState<SquatJobResponse[]>([])
  const [nutritionPlans, setNutritionPlans] = useState<Plan[]>([])
  const [workoutPlans, setWorkoutPlans] = useState<Plan[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
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

  const metrics = [
    { label: 'Total clients', value: clients.length, note: 'Visible in this workspace', Icon: UsersRound },
    { label: 'Active clients', value: activeClients, note: 'Current coaching records', Icon: Activity },
    { label: 'Goals in focus', value: clientsWithGoals, note: 'Clients with a current goal', Icon: Target },
    ...(features.formAnalysis ? [{ label: 'Recent analyses', value: analyses.length, note: `Latest 12 · ${completedAnalyses} complete`, Icon: ScanLine }] : []),
  ]
  return <main className="page-content dashboard">
    <PageHeader eyebrow={business?.name || 'Your workspace'} title="Ready for the next step." description={coach ? `Welcome back, ${coach.first_name}. Keep your clients moving forward.` : 'Your clients, their progress, and the work ahead.'} actions={<><Button variant="secondary" disabled={isLoading} onClick={loadDashboard} aria-label="Refresh dashboard"><RefreshCw size={16} /></Button><Button onClick={() => onTabChange('clients')}>{canCreate ? 'Manage clients' : 'Assigned clients'}<ArrowRight size={16} /></Button></>} />
    {error && <p role="alert" className="error-notice">{error} Refresh to try again.</p>}
    {isLoading ? <Skeleton label="Loading your workspace overview…" /> : <section className="kpi-grid" aria-label="Workspace metrics">{metrics.map(({ label, value, note, Icon }) => <Card key={label} className="kpi-card"><div className="kpi-label"><span>{label}</span><Icon size={18} /></div><div className="metric-value">{error ? '—' : value}</div><p>{error ? 'Could not refresh data' : note}</p></Card>)}</section>}
    <div className="dashboard-grid">
      <Card className="coaching-focus"><p className="eyebrow">Coaching / in focus</p><h2>{selectedClient ? `${selectedClient.first_name} ${selectedClient.last_name}` : 'Good coaching starts with context.'}</h2><p>{selectedClient ? (selectedClient.current_goal_type?.replaceAll('_', ' ') || 'No current goal set') : 'Profiles, training plans, nutrition and progress tracking. Everything you need for your next client conversation.'}</p><Button onClick={() => onTabChange('clients')}>{selectedClient ? 'Continue client work' : 'Open client workspace'}<ArrowRight size={16} /></Button>
        {selectedClient && <div className="focus-plan"><span>Latest plan</span><strong>{latestPlan ? latestPlan.title : 'No plan published yet'}</strong>{latestPlan && <span>Updated {formatDate(latestPlan.updated_at)}</span>}</div>}
      </Card>
      {features.formAnalysis && <Card><div className="section-heading"><h2>Movement review</h2><StatusBadge tone={activeAnalyses ? 'info' : 'neutral'}>{activeAnalyses ? `${activeAnalyses} in progress` : 'Latest activity'}</StatusBadge></div>
        {isLoading ? <Skeleton label="Loading analyses…" /> : error ? <p>Analysis activity is temporarily unavailable.</p> : latestAnalysis ? <><div className="analysis-feature"><ScanLine size={26} /><div><h3>{latestAnalysis.original_filename}</h3><p>{formatDate(latestAnalysis.created_at)}</p></div></div><StatusBadge tone={latestAnalysis.status === 'completed' ? 'success' : latestAnalysis.status === 'failed' ? 'danger' : 'info'}>{latestAnalysis.status}</StatusBadge><p>Review the available results and continue in the client workspace.</p><Button variant="secondary" onClick={() => onTabChange('recent-analysis')}>Review analyses<ArrowRight size={16} /></Button></> : <EmptyState title="Your review library starts here" action={<Button variant="secondary" onClick={() => onTabChange('clients')}>Open clients</Button>}>Upload a client’s squat video to begin movement analysis.</EmptyState>}
      </Card>}
    </div>
    {!isLoading && !error && clients.length > 0 && <Card className="client-overview"><div className="section-heading"><div><p className="eyebrow">People / progress</p><h2>Your coaching roster</h2></div><Button variant="tertiary" onClick={() => onTabChange('clients')}>View all<ArrowRight size={16} /></Button></div><div className="roster-list">{clients.slice(0, 5).map(client => <div className="roster-row" key={client.id}><span className="avatar">{client.first_name[0]}{client.last_name[0]}</span><div><strong>{client.first_name} {client.last_name}</strong><p>{client.current_goal_type?.replaceAll('_', ' ') || 'Goal not set'}</p></div><StatusBadge tone={client.is_active ? 'success' : 'neutral'}>{client.is_active ? 'Active' : 'Inactive'}</StatusBadge></div>)}</div></Card>}
  </main>
}
function formatDate(value: string) { return new Date(value).toLocaleDateString('en-IN', { month: 'short', day: 'numeric', year: 'numeric' }) }
