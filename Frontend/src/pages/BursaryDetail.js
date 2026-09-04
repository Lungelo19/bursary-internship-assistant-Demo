import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { getBursaryDetail } from "../api";
import SiteHeader from "../components/SiteHeader";
import "./BursaryDetail.css";

export default function BursaryDetail() {
  const { id } = useParams();
  const [bursary, setBursary] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    setError("");
    setBursary(null);

    getBursaryDetail(id)
      .then(setBursary)
      .catch((err) => setError(err.message));
  }, [id]);

  if (error) {
    return (
      <div className="detail-page">
        <SiteHeader variant="simple" backTo="/search" backLabel="Back to recommendations" />
        <main className="detail-page__main">
          <p className="form-error">{error}</p>
        </main>
      </div>
    );
  }

  if (!bursary) {
    return (
      <div className="detail-page">
        <SiteHeader variant="simple" backTo="/search" backLabel="Back to recommendations" />
        <main className="detail-page__main">
          <p className="detail-page__loading">Loading…</p>
        </main>
      </div>
    );
  }

  const subtitleParts = [];
  if (bursary.fields_of_study?.length) {
    subtitleParts.push(bursary.fields_of_study[0]);
  }
  subtitleParts.push(bursary.availability_label);
  if (bursary.closing_date) {
    subtitleParts.push(`Closes ${bursary.closing_date}`);
  }

  return (
    <div className="detail-page">
      <SiteHeader variant="simple" backTo="/search" backLabel="Back to recommendations" />

      <main className="detail-page__main">
        <h1>{bursary.title}</h1>
        <p className="detail-page__subtitle">{subtitleParts.join(" · ")}</p>

        <div className="detail-page__grid">
          <section className="detail-card">
            {bursary.fields_of_study?.length > 0 && (
              <div className="detail-card__block">
                <h2>Fields of study</h2>
                <p>{bursary.fields_of_study.join(", ")}</p>
              </div>
            )}

            {bursary.eligibility?.length > 0 && (
              <div className="detail-card__block">
                <h2>Who can apply</h2>
                <ul>
                  {bursary.eligibility.map((e, i) => (
                    <li key={i}>{e}</li>
                  ))}
                </ul>
              </div>
            )}

            {bursary.application_instructions?.length > 0 && (
              <div className="detail-card__block">
                <h2>How to apply</h2>
                <ul>
                  {bursary.application_instructions.map((step, i) => (
                    <li key={i}>{step}</li>
                  ))}
                </ul>
              </div>
            )}
          </section>

          <aside className="deadline-card">
            <p className="deadline-card__label">Application deadline</p>

            {bursary.closing_dates?.length > 0 ? (
              bursary.closing_dates.map((cd, i) => (
                <p className="deadline-card__date" key={i}>
                  {cd.category !== "General" && `${cd.category}: `}
                  {cd.date}
                </p>
              ))
            ) : (
              <p className="deadline-card__date">Not confirmed</p>
            )}

            <p className="deadline-card__note">
              {bursary.verified
                ? "Confirmed from the source listing."
                : "Check the official website before applying."}
            </p>

            {bursary.application_url && (
              <a
                href={bursary.application_url}
                target="_blank"
                rel="noreferrer"
                className="btn btn--primary deadline-card__cta"
              >
                Visit application website &rarr;
              </a>
            )}

            <a
              href={bursary.source_url}
              target="_blank"
              rel="noreferrer"
              className="deadline-card__source"
            >
              Source: {bursary.source}
            </a>
          </aside>
        </div>
      </main>
    </div>
  );
}
