import { Link } from "react-router-dom";
import SiteHeader from "../components/SiteHeader";
import "./Landing.css";

export default function Landing() {
  return (
    <div className="landing">
      <SiteHeader />

      <main className="landing__hero">
        <div className="landing__copy">
          <h1>
            Find the right bursary
            <br />
            for your future.
          </h1>
          <p>
            Tell us what you want to study and share your results.
            BursaryBot will help you discover funding opportunities and
            understand how to apply.
          </p>
          <div className="landing__actions">
            <Link to="/chat" className="btn btn--primary">
              Start chatting &rarr;
            </Link>
            <Link to="/search" className="btn btn--ghost">
              Search bursaries instead
            </Link>
          </div>
        </div>

        <div className="landing__preview" aria-hidden="true">
          <p className="landing__preview-label">BursaryBot</p>
          <div className="landing__preview-bubble landing__preview-bubble--bot">
            Hi! What would you like to study?
          </div>
          <div className="landing__preview-bubble landing__preview-bubble--user">
            I want to study Engineering
          </div>
          <div className="landing__preview-bubble landing__preview-bubble--bot">
            Great — let's find bursaries for you.
          </div>
        </div>
      </main>
    </div>
  );
}
