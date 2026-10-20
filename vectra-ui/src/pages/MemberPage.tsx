import { features } from '../services/features'
import PtPage from './PtPage'
import GymMemberRegistrations from '../components/GymMemberRegistrations'
import { useEffect, useState } from 'react'
import { fetchClient, listClientProgressPhotos, uploadClientProgressPhoto } from '../services/clientApi'
import { listNutritionPlans, listWorkoutPlans, getNutritionPlanPdfUrl, getWorkoutPlanPdfUrl } from '../services/planApi'
import { listClientSquatJobs, createSquatJob, getFormAnalysisPdfUrl } from '../services/squatApi'
import { useBusiness } from '../components/BusinessContext'
import ProtectedImage from '../components/ProtectedImage'
import ProgressGallery from '../components/ProgressGallery'
import { PageHeader, StatusBadge, Skeleton, Button } from '../design-system/components'
import { downloadProtected } from '../services/download'
import { API_BASE_URL } from '../services/apiConfig'
import type { Client, ProgressPhoto } from '../types/client'
import type { Plan } from '../types/plan'
import type { SquatJobResponse } from '../types/squat'
import { fetchCoachingAccess, fetchGoals } from '../services/workspaceApi'
import type { Goal } from '../types/client'

export default function MemberPage() {
  const business = useBusiness()!
  const [client, setClient] = useState<Client | null>(null)
  const [photos, setPhotos] = useState<ProgressPhoto[]>([])
  const [nutrition, setNutrition] = useState<Plan[]>([])
  const [workouts, setWorkouts] = useState<Plan[]>([])
  const [analyses, setAnalyses] = useState<SquatJobResponse[]>([])
  const [error, setError] = useState('')
  const [revision, setRevision] = useState(0)
  const [busy, setBusy] = useState(false)
  const [canUpload, setCanUpload] = useState(false)
  const [goals, setGoals] = useState<Goal[]>([])
  const clientId = business.client_id
  useEffect(() => {
    if (clientId === null) return
    let active = true
    Promise.all([fetchClient(clientId), listClientProgressPhotos(clientId), listNutritionPlans(clientId), listWorkoutPlans(clientId), listClientSquatJobs(clientId), fetchCoachingAccess(clientId), fetchGoals(clientId)])
      .then(([profile, images, meals, training, jobs, access, targets]) => {
        if (!active) return
        setClient(profile); setPhotos(images); setNutrition(meals); setWorkouts(training); setAnalyses(jobs.analyses)
        setCanUpload(access.can_upload); setGoals(targets); setError('')
      }).catch(err => { if (active) setError(err.message) })
    return () => { active = false }
  }, [clientId, revision])
  async function upload(file: File | undefined, video: boolean) {
    if (!file || clientId === null) return
    setBusy(true); setError('')
    try {
      if (video) await createSquatJob(file, clientId)
      else await uploadClientProgressPhoto(clientId, { file, timeline_type: 'weekly', captured_on: new Date().toISOString().slice(0, 10) })
      setRevision(value => value + 1)
    } catch (err) { setError(err instanceof Error ? err.message : 'Upload failed') }
    finally { setBusy(false) }
  }
  const download = (url: string) => { void downloadProtected(url).catch(err => setError(err.message)) }
  if (clientId === null) return <main id="workspace" tabIndex={-1} className="member-home"><h1>Your account is ready</h1>{business.organization_type === 'gym' && <><GymMemberRegistrations /><PtPage /></>}<p>Your business has not linked a coaching profile yet. Contact its administrator.</p></main>
  if (!client && error) return <main id="workspace" tabIndex={-1} className="member-home"><p role="alert">{error}</p><Button onClick={() => { setError(''); setRevision(value => value + 1) }}>Try again</Button></main>
  if (!client && !error) return <main id="workspace" tabIndex={-1} className="member-home"><Skeleton label="Loading your coaching profile…" /></main>
  return <main id="workspace" tabIndex={-1} className="member-home">
    <PageHeader eyebrow="Your performance hub" title={client ? `${client.first_name}, keep moving forward.` : 'Your progress starts here.'} description={`Your plans and check-ins in ${business.name}.`} />
    {error && <p role="alert">{error}</p>}
    {!canUpload && <p role="status">Your published plans and progress history remain available. New uploads require an active coaching profile and, for gym members, current paid membership and PT coverage.</p>}
    {business.organization_type === 'gym' && <><GymMemberRegistrations /><PtPage /></>}
    {business.organization_type === 'coaching' && <PtPage />}
    <div className="member-grid">
      <section className="workspace-card"><h2>Your goals</h2>{goals.length === 0 && <p>No goals published yet.</p>}{goals.map(goal => <article key={goal.id}><h3>{goal.goal_type.replaceAll('_', ' ')}</h3><p>{goal.start_date || 'No start date'} – {goal.end_date || 'Ongoing'}</p><StatusBadge tone={goal.is_current ? 'success' : 'neutral'}>{goal.is_current ? 'Current' : 'Previous'}</StatusBadge></article>)}</section>
      {([['Nutrition', nutrition, getNutritionPlanPdfUrl], ['Workouts', workouts, getWorkoutPlanPdfUrl]] as const).map(([label, plans, pdf]) => <section className="workspace-card" key={label}>
        <h2>{label}</h2>{plans.length === 0 && <p>No published plan yet.</p>}
        {plans.map(plan => <article key={plan.id}><h3>{plan.title}</h3><p>{plan.period_start} – {plan.period_end}</p><PlanContent value={plan.content} /><button onClick={() => download(pdf(plan.id))}>Download PDF</button></article>)}
      </section>)}
      <section className="workspace-card"><h2>Progress photos</h2><label>Upload photo <input type="file" accept="image/*" disabled={busy || !canUpload} onChange={event => void upload(event.target.files?.[0], false)} /></label>
        <ProgressGallery photos={photos} />
      </section>
      {features.formAnalysis && <section className="workspace-card"><h2>Form analysis</h2><label>Upload squat video <input type="file" accept="video/*" disabled={busy || !canUpload} onChange={event => void upload(event.target.files?.[0], true)} /></label>
        <button onClick={() => setRevision(value => value + 1)}>Refresh results</button>
        {analyses.map(job => <article key={job.id}><h3>{job.original_filename}</h3><StatusBadge tone={job.status === "completed" ? "success" : job.status === "failed" ? "danger" : "info"}>{job.status}</StatusBadge><p>{job.coach_feedback_note}</p>
          {job.result && <div><p>{job.result.squat_analysis.feedback?.summary.message || job.result.squat_analysis.message}</p>
            <ul>{job.result.squat_analysis.feedback?.recommendations.map((recommendation, index) => <li key={index}>{recommendation}</li>)}</ul>
            <div className="member-photos">{job.result.squat_analysis.frames?.rep_frames?.map(frame => <ProtectedImage key={frame.rep_number} src={`${API_BASE_URL}${frame.image_path}`} alt={`Rep ${frame.rep_number}`} />)}</div>
          </div>}<button onClick={() => download(getFormAnalysisPdfUrl(job.id))}>Download report</button></article>)}
      </section>}
    </div>
  </main>
}

function PlanContent({ value }: { value: unknown }) {
  if (value === null || value === undefined) return null
  if (Array.isArray(value)) return <ul>{value.map((item, index) => <li key={index}><PlanContent value={item} /></li>)}</ul>
  if (typeof value === 'object') return <dl>{Object.entries(value).map(([key, item]) => <div key={key}><dt>{key.replaceAll('_', ' ')}</dt><dd><PlanContent value={item} /></dd></div>)}</dl>
  return <span>{String(value)}</span>
}
