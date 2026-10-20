import { features } from './services/features'
import PtPage from './pages/PtPage'
import InboxPage from './pages/InboxPage'
import ReportsPage from './pages/ReportsPage'
import GymJoinPage from './pages/GymJoinPage'
import GymSetupPage from './pages/GymSetupPage'
import React, { useCallback, useEffect, useRef, useState } from "react";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import PlaceholderPage from "./pages/PlaceholderPage";
import RecentAnalysisPage from "./pages/RecentAnalysisPage";
import ClientsPage from "./pages/ClientsPage";
import { fetchCurrentUser, loginUser, signupCoach } from "./services/authApi";
import { getStoredAccessToken, setStoredAccessToken, selectBusiness, selectAccessMode } from "./services/session";
import type { AppTab } from "./types/navigation";
import type { SquatJobResponse } from "./types/squat";
import type { Client } from "./types/client";
import type { AuthUser, CoachProfile, OrganizationContext } from "./types/auth";

import { BusinessContext, useBusiness } from './components/BusinessContext'
import MemberPage from './pages/MemberPage'
import AccessPage from './pages/AccessPage'
import BillingGate from './components/BillingGate'
import BusinessOnboardingPage from './pages/BusinessOnboardingPage'
import EmailActionPage, { VerifyEmailPage } from './pages/EmailActionPage'
import './workspace.css'
import AppShell from './design-system/AppShell'
import { Button, Skeleton } from './design-system/components'

