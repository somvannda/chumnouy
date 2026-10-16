import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useAuth } from "../context/auth";
import { Alert, Button, Card, Field, Input } from "../components/ui";

export default function Invite() {
  const { token } = useParams();
  const navigate = useNavigate();
  const { acceptInvite } = useAuth();
  const [form, setForm] = useState({ name: "", password: "" });
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await acceptInvite({
        token,
        password: form.password,
        name: form.name.trim() || null,
      });
      navigate("/inbox", { replace: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-md items-center px-4">
      <Card className="w-full">
        <h1 className="text-lg font-black text-ink">Join the workspace</h1>
        <p className="mt-1 text-sm text-ink-soft">
          Set a password to accept your invitation. If you already have an account, your existing
          password still works.
        </p>
        <form onSubmit={submit} className="mt-5 space-y-4">
          <Alert>{error}</Alert>
          <Field label="Your name" hint="Optional.">
            <Input
              value={form.name}
              onChange={(event) => setForm({ ...form, name: event.target.value })}
              placeholder="Sok Dara"
            />
          </Field>
          <Field label="Password" hint="At least 8 characters.">
            <Input
              type="password"
              required
              minLength={8}
              autoComplete="new-password"
              value={form.password}
              onChange={(event) => setForm({ ...form, password: event.target.value })}
            />
          </Field>
          <Button type="submit" className="w-full" disabled={busy || form.password.length < 8}>
            Accept invitation
          </Button>
        </form>
        <p className="mt-4 text-center text-xs text-muted">
          Already a member? <Link className="font-bold text-brand" to="/login">Sign in</Link>
        </p>
      </Card>
    </div>
  );
}
