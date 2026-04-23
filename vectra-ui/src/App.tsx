import React, { useEffect, useState } from "react";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import PlaceholderPage from "./pages/PlaceholderPage";
import RecentAnalysisPage from "./pages/RecentAnalysisPage";
import { loginUser } from "./services/authApi";
import type { AppTab } from "./types/navigation";
import type { SquatJobResponse } from "./types/squat";

const AUTH_STORAGE_KEY = "vectra.isLoggedIn";
const ACTIVE_TAB_STORAGE_KEY = "vectra.activeTab";

function getStoredLoginState() {
  if (typeof window === "undefined") {
    return false;
  }

  return window.sessionStorage.getItem(AUTH_STORAGE_KEY) === "true";
}

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

export default function App() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isLoggedIn, setIsLoggedIn] = useState(getStoredLoginState);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [activeTab, setActiveTab] = useState<AppTab>(getStoredActiveTab);
  const [selectedJob, setSelectedJob] = useState<SquatJobResponse | null>(null);

  useEffect(() => {
    window.sessionStorage.setItem(AUTH_STORAGE_KEY, String(isLoggedIn));
  }, [isLoggedIn]);

  useEffect(() => {
    window.localStorage.setItem(ACTIVE_TAB_STORAGE_KEY, activeTab);
  }, [activeTab]);

  const handleLogin = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    try {
      setIsSubmitting(true);
      setError("");

      const result = await loginUser({
        username,
        password,
      });

      if (result.authenticated) {
        setIsLoggedIn(true);
        setError("");
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Login failed.";
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleLogout = () => {
    setIsLoggedIn(false);
    setActiveTab("dashboard");
    setSelectedJob(null);
    setUsername("");
    setPassword("");
    setError("");
    window.sessionStorage.removeItem(AUTH_STORAGE_KEY);
  };

  if (!isLoggedIn) {
    return (
      <LoginPage
        username={username}
        password={password}
        error={error}
        isSubmitting={isSubmitting}
        onUsernameChange={setUsername}
        onPasswordChange={setPassword}
        onSubmit={handleLogin}
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
          setActiveTab("dashboard");
        }}
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
    />
  );
}
