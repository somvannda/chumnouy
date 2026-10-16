import { useCallback, useEffect, useState } from "react";
import { api } from "../lib/api";
import { useAuth } from "../context/auth";
import { Alert, Button, Card, Field, Input, Select, Spinner, Textarea } from "../components/ui";

const EMPTY_AI = { provider: "", model: "", base_url: "", api_key: "" };
const EMPTY_NOTIFYR = { notifyr_api_url: "", notifyr_api_key: "" };
const WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];
const PRIORITIES = ["low", "normal", "high", "urgent"];

export default function Settings() {
  const { token } = useAuth();
  const [settings, setSettings] = useState(null);
  const [ai, setAi] = useState(EMPTY_AI);
  const [notifyr, setNotifyr] = useState(EMPTY_NOTIFYR);
  const [sla, setSla] = useState(null);
  const [slaScope, setSlaScope] = useState("");
  const [teams, setTeams] = useState([]);
  const [sso, setSso] = useState(null);
  const [hours, setHours] = useState(null);
  const [branding, setBranding] = useState(null);
  const [allowlist, setAllowlist] = useState("");
  const [error, setError] = useState(null);
  const [saved, setSaved] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(
    () =>
      api
        .getSettings(token)
        .then((data) => {
          setSettings(data);
          setAi({
            provider: data.ai.provider || "",
            model: data.ai.model || "",
            base_url: data.ai.base_url || "",
            api_key: "",
          });
          setNotifyr({
            notifyr_api_url: data.notifications.notifyr_api_url || "",
            notifyr_api_key: "",
          });
          setSla({
            first_response_minutes: data.sla?.first_response_minutes || {},
            resolution_minutes: data.sla?.resolution_minutes || {},
            teams: data.sla?.teams || {},
          });
          setSso({
            enabled: data.sso?.enabled || false,
            issuer: data.sso?.issuer || "",
            client_id: data.sso?.client_id || "",
            client_secret: "",
            allowed_domains: (data.sso?.allowed_domains || []).join(", "),
            client_secret_set: data.sso?.client_secret_set || false,
          });
          const days = data.business_hours?.days || {};
          setHours({
            enabled: data.business_hours?.enabled || false,
            timezone: data.business_hours?.timezone || "UTC",
            days: Object.fromEntries(
              WEEKDAYS.map((day) => [day, days[day] || ["09:00", "17:00"]]),
            ),
          });
          setBranding({
            title: data.branding?.title || "Support",
            label: data.branding?.label || "Support",
            accent: data.branding?.accent || "#6957f5",
            position: data.branding?.position || "right",
            greeting: data.branding?.greeting || "",
            pre_chat: data.branding?.pre_chat || false,
          });
          setAllowlist((data.security?.ip_allowlist || []).join("\n"));
        })
        .catch((err) => setError(err.message)),
    [token],
  );

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    api.listTeams(token).then(setTeams).catch(() => setTeams([]));
  }, [token]);

  // Editing a team that has no override yet starts from the workspace policy.
  function selectSlaScope(scope) {
    setSlaScope(scope);
    if (!scope) return;
    setSla((prev) => {
      if (!prev || prev.teams[scope]) return prev;
      return {
        ...prev,
        teams: {
          ...prev.teams,
          [scope]: {
            first_response_minutes: { ...prev.first_response_minutes },
            resolution_minutes: { ...prev.resolution_minutes },
          },
        },
      };
    });
  }

  const emptyPolicy = { first_response_minutes: {}, resolution_minutes: {} };
  const slaValues = slaScope ? sla?.teams[slaScope] || emptyPolicy : sla || emptyPolicy;

  async function save(event, run, message) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setSaved(null);
    try {
      await run();
      setSaved(message);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  function saveAi(event) {
    const body = {
      provider: ai.provider || null,
      model: ai.model || null,
      base_url: ai.base_url || null,
    };
    if (ai.api_key) body.api_key = ai.api_key;
    return save(event, () => api.updateAISettings(token, body), "AI settings saved.");
  }

  function saveNotifyr(event) {
    const body = {
      notifyr_api_url: notifyr.notifyr_api_url || null,
    };
    if (notifyr.notifyr_api_key) body.notifyr_api_key = notifyr.notifyr_api_key;
    return save(event, () => api.updateNotificationSettings(token, body), "Notification settings saved.");
  }

  function saveSla(event) {
    const minutes = (values) =>
      Object.fromEntries(
        Object.entries(values || {}).map(([key, value]) => [key, Math.max(0, Number(value) || 0)]),
      );
    const teamPolicies = Object.fromEntries(
      Object.entries(sla.teams || {}).map(([teamId, policy]) => [
        teamId,
        {
          first_response_minutes: minutes(policy.first_response_minutes),
          resolution_minutes: minutes(policy.resolution_minutes),
        },
      ]),
    );
    return save(
      event,
      () =>
        api.updateSlaSettings(token, {
          first_response_minutes: minutes(sla.first_response_minutes),
          resolution_minutes: minutes(sla.resolution_minutes),
          teams: teamPolicies,
        }),
      "SLA settings saved.",
    );
  }

  function saveSso(event) {
    const body = {
      enabled: sso.enabled,
      issuer: sso.issuer || null,
      client_id: sso.client_id || null,
      allowed_domains: sso.allowed_domains
        .split(",")
        .map((domain) => domain.trim())
        .filter(Boolean),
    };
    if (sso.client_secret) body.client_secret = sso.client_secret;
    return save(event, () => api.updateSsoSettings(token, body), "SSO settings saved.");
  }

  function saveHours(event) {
    return save(
      event,
      () =>
        api.updateBusinessHours(token, {
          enabled: hours.enabled,
          timezone: hours.timezone || "UTC",
          days: hours.days,
        }),
      "Business hours saved.",
    );
  }

  function saveBranding(event) {
    return save(
      event,
      () =>
        api.updateBranding(token, {
          title: branding.title || null,
          label: branding.label || null,
          accent: branding.accent || null,
          position: branding.position,
          greeting: branding.greeting || null,
          pre_chat: branding.pre_chat,
        }),
      "Widget branding saved.",
    );
  }

  function saveSecurity(event) {
    const entries = allowlist
      .split(/[\n,]/)
      .map((entry) => entry.trim())
      .filter(Boolean);
    return save(
      event,
      () => api.updateSecuritySettings(token, { ip_allowlist: entries }),
      "Sign-in access saved.",
    );
  }

  if (!settings) {
    return (
      <div className="flex justify-center py-20">
        {error ? <p className="text-sm font-semibold text-danger">{error}</p> : <Spinner />}
      </div>
    );
  }

  const keyPlaceholder = settings.ai.api_key_set ? "•••••••• configured" : "sk-…";

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <h1 className="text-lg font-black text-ink">Settings</h1>
      <Alert className="">{error}</Alert>
      {saved && <Alert tone="success">{saved}</Alert>}

      <Card>
        <h2 className="text-sm font-extrabold text-ink">AI assistant</h2>
        <p className="mt-1 text-sm text-ink-soft">
          Bring your own provider key. It powers grounded answers in the console.
        </p>
        <form onSubmit={saveAi} className="mt-4 space-y-4">
          <Field label="Provider">
            <Select value={ai.provider} onChange={(e) => setAi({ ...ai, provider: e.target.value })}>
              <option value="">— none —</option>
              {settings.ai.providers.map((provider) => (
                <option key={provider.code} value={provider.code}>
                  {provider.label}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Model" hint="Optional — the provider default is used when blank.">
            <Input value={ai.model} onChange={(e) => setAi({ ...ai, model: e.target.value })} placeholder="gpt-4o-mini" />
          </Field>
          <Field label="Base URL" hint="Optional — override the provider's API host.">
            <Input value={ai.base_url} onChange={(e) => setAi({ ...ai, base_url: e.target.value })} placeholder="https://api.openai.com/v1" />
          </Field>
          <Field label="API key" hint="Write-only. Leave blank to keep the current key.">
            <Input
              type="password"
              value={ai.api_key}
              onChange={(e) => setAi({ ...ai, api_key: e.target.value })}
              placeholder={keyPlaceholder}
              autoComplete="off"
            />
          </Field>
          <Button type="submit" disabled={busy}>
            Save AI settings
          </Button>
        </form>
      </Card>

      <Card>
        <h2 className="text-sm font-extrabold text-ink">Notifications</h2>
        <p className="mt-1 text-sm text-ink-soft">
          Where ticket events are handed off for human-facing delivery. Leave blank to use the platform default.
        </p>
        <form onSubmit={saveNotifyr} className="mt-4 space-y-4">
          <Field label="Notifyr API URL">
            <Input
              value={notifyr.notifyr_api_url}
              onChange={(e) => setNotifyr({ ...notifyr, notifyr_api_url: e.target.value })}
              placeholder="https://notifyr.example.com"
            />
          </Field>
          <Field label="Notifyr API key" hint="Write-only. Leave blank to keep the current key.">
            <Input
              type="password"
              value={notifyr.notifyr_api_key}
              onChange={(e) => setNotifyr({ ...notifyr, notifyr_api_key: e.target.value })}
              placeholder={settings.notifications.notifyr_api_key_set ? "•••••••• configured" : "nkey_…"}
              autoComplete="off"
            />
          </Field>
          <Button type="submit" disabled={busy}>
            Save notification settings
          </Button>
        </form>
      </Card>

      <Card>
        <h2 className="text-sm font-extrabold text-ink">SLA targets</h2>
        <p className="mt-1 text-sm text-ink-soft">
          Minutes by priority; 0 disables the target. A team policy overrides the workspace one, and
          a ticket&apos;s targets follow its team.
        </p>
        <form onSubmit={saveSla} className="mt-4 space-y-4">
          <Field label="Applies to">
            <Select value={slaScope} onChange={(event) => selectSlaScope(event.target.value)}>
              <option value="">Workspace default</option>
              {teams.map((team) => (
                <option key={team.id} value={team.id}>
                  Team: {team.name}
                </option>
              ))}
            </Select>
          </Field>
          {["first_response_minutes", "resolution_minutes"].map((key) => (
            <div key={key}>
              <p className="mb-1.5 text-xs font-bold uppercase tracking-[.08em] text-ink-soft">
                {key === "first_response_minutes" ? "First response" : "Resolution"}
              </p>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                {PRIORITIES.map((priority) => (
                  <label key={priority} className="text-xs font-bold capitalize text-muted">
                    {priority}
                    <Input
                      className="mt-1"
                      inputMode="numeric"
                      value={slaValues[key]?.[priority] ?? ""}
                      onChange={(event) =>
                        setSla((prev) =>
                          slaScope
                            ? {
                                ...prev,
                                teams: {
                                  ...prev.teams,
                                  [slaScope]: {
                                    ...prev.teams[slaScope],
                                    [key]: {
                                      ...prev.teams[slaScope]?.[key],
                                      [priority]: event.target.value,
                                    },
                                  },
                                },
                              }
                            : { ...prev, [key]: { ...prev[key], [priority]: event.target.value } },
                        )
                      }
                    />
                  </label>
                ))}
              </div>
            </div>
          ))}
          <Button type="submit" disabled={busy || !sla}>
            Save SLA settings
          </Button>
        </form>
      </Card>

      <Card>
        <h2 className="text-sm font-extrabold text-ink">Single sign-on (OIDC)</h2>
        <p className="mt-1 text-sm text-ink-soft">
          Let your team sign in through an identity provider.
        </p>
        <form onSubmit={saveSso} className="mt-4 space-y-4">
          <label className="flex items-center gap-2 text-sm font-bold text-ink-soft">
            <input
              type="checkbox"
              checked={sso?.enabled || false}
              onChange={(event) => setSso({ ...sso, enabled: event.target.checked })}
            />
            Enabled
          </label>
          <Field label="Issuer">
            <Input
              value={sso?.issuer || ""}
              onChange={(event) => setSso({ ...sso, issuer: event.target.value })}
              placeholder="https://idp.example.com"
            />
          </Field>
          <Field label="Client ID">
            <Input
              value={sso?.client_id || ""}
              onChange={(event) => setSso({ ...sso, client_id: event.target.value })}
            />
          </Field>
          <Field label="Client secret" hint="Write-only. Leave blank to keep the current secret.">
            <Input
              type="password"
              autoComplete="off"
              value={sso?.client_secret || ""}
              onChange={(event) => setSso({ ...sso, client_secret: event.target.value })}
              placeholder={sso?.client_secret_set ? "•••••••• configured" : ""}
            />
          </Field>
          <Field label="Allowed email domains" hint="Comma-separated; blank allows any.">
            <Input
              value={sso?.allowed_domains || ""}
              onChange={(event) => setSso({ ...sso, allowed_domains: event.target.value })}
              placeholder="example.com"
            />
          </Field>
          <Button type="submit" disabled={busy || !sso}>
            Save SSO settings
          </Button>
        </form>
      </Card>

      <Card>
        <h2 className="text-sm font-extrabold text-ink">Business hours</h2>
        <p className="mt-1 text-sm text-ink-soft">SLA due dates are computed over these hours.</p>
        <form onSubmit={saveHours} className="mt-4 space-y-4">
          <label className="flex items-center gap-2 text-sm font-bold text-ink-soft">
            <input
              type="checkbox"
              checked={hours?.enabled || false}
              onChange={(event) => setHours({ ...hours, enabled: event.target.checked })}
            />
            Enabled
          </label>
          <Field label="Timezone">
            <Input
              value={hours?.timezone || ""}
              onChange={(event) => setHours({ ...hours, timezone: event.target.value })}
              placeholder="Asia/Phnom_Penh"
            />
          </Field>
          <div className="space-y-2">
            {WEEKDAYS.map((day) => (
              <div key={day} className="flex items-center gap-3">
                <span className="w-10 text-xs font-bold uppercase text-muted">{day}</span>
                <Input
                  type="time"
                  className="w-32"
                  value={hours?.days?.[day]?.[0] || ""}
                  onChange={(event) =>
                    setHours({
                      ...hours,
                      days: { ...hours.days, [day]: [event.target.value, hours.days[day][1]] },
                    })
                  }
                />
                <Input
                  type="time"
                  className="w-32"
                  value={hours?.days?.[day]?.[1] || ""}
                  onChange={(event) =>
                    setHours({
                      ...hours,
                      days: { ...hours.days, [day]: [hours.days[day][0], event.target.value] },
                    })
                  }
                />
              </div>
            ))}
          </div>
          <Button type="submit" disabled={busy || !hours}>
            Save business hours
          </Button>
        </form>
      </Card>

      <Card>
        <h2 className="text-sm font-extrabold text-ink">Widget branding</h2>
        <p className="mt-1 text-sm text-ink-soft">
          The embeddable widget reads these from <code>/v1/public/branding</code>.
        </p>
        <form onSubmit={saveBranding} className="mt-4 space-y-4">
          <Field label="Panel title">
            <Input
              value={branding?.title || ""}
              onChange={(event) => setBranding({ ...branding, title: event.target.value })}
            />
          </Field>
          <Field label="Launcher label">
            <Input
              value={branding?.label || ""}
              onChange={(event) => setBranding({ ...branding, label: event.target.value })}
            />
          </Field>
          <Field label="Accent colour" hint="Hex, e.g. #0ea5e9. Invalid values fall back to the default.">
            <Input
              value={branding?.accent || ""}
              onChange={(event) => setBranding({ ...branding, accent: event.target.value })}
            />
          </Field>
          <Field label="Position">
            <Select
              value={branding?.position || "right"}
              onChange={(event) => setBranding({ ...branding, position: event.target.value })}
            >
              <option value="right">Right</option>
              <option value="left">Left</option>
            </Select>
          </Field>
          <Field label="Greeting" hint="Shown at the top of the widget and before a chat starts.">
            <Input
              value={branding?.greeting || ""}
              onChange={(event) => setBranding({ ...branding, greeting: event.target.value })}
            />
          </Field>
          <label className="flex items-center gap-2 text-sm font-bold text-ink-soft">
            <input
              type="checkbox"
              checked={branding?.pre_chat || false}
              onChange={(event) => setBranding({ ...branding, pre_chat: event.target.checked })}
            />
            Ask for a message before starting a chat
          </label>
          <Button type="submit" disabled={busy || !branding}>
            Save widget branding
          </Button>
        </form>
      </Card>

      <Card>
        <h2 className="text-sm font-extrabold text-ink">Sign-in access</h2>
        <p className="mt-1 text-sm text-ink-soft">
          Restrict console sign-in to a set of networks. One IP or CIDR block per line; leave empty
          to allow any address. The client address comes from <code>X-Forwarded-For</code> when a
          proxy sets it, so only enable this behind a trusted proxy.
        </p>
        <form onSubmit={saveSecurity} className="mt-4 space-y-4">
          <Field label="Allowed IPs / CIDR blocks">
            <Textarea
              rows={3}
              value={allowlist}
              onChange={(event) => setAllowlist(event.target.value)}
              placeholder={"10.0.0.0/8\n192.168.1.5"}
            />
          </Field>
          <Button type="submit" disabled={busy}>
            Save sign-in access
          </Button>
        </form>
      </Card>
    </div>
  );
}
