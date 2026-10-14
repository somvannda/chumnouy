import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../context/auth";
import { Alert, Button, Field, Input } from "../components/ui";
import AuthShell from "../components/AuthShell";

export default function Signup() {
  const { signup, token } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: "", email: "", password: "", workspace_name: "" });
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  if (token) return <Navigate to="/inbox" replace />;

  function update(key) {
    return (event) => setForm((prev) => ({ ...prev, [key]: event.target.value }));
  }

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await signup({
        name: form.name,
        email: form.email,
        password: form.password,
        workspace_name: form.workspace_name || undefined,
      });
      navigate("/inbox", { replace: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell
      title="Create your workspace"
      subtitle="Sign up once, then take an API key for your product."
      footer={
        <>
          Already have an account?{" "}
          <Link to="/login" className="font-bold text-brand hover:underline">
            Sign in
          </Link>
        </>
      }
    >
      <form onSubmit={submit} className="space-y-4">
        <Alert>{error}</Alert>
        <Field label="Your name">
          <Input required value={form.name} onChange={update("name")} placeholder="Sok Dara" />
        </Field>
        <Field label="Work email">
          <Input
            type="email"
            autoComplete="email"
            required
            value={form.email}
            onChange={update("email")}
            placeholder="you@example.com"
          />
        </Field>
        <Field label="Password" hint="At least 8 characters.">
          <Input
            type="password"
            autoComplete="new-password"
            required
            minLength={8}
            value={form.password}
            onChange={update("password")}
            placeholder="••••••••"
          />
        </Field>
        <Field label="Workspace name" hint="Optional — defaults to your name.">
          <Input value={form.workspace_name} onChange={update("workspace_name")} placeholder="Acme Support" />
        </Field>
        <Button type="submit" disabled={busy} className="w-full">
          {busy ? "Creating…" : "Create workspace"}
        </Button>
      </form>
    </AuthShell>
  );
}
