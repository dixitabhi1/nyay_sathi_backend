import { FormEvent, useState } from "react";

import { useAuth } from "../lib/auth-context";

type Mode = "login" | "register";

export function AccountPanel() {
  const { user, loading, isAuthenticated, login, logout, register } = useAuth();
  const [mode, setMode] = useState<Mode>("login");
  const [error, setError] = useState<string | null>(null);
  const [loginForm, setLoginForm] = useState({ email: "", password: "" });
  const [registerForm, setRegisterForm] = useState({
    full_name: "",
    email: "",
    password: "",
    role: "citizen",
    professional_id: "",
    organization: "",
    city: "",
    preferred_language: "en",
  });

  async function handleLogin(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      await login(loginForm);
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Unable to log in.");
    }
  }

  async function handleRegister(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      await register(registerForm);
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Unable to register.");
    }
  }

  if (isAuthenticated && user) {
    return (
      <section className="utility-card account-card">
        <p className="section-kicker">Account</p>
        <h3>{user.full_name}</h3>
        <p>{user.email}</p>
        <div className="account-status-grid">
          <span className="mini-pill">{user.role}</span>
          <span className={`mini-pill ${user.approval_status === "approved" ? "approved" : "pending"}`}>
            {user.approval_status}
          </span>
        </div>
        <p className="helper-text">
          Requested role: <strong>{user.requested_role}</strong>
        </p>
        {user.approval_status !== "approved" && (
          <p className="helper-text">
            {user.approval_notes ?? "Professional access is pending approval. Citizen features remain available meanwhile."}
          </p>
        )}
        <div className="account-status-grid">
          <span className={user.can_access_lawyer_dashboard ? "status-pill" : "status-pill muted"}>
            Lawyer dashboard {user.can_access_lawyer_dashboard ? "enabled" : "locked"}
          </span>
          <span className={user.can_access_police_dashboard ? "status-pill" : "status-pill muted"}>
            Police dashboard {user.can_access_police_dashboard ? "enabled" : "locked"}
          </span>
        </div>
        <button className="ghost-button" type="button" onClick={() => void logout()} disabled={loading}>
          Logout
        </button>
      </section>
    );
  }

  return (
    <section className="utility-card account-card">
      <div className="card-header-inline">
        <div>
          <p className="section-kicker">Account Access</p>
          <h3>Sign in or create an account</h3>
        </div>
        <div className="mini-toggle">
          <button type="button" className={mode === "login" ? "active" : ""} onClick={() => setMode("login")}>
            Login
          </button>
          <button type="button" className={mode === "register" ? "active" : ""} onClick={() => setMode("register")}>
            Register
          </button>
        </div>
      </div>

      {mode === "login" ? (
        <form className="fir-form compact-form" onSubmit={handleLogin}>
          <label>
            Email
            <input value={loginForm.email} onChange={(event) => setLoginForm({ ...loginForm, email: event.target.value })} />
          </label>
          <label>
            Password
            <input
              type="password"
              value={loginForm.password}
              onChange={(event) => setLoginForm({ ...loginForm, password: event.target.value })}
            />
          </label>
          <button className="submit-button" type="submit" disabled={loading}>
            Login
          </button>
        </form>
      ) : (
        <form className="fir-form compact-form" onSubmit={handleRegister}>
          <label>
            Full Name
            <input value={registerForm.full_name} onChange={(event) => setRegisterForm({ ...registerForm, full_name: event.target.value })} />
          </label>
          <label>
            Email
            <input value={registerForm.email} onChange={(event) => setRegisterForm({ ...registerForm, email: event.target.value })} />
          </label>
          <label>
            Password
            <input
              type="password"
              value={registerForm.password}
              onChange={(event) => setRegisterForm({ ...registerForm, password: event.target.value })}
            />
          </label>
          <label>
            Role
            <select value={registerForm.role} onChange={(event) => setRegisterForm({ ...registerForm, role: event.target.value })}>
              <option value="citizen">Citizen</option>
              <option value="lawyer">Lawyer</option>
              <option value="police">Police Officer</option>
            </select>
          </label>
          <label>
            Professional ID
            <input
              placeholder="Bar Council ID or badge number"
              value={registerForm.professional_id}
              onChange={(event) => setRegisterForm({ ...registerForm, professional_id: event.target.value })}
            />
          </label>
          <label>
            Organization / Court / Station
            <input
              value={registerForm.organization}
              onChange={(event) => setRegisterForm({ ...registerForm, organization: event.target.value })}
            />
          </label>
          <div className="two-up">
            <label>
              City
              <input value={registerForm.city} onChange={(event) => setRegisterForm({ ...registerForm, city: event.target.value })} />
            </label>
            <label>
              Language
              <select
                value={registerForm.preferred_language}
                onChange={(event) => setRegisterForm({ ...registerForm, preferred_language: event.target.value })}
              >
                <option value="en">English</option>
                <option value="hi">Hindi</option>
              </select>
            </label>
          </div>
          <p className="helper-text">Lawyer and police accounts remain pending until approved. Citizen accounts activate immediately.</p>
          <button className="submit-button" type="submit" disabled={loading}>
            Create Account
          </button>
        </form>
      )}

      {error && <div className="error-banner">{error}</div>}
    </section>
  );
}
