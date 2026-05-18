import React from "react";
import { Dumbbell, Lock, Sparkles } from "lucide-react";
import { PRIMARY_BORDER, THEME } from "../theme";

type LoginPageProps = {
  email: string;
  password: string;
  firstName: string;
  lastName: string;
  authMode: "signin" | "signup";
  error: string;
  isSubmitting: boolean;
  onEmailChange: (value: string) => void;
  onPasswordChange: (value: string) => void;
  onFirstNameChange: (value: string) => void;
  onLastNameChange: (value: string) => void;
  onModeChange: (mode: "signin" | "signup") => void;
  onSubmit: (e: React.FormEvent<HTMLFormElement>) => void;
};

export default function LoginPage({
  email,
  password,
  firstName,
  lastName,
  authMode,
  error,
  isSubmitting,
  onEmailChange,
  onPasswordChange,
  onFirstNameChange,
  onLastNameChange,
  onModeChange,
  onSubmit,
}: LoginPageProps) {
  const isSignup = authMode === "signup";

  return (
    <div style={styles.page}>
      <div style={styles.card}>
        <div style={styles.logoMark}><Dumbbell size={24} /></div>
        <h1 style={styles.title}>Vectra</h1>
        <p style={styles.subtitle}>Fitness Coach Client Management</p>

        <div style={styles.modeRow}>
          <button
            type="button"
            style={isSignup ? styles.modeButton : styles.modeButtonActive}
            onClick={() => onModeChange("signin")}
          >
            Sign in
          </button>
          <button
            type="button"
            style={isSignup ? styles.modeButtonActive : styles.modeButton}
            onClick={() => onModeChange("signup")}
          >
            Sign up
          </button>
        </div>

        <form onSubmit={onSubmit} style={styles.form}>
          {isSignup ? (
            <>
              <input
                value={firstName}
                onChange={(e) => onFirstNameChange(e.target.value)}
                placeholder="First name"
                style={styles.input}
              />
              <input
                value={lastName}
                onChange={(e) => onLastNameChange(e.target.value)}
                placeholder="Last name"
                style={styles.input}
              />
            </>
          ) : null}

          <input
            value={email}
            onChange={(e) => onEmailChange(e.target.value)}
            placeholder="Email"
            style={styles.input}
          />

          <input
            type="password"
            value={password}
            onChange={(e) => onPasswordChange(e.target.value)}
            placeholder="Password"
            style={styles.input}
          />

          {error ? <div style={styles.error}>{error}</div> : null}

          <button type="submit" style={styles.button} disabled={isSubmitting}>
            {isSignup ? <Sparkles size={16} /> : <Lock size={16} />}
            {isSubmitting
              ? isSignup
                ? "Creating account..."
                : "Signing in..."
              : isSignup
                ? "Create coach account"
                : "Sign in"}
          </button>
        </form>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: {
    minHeight: "100vh",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    background: THEME.gradients.app,
  },
  card: {
    width: "100%",
    maxWidth: "440px",
    backgroundColor: "rgba(255,255,255,0.9)",
    padding: "32px",
    borderRadius: THEME.radii.panel,
    boxShadow: THEME.shadows.cardHover,
    border: `1px solid ${THEME.colors.border}`,
  },
  logoMark: {
    width: "52px",
    height: "52px",
    borderRadius: THEME.radii.lg,
    background: THEME.gradients.primary,
    color: THEME.colors.white,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: "18px",
    boxShadow: `0 14px 26px ${THEME.shadows.primarySoft}`,
  },
  title: {
    margin: 0,
    fontSize: "28px",
    fontWeight: 700,
    color: THEME.colors.ink,
  },
  subtitle: {
    marginTop: "8px",
    marginBottom: "24px",
    color: "#64748b",
  },
  modeRow: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gap: "10px",
    marginBottom: "16px",
  },
  modeButton: {
    padding: "10px 14px",
    borderRadius: "10px",
    border: "1px solid #cbd5e1",
    backgroundColor: "rgba(255,255,255,0.72)",
    cursor: "pointer",
  },
  modeButtonActive: {
    padding: "10px 14px",
    borderRadius: "10px",
    border: PRIMARY_BORDER,
    backgroundColor: THEME.colors.indigo,
    color: THEME.colors.white,
    cursor: "pointer",
  },
  form: {
    display: "flex",
    flexDirection: "column",
    gap: "12px",
  },
  input: {
    padding: "12px 14px",
    borderRadius: "10px",
    border: `1px solid ${THEME.colors.borderStrong}`,
    fontSize: "14px",
  },
  error: {
    color: "#dc2626",
    fontSize: "14px",
  },
  button: {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    gap: "8px",
    padding: "12px 14px",
    borderRadius: "10px",
    border: "none",
    backgroundColor: THEME.colors.indigo,
    color: THEME.colors.white,
    fontSize: "14px",
    cursor: "pointer",
    fontWeight: 700,
    boxShadow: `0 12px 24px ${THEME.shadows.primarySoft}`,
  },
};
