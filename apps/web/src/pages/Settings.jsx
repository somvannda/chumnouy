import { useCallback, useEffect, useState } from "react";
import { api } from "../lib/api";
import { useAuth } from "../context/auth";
import { Alert, Button, Card, Field, Input, Select, Spinner } from "../components/ui";

const EMPTY_AI = { provider: "", model: "", base_url: "", api_key: "" };
const EMPTY_NOTIFYR = { notifyr_api_url: "", notifyr_api_key: "" };

export default function Settings() {
  const { token } = useAuth();
  const [settings, setSettings] = useState(null);
  const [ai, setAi] = useState(EMPTY_AI);
  const [notifyr, setNotifyr] = useState(EMPTY_NOTIFYR);
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
        })
        .catch((err) => setError(err.message)),
    [token],
  );

  useEffect(() => {
    load();
  }, [load]);

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
    </div>
  );
}
