import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { searchBursaries, getFields } from "../api";
import SiteHeader from "../components/SiteHeader";
import "./BursaryList.css";

const STATUS_META = {
  verified_open: { label: "Open", tone: "green" },
  needs_verification: { label: "Verify before applying", tone: "amber" },
  expired: { label: "Closed", tone: "muted" },
  closed: { label: "Closed", tone: "muted" },
  unknown: { label: "Unconfirmed", tone: "muted" },
};

export default function BursaryList() {
  const [course, setCourse] = useState("");
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [suggestions, setSuggestions] = useState([]);

  useEffect(() => {
    getFields()
      .then((fields) => setSuggestions(fields.slice(0, 8)))
      .catch(() => setSuggestions([]));
  }, []);

  async function runSearch(value) {
    if (!value.trim()) return;

    setLoading(true);
    setError("");
    setResults(null);

    try {
      const data = await searchBursaries(value.trim());
      setResults(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  function handleSubmit(e) {
    e.preventDefault();
    runSearch(course);
  }

  function handleChip(field) {
    setCourse(field);
    runSearch(field);
  }

  return (
    <div className="search-page">
      <SiteHeader />

      <main className="search-page__main">
        <h1>Find bursaries for your course</h1>
        <p className="search-page__sub">
          Search by field of study to see verified, currently open bursaries
          and internships.
        </p>

        <form onSubmit={handleSubmit} className="search-form">
          <input
            type="text"
            placeholder="e.g. Computer Science"
            value={course}
            onChange={(e) => setCourse(e.target.value)}
          />
          <button type="submit" className="btn btn--primary" disabled={loading}>
            {loading ? "Searching…" : "Search"}
          </button>
        </form>

        {suggestions.length > 0 && (
          <div className="search-page__chips">
            {suggestions.map((field) => (
              <button
                key={field}
                type="button"
                className="chip"
                onClick={() => handleChip(field)}
              >
                {field}
              </button>
            ))}
          </div>
        )}

        {error && <p className="form-error">{error}</p>}

        {results && results.length === 0 && (
          <p className="search-page__empty">
            No currently open bursaries found for "{course}". Try a broader
            term, or ask the chat assistant instead.
          </p>
        )}

        <div className="result-list">
          {results?.map((b) => {
            const meta = STATUS_META[b.availability_status] || STATUS_META.unknown;
            return (
              <Link to={`/bursaries/${b.id}`} key={b.id} className="result-card">
                <div className="result-card__top">
                  <h3>{b.title}</h3>
                  <span className={`badge badge--${meta.tone}`}>{meta.label}</span>
                </div>
                {b.fields_of_study?.length > 0 && (
                  <p className="result-card__fields">
                    {b.fields_of_study.slice(0, 2).join(" · ")}
                  </p>
                )}
                {b.closing_date && (
                  <p className="result-card__closing">Closes {b.closing_date}</p>
                )}
              </Link>
            );
          })}
        </div>
      </main>
    </div>
  );
}
