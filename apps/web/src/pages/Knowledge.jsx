import { useCallback, useEffect, useState } from "react";
import { BookOpen, Plus, RotateCcw } from "lucide-react";
import { api } from "../lib/api";
import { useAuth } from "../context/auth";
import {
  Alert,
  Badge,
  Button,
  Card,
  EmptyState,
  Field,
  Input,
  Select,
  Spinner,
  Textarea,
} from "../components/ui";

const LOCALES = ["en", "km"];
const EMPTY = {
  id: null,
  title: "",
  section: "general",
  locale: "en",
  summary: "",
  body: "",
};

export default function Knowledge() {
  const { token } = useAuth();
  const [articles, setArticles] = useState(null);
  const [error, setError] = useState(null);
  const [saved, setSaved] = useState(null);
  const [busy, setBusy] = useState(false);
  const [q, setQ] = useState("");
  const [locale, setLocale] = useState("");
  const [active, setActive] = useState("true");
  const [form, setForm] = useState(EMPTY);

  const load = useCallback(() => {
    const params = {};
    if (q) params.q = q;
    if (locale) params.locale = locale;
    if (active) params.active = active;
    return api
      .listKnowledge(token, params)
      .then(setArticles)
      .catch((err) => setError(err.message));
  }, [token, q, locale, active]);

  useEffect(() => {
    load();
  }, [load]);

  function select(article) {
    setSaved(null);
    setForm({
      id: article.id,
      title: article.title,
      section: article.section,
      locale: article.locale,
      summary: article.summary || "",
      body: article.body,
    });
  }

  function newArticle() {
    setSaved(null);
    setForm(EMPTY);
  }

  async function save(event) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setSaved(null);
    const body = {
      title: form.title.trim(),
      section: form.section.trim() || "general",
      locale: form.locale,
      summary: form.summary || null,
      body: form.body,
    };
    try {
      if (form.id) await api.updateKnowledgeArticle(token, form.id, body);
      else await api.createKnowledgeArticle(token, body);
      setSaved(form.id ? "Article saved." : "Article created.");
      if (!form.id) setForm(EMPTY);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function toggleActive(article) {
    setBusy(true);
    setError(null);
    try {
      if (article.is_active) await api.updateKnowledgeArticle(token, article.id, { is_active: false });
      else await api.restoreKnowledgeArticle(token, article.id);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-5xl">
      <h1 className="text-lg font-black text-ink">Knowledge base</h1>
      <p className="mt-1 text-sm text-ink-soft">
        The help corpus the AI assistant is grounded in.
      </p>

      <Alert className="mt-4">{error}</Alert>
      {saved && <Alert tone="success" className="mt-4">{saved}</Alert>}

      <div className="mt-4 grid gap-6 lg:grid-cols-[1fr_1.2fr]">
        <section className="min-w-0">
          <div className="flex items-center gap-2">
            <Input placeholder="Search…" value={q} onChange={(e) => setQ(e.target.value)} />
            <Button variant="secondary" onClick={newArticle}>
              <Plus size={16} /> New
            </Button>
          </div>
          <div className="mt-2 flex gap-2">
            <Select value={locale} onChange={(e) => setLocale(e.target.value)}>
              <option value="">All locales</option>
              {LOCALES.map((code) => (
                <option key={code} value={code}>
                  {code}
                </option>
              ))}
            </Select>
            <Select value={active} onChange={(e) => setActive(e.target.value)}>
              <option value="true">Active</option>
              <option value="false">Inactive</option>
              <option value="">All</option>
            </Select>
          </div>

          <div className="mt-4 space-y-2">
            {!articles && (
              <div className="flex justify-center py-10">
                <Spinner />
              </div>
            )}
            {articles?.length === 0 && (
              <EmptyState icon={BookOpen} title="No articles">
                Create one to seed the assistant's corpus.
              </EmptyState>
            )}
            {articles?.map((article) => (
              <Card
                key={article.id}
                className={`cursor-pointer transition hover:border-brand/40 ${
                  form.id === article.id ? "border-brand" : ""
                }`}
                onClick={() => select(article)}
              >
                <div className="flex items-start justify-between gap-3">
                  <p className="min-w-0 truncate text-sm font-extrabold text-ink">{article.title}</p>
                  <button
                    type="button"
                    title={article.is_active ? "Deactivate" : "Reactivate"}
                    onClick={(event) => {
                      event.stopPropagation();
                      toggleActive(article);
                    }}
                    className="shrink-0 text-muted hover:text-brand"
                  >
                    <RotateCcw size={15} />
                  </button>
                </div>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  <Badge tone="neutral">{article.section}</Badge>
                  <Badge tone="neutral">{article.locale}</Badge>
                  {!article.is_active && <Badge tone="warning">inactive</Badge>}
                </div>
              </Card>
            ))}
          </div>
        </section>

        <section>
          <Card>
            <h2 className="text-sm font-extrabold text-ink">
              {form.id ? "Edit article" : "New article"}
            </h2>
            <form onSubmit={save} className="mt-4 space-y-4">
              <Field label="Title">
                <Input
                  required
                  value={form.title}
                  onChange={(e) => setForm({ ...form, title: e.target.value })}
                />
              </Field>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Section">
                  <Input
                    value={form.section}
                    onChange={(e) => setForm({ ...form, section: e.target.value })}
                    placeholder="general"
                  />
                </Field>
                <Field label="Locale">
                  <Select
                    value={form.locale}
                    onChange={(e) => setForm({ ...form, locale: e.target.value })}
                  >
                    {LOCALES.map((code) => (
                      <option key={code} value={code}>
                        {code}
                      </option>
                    ))}
                  </Select>
                </Field>
              </div>
              <Field label="Summary" hint="Optional one-line summary.">
                <Input
                  value={form.summary}
                  onChange={(e) => setForm({ ...form, summary: e.target.value })}
                />
              </Field>
              <Field label="Body">
                <Textarea
                  rows={10}
                  required
                  value={form.body}
                  onChange={(e) => setForm({ ...form, body: e.target.value })}
                />
              </Field>
              <div className="flex gap-2">
                <Button type="submit" disabled={busy || !form.title.trim() || !form.body.trim()}>
                  {form.id ? "Save" : "Create"}
                </Button>
                {form.id && (
                  <Button type="button" variant="secondary" onClick={newArticle}>
                    Cancel
                  </Button>
                )}
              </div>
            </form>
          </Card>
        </section>
      </div>
    </div>
  );
}
