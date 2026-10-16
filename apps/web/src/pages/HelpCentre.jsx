import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { BookOpen, LifeBuoy, Search, ThumbsDown, ThumbsUp } from "lucide-react";
import { api } from "../lib/api";
import { Alert, Badge, Button, Card, EmptyState, Input, Spinner } from "../components/ui";

export default function HelpCentre() {
  const { slug, articleSlug } = useParams();
  const [index, setIndex] = useState(null);
  const [article, setArticle] = useState(null);
  const [query, setQuery] = useState("");
  const [section, setSection] = useState("");
  const [error, setError] = useState(null);
  const [voted, setVoted] = useState(null);

  const loadIndex = useCallback(() => {
    const params = {};
    if (query) params.q = query;
    if (section) params.section = section;
    return api
      .helpIndex(slug, params)
      .then(setIndex)
      .catch((err) => setError(err.message));
  }, [slug, query, section]);

  useEffect(() => {
    if (!articleSlug) loadIndex();
  }, [articleSlug, loadIndex]);

  useEffect(() => {
    if (!articleSlug) {
      setArticle(null);
      return;
    }
    setArticle(null);
    setVoted(null);
    setError(null);
    api
      .helpArticle(slug, articleSlug)
      .then(setArticle)
      .catch((err) => setError(err.message));
  }, [slug, articleSlug]);

  async function vote(helpful) {
    setVoted(helpful);
    try {
      await api.helpFeedback(slug, articleSlug, { helpful });
      setArticle((current) =>
        current
          ? {
              ...current,
              helpful_yes: current.helpful_yes + (helpful ? 1 : 0),
              helpful_no: current.helpful_no + (helpful ? 0 : 1),
            }
          : current,
      );
    } catch (err) {
      setError(err.message);
      setVoted(null);
    }
  }

  return (
    <div className="min-h-screen bg-page px-6 py-10 text-ink-soft">
      <div className="mx-auto max-w-3xl">
        <Link to={`/help/${slug}`} className="flex items-center gap-2.5">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand text-white">
            <LifeBuoy size={18} />
          </span>
          <span className="text-base font-extrabold text-ink">Help centre</span>
        </Link>

        <Alert className="mt-4">{error}</Alert>

        {articleSlug ? (
          <article className="mt-6">
            {!article && !error && (
              <div className="flex justify-center py-16">
                <Spinner />
              </div>
            )}
            {article && (
              <>
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone="neutral">{article.section}</Badge>
                  <Badge tone="neutral">{article.locale}</Badge>
                </div>
                <h1 className="mt-3 text-2xl font-black text-ink">{article.title}</h1>
                {article.summary && <p className="mt-2 text-sm text-muted">{article.summary}</p>}
                <div className="mt-6 whitespace-pre-wrap text-sm leading-relaxed text-ink">
                  {article.body}
                </div>
                <div className="mt-8 border-t border-line pt-5">
                  <p className="text-xs font-bold uppercase tracking-[.08em] text-muted">
                    Was this helpful?
                  </p>
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <Button
                      variant={voted === true ? "primary" : "secondary"}
                      disabled={voted !== null}
                      onClick={() => vote(true)}
                    >
                      <ThumbsUp size={16} /> Yes
                    </Button>
                    <Button
                      variant={voted === false ? "primary" : "secondary"}
                      disabled={voted !== null}
                      onClick={() => vote(false)}
                    >
                      <ThumbsDown size={16} /> No
                    </Button>
                    <span className="text-xs text-muted">
                      {article.helpful_yes} found this helpful · {article.helpful_no} did not
                    </span>
                  </div>
                  {voted !== null && (
                    <p className="mt-2 text-xs font-bold text-brand">Thanks for the feedback.</p>
                  )}
                </div>
              </>
            )}
          </article>
        ) : (
          <>
            <div className="mt-6 flex flex-wrap gap-3">
              <form
                className="relative flex-1"
                onSubmit={(event) => {
                  event.preventDefault();
                  loadIndex();
                }}
              >
                <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
                <Input
                  className="pl-9"
                  placeholder="Search articles…"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                />
              </form>
              {index?.sections?.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {index.sections.map((s) => (
                    <button
                      key={s.section}
                      type="button"
                      onClick={() => setSection(section === s.section ? "" : s.section)}
                      className={`rounded-full px-2.5 py-1 text-xs font-bold transition ${
                        section === s.section
                          ? "bg-brand-soft text-brand"
                          : "bg-surface-sunken text-muted hover:text-ink-soft"
                      }`}
                    >
                      {s.section} ({s.count})
                    </button>
                  ))}
                </div>
              )}
            </div>

            <div className="mt-6 space-y-2">
              {!index && !error && (
                <div className="flex justify-center py-16">
                  <Spinner />
                </div>
              )}
              {index?.articles?.length === 0 && (
                <EmptyState icon={BookOpen} title="No articles">
                  Nothing matches your search.
                </EmptyState>
              )}
              {index?.articles?.map((a) => (
                <Link key={a.slug} to={`/help/${slug}/${a.slug}`} className="block">
                  <Card className="transition hover:border-brand/40">
                    <p className="text-sm font-extrabold text-ink">{a.title}</p>
                    {a.summary && <p className="mt-1 text-sm text-ink-soft">{a.summary}</p>}
                    <Badge tone="neutral" className="mt-2">
                      {a.section}
                    </Badge>
                  </Card>
                </Link>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
