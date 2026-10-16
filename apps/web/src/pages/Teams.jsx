import { useCallback, useEffect, useState } from "react";
import { Plus, Trash2, UserPlus, Users } from "lucide-react";
import { api } from "../lib/api";
import { useAuth } from "../context/auth";
import { Alert, Badge, Button, Card, EmptyState, Field, Input, Select, Spinner } from "../components/ui";
import { initials } from "../lib/format";

const TEAM_ROLES = ["member", "lead"];

export default function Teams() {
  const { token } = useAuth();
  const [teams, setTeams] = useState(null);
  const [members, setMembers] = useState([]);
  const [form, setForm] = useState({ name: "", description: "" });
  const [openId, setOpenId] = useState(null);
  const [pick, setPick] = useState({ user_id: "", role: "member" });
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setTeams(await api.listTeams(token));
      api.listMembers(token).then(setMembers).catch(() => setMembers([]));
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

  function create(event) {
    event.preventDefault();
    const body = { name: form.name.trim() };
    if (form.description.trim()) body.description = form.description.trim();
    return run(async () => {
      const created = await api.createTeam(token, body);
      setOpenId(created.id);
      setForm({ name: "", description: "" });
    }, "Team created.");
  }

  if (!teams) {
    return (
      <div className="flex justify-center py-20">
        {error ? <p className="text-sm font-semibold text-danger">{error}</p> : <Spinner />}
      </div>
    );
  }

  const byId = Object.fromEntries(members.map((member) => [member.user_id, member]));

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <h1 className="text-lg font-black text-ink">Teams</h1>
      <p className="text-sm text-ink-soft">
        Group agents so tickets can be routed to a team (routing, reports and assignment).
      </p>
      <Alert>{error}</Alert>
      {notice && <Alert tone="success">{notice}</Alert>}

      <Card>
        <h2 className="text-sm font-extrabold text-ink">New team</h2>
        <form onSubmit={create} className="mt-4 space-y-4">
          <Field label="Name">
            <Input
              required
              value={form.name}
              onChange={(event) => setForm({ ...form, name: event.target.value })}
              placeholder="Billing"
            />
          </Field>
          <Field label="Description" hint="Optional.">
            <Input
              value={form.description}
              onChange={(event) => setForm({ ...form, description: event.target.value })}
            />
          </Field>
          <Button type="submit" disabled={busy || !form.name.trim()}>
            <Plus size={16} /> Create team
          </Button>
        </form>
      </Card>

      {teams.length === 0 ? (
        <EmptyState icon={Users} title="No teams yet" />
      ) : (
        teams.map((team) => {
          const open = openId === team.id;
          const available = members.filter(
            (member) => !team.members.some((row) => row.user_id === member.user_id),
          );
          return (
            <Card key={team.id}>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <button
                  type="button"
                  className="min-w-0 text-left"
                  onClick={() => setOpenId(open ? null : team.id)}
                >
                  <h2 className="truncate text-sm font-extrabold text-ink">{team.name}</h2>
                  <p className="text-xs text-muted">
                    {team.slug} · {team.members.length} member{team.members.length === 1 ? "" : "s"}
                  </p>
                </button>
                <div className="flex items-center gap-2">
                  <Button type="button" variant="secondary" onClick={() => setOpenId(open ? null : team.id)}>
                    {open ? "Hide" : "Members"}
                  </Button>
                  <Button
                    type="button"
                    variant="secondary"
                    disabled={busy}
                    onClick={() => run(() => api.deleteTeam(token, team.id), "Team deleted.")}
                  >
                    <Trash2 size={16} />
                  </Button>
                </div>
              </div>

              {team.description && <p className="mt-2 text-sm text-ink-soft">{team.description}</p>}

              {open && (
                <div className="mt-4 space-y-3 border-t border-line pt-4">
                  {team.members.length === 0 ? (
                    <p className="text-sm text-muted">No members yet.</p>
                  ) : (
                    team.members.map((row) => (
                      <div key={row.user_id} className="flex items-center gap-3">
                        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-brand-soft text-xs font-black text-brand">
                          {initials(byId[row.user_id]?.name || byId[row.user_id]?.email || "?")}
                        </span>
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-bold text-ink">
                            {byId[row.user_id]?.name || byId[row.user_id]?.email || row.user_id}
                          </p>
                          <p className="truncate text-xs text-muted">{byId[row.user_id]?.email}</p>
                        </div>
                        <Badge tone={row.role === "lead" ? "brand" : "neutral"}>{row.role}</Badge>
                        <Button
                          type="button"
                          variant="secondary"
                          disabled={busy}
                          onClick={() =>
                            run(
                              () => api.removeTeamMember(token, team.id, row.user_id),
                              "Member removed.",
                            )
                          }
                        >
                          <Trash2 size={16} />
                        </Button>
                      </div>
                    ))
                  )}

                  <div className="flex flex-wrap items-end gap-2">
                    <Select
                      className="w-56"
                      value={pick.user_id}
                      disabled={busy || available.length === 0}
                      onChange={(event) => setPick({ ...pick, user_id: event.target.value })}
                    >
                      <option value="">
                        {available.length ? "Add a member…" : "Everyone is already in the team"}
                      </option>
                      {available.map((member) => (
                        <option key={member.user_id} value={member.user_id}>
                          {member.name || member.email}
                        </option>
                      ))}
                    </Select>
                    <Select
                      className="w-32"
                      value={pick.role}
                      disabled={busy}
                      onChange={(event) => setPick({ ...pick, role: event.target.value })}
                    >
                      {TEAM_ROLES.map((role) => (
                        <option key={role} value={role}>
                          {role}
                        </option>
                      ))}
                    </Select>
                    <Button
                      type="button"
                      disabled={busy || !pick.user_id}
                      onClick={() =>
                        run(async () => {
                          await api.addTeamMember(token, team.id, {
                            user_id: pick.user_id,
                            role: pick.role,
                          });
                          setPick({ user_id: "", role: "member" });
                        }, "Member added.")
                      }
                    >
                      <UserPlus size={16} /> Add
                    </Button>
                  </div>
                </div>
              )}
            </Card>
          );
        })
      )}
    </div>
  );
}
