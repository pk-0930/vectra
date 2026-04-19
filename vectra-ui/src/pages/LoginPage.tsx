import React from "react";

type LoginPageProps = {
  username: string;
  password: string;
  error: string;
  isSubmitting: boolean;
  onUsernameChange: (value: string) => void;
  onPasswordChange: (value: string) => void;
  onSubmit: (e: React.FormEvent<HTMLFormElement>) => void;
};

export default function LoginPage({
  username,
  password,
  error,
  isSubmitting,
  onUsernameChange,
  onPasswordChange,
  onSubmit,
}: LoginPageProps) {
  return (
    <div style={styles.page}>
      <div style={styles.card}>
        <h1 style={styles.title}>Vectra</h1>
        <p style={styles.subtitle}>Trainer Demo Login</p>

        <form onSubmit={onSubmit} style={styles.form}>
          <input
            value={username}
            onChange={(e) => onUsernameChange(e.target.value)}
            placeholder="Username"
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
            {isSubmitting ? "Signing in..." : "Login"}
          </button>
        </form>

        <div style={styles.demoText}>Demo: admin / admin</div>
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
    backgroundColor: "#f1f5f9",
  },
  card: {
    width: "100%",
    maxWidth: "420px",
    backgroundColor: "#ffffff",
    padding: "32px",
    borderRadius: "20px",
    boxShadow: "0 4px 16px rgba(0,0,0,0.08)",
    border: "1px solid #e2e8f0",
  },
  title: {
    margin: 0,
    fontSize: "28px",
    fontWeight: 700,
  },
  subtitle: {
    marginTop: "8px",
    marginBottom: "24px",
    color: "#64748b",
  },
  form: {
    display: "flex",
    flexDirection: "column",
    gap: "12px",
  },
  input: {
    padding: "12px 14px",
    borderRadius: "10px",
    border: "1px solid #cbd5e1",
    fontSize: "14px",
  },
  error: {
    color: "#dc2626",
    fontSize: "14px",
  },
  button: {
    padding: "12px 14px",
    borderRadius: "10px",
    border: "none",
    backgroundColor: "#0f172a",
    color: "#ffffff",
    fontSize: "14px",
    cursor: "pointer",
  },
  demoText: {
    marginTop: "16px",
    fontSize: "14px",
    color: "#64748b",
  },
};