export default function App() {
  const [addingBusiness, setAddingBusiness] = useState(false)
  const [emailAction, setEmailAction] = useState(() => {
    const params = new URLSearchParams(window.location.hash.slice(1))
    return params.has('action') ? { action: params.get('action') || '', token: params.get('token') || '' } : null
  })
  const [user, setUser] = useState<AuthUser | null>(null)
  useEffect(() => {
    const openEmailLink = () => {
      const params = new URLSearchParams(window.location.hash.slice(1))
      if (params.has('action')) setEmailAction({ action: params.get('action') || '', token: params.get('token') || '' })
    }
    window.addEventListener('hashchange', openEmailLink)
    return () => window.removeEventListener('hashchange', openEmailLink)
  }, [])
  useEffect(() => {
    if (emailAction) window.history.replaceState(null, '', window.location.pathname + window.location.search)
  }, [emailAction])
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [authMode, setAuthMode] = useState<"signin" | "signup">("signin");
  const [error, setError] = useState("");
  const [isLoggedIn, setIsLoggedIn] = useState(Boolean(getStoredAccessToken()));
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isBootstrapping, setIsBootstrapping] = useState(Boolean(getStoredAccessToken()));
  const [coach, setCoach] = useState<CoachProfile | null>(null)
  const [organizations, setOrganizations] = useState<OrganizationContext[]>([])
  const [selectedBusiness, setSelectedBusiness] = useState<number | null>(() => {
    const id = Number(window.sessionStorage.getItem('vectra.onboardingBusiness'))
    return id > 0 ? id : null
  })
  useEffect(() => { window.sessionStorage.removeItem('vectra.onboardingBusiness') }, [])
  const [contextRevision, setContextRevision] = useState(0)
  const contextSignature = useRef('')
  const applySession = useCallback((items: OrganizationContext[]) => {
    const signature = JSON.stringify(items)
    if (signature === contextSignature.current) return
    contextSignature.current = signature
    setOrganizations(items)
    setSelectedBusiness(current => {
      const next = items.some(item => item.organization_id === current) ? current : items[0]?.organization_id ?? null
      selectBusiness(next)
      return next
    })
    setContextRevision(value => value + 1)
  }, [])

  useEffect(() => {
    const token = getStoredAccessToken();
    if (!token) {
      setIsBootstrapping(false);
      return;
    }

    fetchCurrentUser()
      .then((result) => {
        setCoach(result.coach);
        setUser(result.user);
        applySession(result.organizations);
        setIsLoggedIn(true);
      })
      .catch(() => {
        setStoredAccessToken("");
        setIsLoggedIn(false);
      })
      .finally(() => {
        setIsBootstrapping(false);
      });
  }, [applySession]);

  useEffect(() => {
    if (!isLoggedIn) return
    const refresh = () => {
      fetchCurrentUser().then(result => { setUser(result.user); applySession(result.organizations) }).catch(() => {
        setStoredAccessToken(''); setIsLoggedIn(false); setOrganizations([])
      })
    }
    window.addEventListener('focus', refresh)
    const storage = (event: StorageEvent) => { if (event.key === 'vectra.accessToken') window.location.reload() }
    window.addEventListener('storage', storage)
    return () => { window.removeEventListener('focus', refresh); window.removeEventListener('storage', storage) }
  }, [isLoggedIn, applySession])

  const handleAuth = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    try {
      setIsSubmitting(true);
      setError("");

      const result =
        authMode === "signup"
          ? await signupCoach({
              email,
              password,
              coach: {
                first_name: firstName,
                last_name: lastName,
              },
            })
          : await loginUser({
              email,
              password,
            });

      setCoach(result.coach);
        setUser(result.user);
      contextSignature.current = '';
      applySession(result.organizations);
      setIsLoggedIn(true);
      setError("");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Authentication failed.";
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleLogout = () => {
    contextSignature.current = '';
    setStoredAccessToken("");
    setIsLoggedIn(false);
    setCoach(null);
    setUser(null);
    setOrganizations([]);
    setSelectedBusiness(null);
    setEmail("");
    setPassword("");
    setFirstName("");
    setLastName("");
    setError("");
  };

  const joinMatch = window.location.pathname.match(/^\/join\/([0-9a-f-]{36})\/?$/i)
  if (emailAction) return <EmailActionPage key={emailAction.token || emailAction.action} action={emailAction.action} token={emailAction.token} onBack={() => { const pending = sessionStorage.getItem('vectra.pendingGymJoin'); window.location.href = joinMatch ? window.location.pathname : pending && /^\/join\/[0-9a-f-]{36}$/i.test(pending) ? pending : window.location.pathname }} />
  if (joinMatch && !isBootstrapping) return <GymJoinPage key={`${joinMatch[1]}:${user?.id ?? "guest"}`} publicId={joinMatch[1]} user={isLoggedIn ? user : null} onLogout={handleLogout} />
  if (isLoggedIn && user?.verification_required) return <VerifyEmailPage email={user.email} onLogout={handleLogout} />

  if (isBootstrapping) {
    return <main className="page-content"><Skeleton label="Loading your workspace…" /></main>;
  }

  if ((!isLoggedIn && authMode === 'signup') || (isLoggedIn && addingBusiness)) {
    return <BusinessOnboardingPage register={!isLoggedIn} onBack={() => { setAuthMode('signin'); setAddingBusiness(false) }} />
  }

  if (!isLoggedIn) {
    return (
      <LoginPage
        email={email}
        password={password}
        firstName={firstName}
        lastName={lastName}
        authMode={authMode}
        error={error}
        isSubmitting={isSubmitting}
        onEmailChange={setEmail}
        onPasswordChange={setPassword}
        onFirstNameChange={setFirstName}
        onLastNameChange={setLastName}
        onModeChange={setAuthMode}
        onSubmit={handleAuth}
        onForgotPassword={() => setEmailAction({ action: "request-recovery", token: "" })}
      />
    );
  }

  const business = organizations.find(item => item.organization_id === selectedBusiness)
  return <>
    <a className="skip-link" href="#workspace">Skip to workspace</a>
    <header className="business-bar">
      <strong>Vectra</strong>
      {organizations.length > 1 ? <label>Business <select aria-label="Current business" value={selectedBusiness ?? ''} onChange={event => {
        const id = Number(event.target.value)
        selectBusiness(id); setSelectedBusiness(id); setContextRevision(value => value + 1)
      }}>{organizations.map(item => <option key={item.organization_id} value={item.organization_id}>{item.name}</option>)}</select></label> : <span className="business-name">{business?.name}</span>}
      <span className="business-role">{business?.staff_roles.join(' · ') || 'Member'}</span>
      <div className="account-actions"><Button variant="secondary" onClick={() => setAddingBusiness(true)}>Add business</Button>
      <Button variant="tertiary" onClick={handleLogout}>Sign out</Button></div>
    </header>
    {business ? <BusinessContext.Provider value={business}>
      <BillingGate key={`${business.organization_id}:${contextRevision}`} organizationId={business.organization_id}><Workspace coach={coach} handleLogout={handleLogout} /></BillingGate>
    </BusinessContext.Provider> : <main id="workspace" tabIndex={-1} className="member-home"><h1>No active business access</h1><p>Contact your business administrator to link your account, or add a business you own.</p><button onClick={() => setAddingBusiness(true)}>Add business</button></main>}
  </>
}

