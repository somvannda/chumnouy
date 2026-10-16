import { useCallback, useEffect, useState } from "react";
import { Copy, Trash2, UserPlus, Users } from "lucide-react";
import { api } from "../lib/api";
import { useAuth } from "../context/auth";
import { Alert, Badge, Button, Card, EmptyState, Field, Input, Select, Spinner } from "../components/ui";
import { formatRelativeTime, initials } from "../lib/format";

const ROLES = ["admin", "team_lead", "agent", "viewer"];

export default function Members() {
  const { token, user } = useAuth();
  const [members, setMembers] = useState(null);
  const [invites, setInvites] = useState([]);
  const [form, setForm] = useState({ email: "", name: "", role: "agent" });
  const [link, setLink] = useState(null);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setMembers(await api.listMembers(token));
      try {
        setInvites(await api.listInvites(token));
      } catch {
        // Reading pending invitations needs members:manage; the roster is enough.
        setInvites([]);
      }
    } catch (err) {
      setError(err.message);
    }
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  async function run(action, message) {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await action();
      if (message) setNotice(message);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  function invite(event) {
    event.preventDefault();
    const body = { email: form.email.trim(), role: form.role };
    if (form.name.trim()) body.name = form.name.trim();
    return run(async () => {
      const created = await api.inviteMember(token, body);
      setLink(
        created.token
          ? { email: created.email, url: `${window.location.origin}/invite/${created.token}` }
          : null,
      );
      setNotice(
        created.token
          ? "Invitation created — copy the link below."
          : `${created.email} was added to the workspace.`,
      );
      setForm({ email: "", name: "", role: "agent" });
    });
  }

  if (!members) {
    return (
      <div className="flex justify-center py-20">
        {error ? <p className="text-sm font-semibold text-danger">{error}</p> : <Spinner />}
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <h1 className="text-lg font-black text-ink">Members</h1>
      <Alert>{error}</Alert>
      {notice && <Alert tone="success">{notice}</Alert>}

      {link && (
        <Card className="border-brand/40">
          <h2 className="text-sm font-extrabold text-ink">Invitation link for {link.email}</h2>
          <p className="mt-1 text-sm text-ink-soft">
            Shown once. Delivery is Notifyr&apos;s job — copy it to the invitee (or wire it to a
            notification).
          </p>
          <div className="mt-3 flex items-center gap-2">
            <code className="min-w-0 flex-1 truncate rounded-lg bg-surface-muted px-3 py-2 text-xs text-ink">
              {link.url}
            </code>
            <Button
              type="button"
              variant="secondary"
              onClick={() => navigator.clipboard?.writeText(link.url)}
            >
              <Copy size={16} /> Copy
            </Button>
          </div>
        </Card>
      )}

      <Card>
        <h2 className="text-sm font-extrabold text-ink">Invite a teammate</h2>
        <form onSubmit={invite} className="mt-4 space-y-4">
          <Field label="Email">
            <Input
              type="email"
              required
              value={form.email}
              onChange={(event) => setForm({ ...form, email: event.target.value })}
              placeholder="teammate@example.com"
            />
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Name" hint="Optional; used when creating the account.">
              <Input
                value={form.name}
                onChange={(event) => setForm({ ...form, name: event.target.value })}
              />
            </Field>
            <Field label="Role">
              <Select
                value={form.role}
                onChange={(event) => setForm({ ...form, role: event.target.value })}
              >
                {ROLES.map((role) => (
                  <option key={role} value={role}>
                    {role.replace("_", " ")}
                  </option>
                ))}
              </Select>
            </Field>
          </div>
          <Button type="submit" disabled={busy || !form.email.trim()}>
            <UserPlus size={16} /> Send invitation
          </Button>
        </form>
      </Card>

      {invites.length > 0 && (
        <Card>
          <h2 className="text-sm font-extrabold text-ink">Pending invitations</h2>
          <div className="mt-3 divide-y divide-line">
            {invites.map((invite) => (
              <div key={invite.id} className="flex items-center justify-between gap-3 py-2.5">
                <div className="min-w-0">
                  <p className="truncate text-sm font-bold text-ink">{invite.email}</p>
                  <p className="text-xs text-muted">
                    {invite.role.replace("_", " ")} · expires {formatRelativeTime(invite.expires_at)}
                  </p>
                </div>
                <Button
                  type="button"
                  variant="secondary"
                  disabled={busy}
                  onClick={() => run(() => api.revokeInvite(token, invite.id), "Invitation revoked.")}
                >
                  <Trash2 size={16} /> Revoke
                </Button>
              </div>
            ))}
          </div>
        </Card>
      )}

      <Card>
        <h2 className="text-sm font-extrabold text-ink">Roster</h2>
        {members.length === 0 ? (
          <EmptyState icon={Users} title="No members yet" />
        ) : (
          <div className="mt-3 divide-y divide-line">
            {members.map((member) => (
              <div key={member.user_id} className="flex items-center gap-3 py-3">
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-brand-soft text-xs font-black text-brand">
                  {initials(member.name || member.email)}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-bold text-ink">
                    {member.name || member.email}
                    {member.user_id === user?.id && <span className="ml-2 text-xs text-muted">you</span>}
                  </p>
                  <p className="truncate text-xs text-muted">{member.email}</p>
                </div>
                {member.role === "owner" ? (
                  <Badge tone="brand">owner</Badge>
                ) : (
                  <Select
                    className="w-32"
                    value={member.role}
                    disabled={busy}
                    onChange={(event) =>
                      run(
                        () => api.updateMemberRole(token, member.user_id, { role: event.target.value }),
                        "Role updated.",
                      )
                    }
                  >
                    {ROLES.map((role) => (
                      <option key={role} value={role}>
                        {role.replace("_", " ")}
                      </option>
                    ))}
                  </Select>
                )}
                {member.role !== "owner" && (
                  <Button
                    type="button"
                    variant="secondary"
                    disabled={busy}
                    onClick={() => run(() => api.removeMember(token, member.user_id), "Member removed.")}
                  >
                    <Trash2 size={16} />
                  </Button>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
