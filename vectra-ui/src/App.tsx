import React, { useCallback, useEffect, useState } from "react";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import PlaceholderPage from "./pages/PlaceholderPage";
import RecentAnalysisPage from "./pages/RecentAnalysisPage";
import ClientsPage from "./pages/ClientsPage";
import { fetchCurrentUser, loginUser, signupCoach } from "./services/authApi";
import { getStoredAccessToken, setStoredAccessToken } from "./services/session";
import type { AppTab } from "./types/navigation";
import type { SquatJobResponse } from "./types/squat";
import type { Client } from "./types/client";
import type { CoachProfile } from "./types/auth";

const ACTIVE_TAB_STORAGE_KEY = "vectra.activeTab";
const SELECTED_CLIENT_STORAGE_KEY = "vectra.selectedClientId";

function getStoredActiveTab(): AppTab {
  if (typeof window === "undefined") {
    return "dashboard";
  }

  const savedTab = window.localStorage.getItem(ACTIVE_TAB_STORAGE_KEY);
  const allowedTabs: AppTab[] = [
    "dashboard",
    "recent-analysis",
    "clients",
    "sessions",
    "insights",
    "settings",
  ];

  if (savedTab && allowedTabs.includes(savedTab as AppTab)) {
    return savedTab as AppTab;
  }

  return "dashboard";
}

function getStoredClientId() {
  if (typeof window === "undefined") {
    return null;
  }

  const raw = window.localStorage.getItem(SELECTED_CLIENT_STORAGE_KEY);
  return raw ? Number(raw) : null;
}

export default function App() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [authMode, setAuthMode] = useState<"signin" | "signup">("signin");
  const [error, setError] = useState("");
  const [isLoggedIn, setIsLoggedIn] = useState(Boolean(getStoredAccessToken()));
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isBootstrapping, setIsBootstrapping] = useState(Boolean(getStoredAccessToken()));
  const [activeTab, setActiveTab] = useState<AppTab>(getStoredActiveTab);
  const [selectedJob, setSelectedJob] = useState<SquatJobResponse | null>(null);
  const [selectedClient, setSelectedClient] = useState<Client | null>(null);
  const [selectedClientId, setSelectedClientId] = useState<number | null>(getStoredClientId);
  const [coach, setCoach] = useState<CoachProfile | null>(null);

  useEffect(() => {
    window.localStorage.setItem(ACTIVE_TAB_STORAGE_KEY, activeTab);
  }, [activeTab]);

  useEffect(() => {
    if (selectedClientId == null) {
      window.localStorage.removeItem(SELECTED_CLIENT_STORAGE_KEY);
      return;
    }

    window.localStorage.setItem(SELECTED_CLIENT_STORAGE_KEY, String(selectedClientId));
  }, [selectedClientId]);

  useEffect(() => {
    const token = getStoredAccessToken();
    if (!token) {
      setIsBootstrapping(false);
      return;
    }

    fetchCurrentUser()
      .then((result) => {
        setCoach(result.coach);
        setIsLoggedIn(true);
      })
      .catch(() => {
        setStoredAccessToken("");
        setIsLoggedIn(false);
      })
      .finally(() => {
        setIsBootstrapping(false);
      });
  }, []);

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
    setStoredAccessToken("");
    setIsLoggedIn(false);
    setActiveTab("dashboard");
    setSelectedJob(null);
    setSelectedClient(null);
    setSelectedClientId(null);
    setCoach(null);
    setEmail("");
    setPassword("");
    setFirstName("");
    setLastName("");
    setError("");
  };

  const handleSelectClient = useCallback((client: Client) => {
    setSelectedClient(client);
    setSelectedClientId(client.id);
  }, []);

  if (isBootstrapping) {
    return <div style={{ padding: 32, fontFamily: "sans-serif" }}>Loading coach workspace…</div>;
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
      />
    );
  }

  if (activeTab === "recent-analysis") {
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