function Workspace({ coach, handleLogout }: { coach: CoachProfile | null; handleLogout: () => void }) {
  const business = useBusiness()!
  const [activeTab, setActiveTab] = useState<AppTab>('dashboard')
  const [selectedJob, setSelectedJob] = useState<SquatJobResponse | null>(null)
  const [selectedClient, setSelectedClient] = useState<Client | null>(null)
  const [selectedClientId, setSelectedClientId] = useState<number | null>(null)
  const [memberView, setMemberView] = useState(false)
  const handleSelectClient = useCallback((client: Client) => {
    setSelectedClient(client); setSelectedClientId(client.id)
  }, [])
  if (!business.staff_roles.length) return <MemberWorkspace />
  if (memberView) return <><div className="workspace-shortcuts"><Button variant="secondary" onClick={() => { selectAccessMode("staff"); setMemberView(false) }}>Back to staff workspace</Button></div><MemberWorkspace /></>
  const content = () => {
  if (activeTab === 'inbox') return <InboxPage />
  if (activeTab === 'insights' && business.staff_roles.some(role => role === 'owner' || role === 'admin')) return <ReportsPage />
  if (activeTab === 'gym-setup' && business.organization_type === 'gym' && business.staff_roles.some(role => role === 'owner' || role === 'admin')) return <GymSetupPage />
  if (features.formAnalysis && activeTab === "recent-analysis") {
    return (
      <RecentAnalysisPage
        activeTab={activeTab}
        onTabChange={setActiveTab}
        selectedJobId={selectedJob?.id ?? null}
        onLogout={handleLogout}
        onOpenAnalysis={(job) => {
          setSelectedJob(job);
          if (job.client_id) {
            setSelectedClientId(job.client_id);
          }
          setActiveTab("clients");
        }}
      />
    );
  }

  if (activeTab === "clients") {
    return (
      <ClientsPage
        activeTab={activeTab}
        onTabChange={setActiveTab}
        onLogout={handleLogout}
        selectedClientId={selectedClientId}
        onSelectClient={handleSelectClient}
        requestedAnalysis={selectedJob}
        onAnalysisLoaded={setSelectedJob}
      />
    );
  }

  if (activeTab === "settings" && business.staff_roles.some(role => role === "owner" || role === "admin")) return <AccessPage />;

  if (activeTab === "sessions") return <PtPage />

  if (activeTab !== "dashboard") {
    return (
      <PlaceholderPage
        activeTab={activeTab}
        onTabChange={setActiveTab}
        onLogout={handleLogout}
      />
    );
  }

  return (
    <DashboardPage
      activeTab={activeTab}
      onTabChange={setActiveTab}
      onLogout={handleLogout}
      requestedJob={selectedJob}
      onJobLoaded={setSelectedJob}
      selectedClient={selectedClient}
      selectedClientId={selectedClientId}
      coach={coach}
    />
  );
  }
  return <AppShell activeTab={activeTab} onTabChange={setActiveTab} memberAction={business.client_id !== null ? () => { selectAccessMode('member'); setMemberView(true) } : undefined}>
    {content()}
  </AppShell>
}

function MemberWorkspace() {
  const [inbox, setInbox] = useState(false)
  return <><nav className="workspace-shortcuts" aria-label="Member navigation">
    <Button variant={inbox ? 'secondary' : 'primary'} onClick={() => setInbox(false)}>My coaching</Button>
    <Button variant={inbox ? 'primary' : 'secondary'} onClick={() => setInbox(true)}>Inbox</Button>
  </nav>{inbox ? <main id="workspace" tabIndex={-1}><InboxPage memberMode /></main> : <MemberPage />}</>
}
