import { Link } from "react-router-dom";
import Logo from "./Logo";
import "./Sidebar.css";

export default function Sidebar({ conversations, activeId, onNewConversation, onSelectConversation }) {
  return (
    <aside className="sidebar">
      <div className="sidebar__brand logo-sidebar">
        <Logo size="sm" />
        <span className="logo-tagline">Your bursary assistant</span>
      </div>

      <button className="sidebar__new" onClick={onNewConversation}>
        + New conversation
      </button>

      <div className="sidebar__section">
        <p className="sidebar__label">Recent chats</p>

        {conversations.length === 0 && (
          <p className="sidebar__empty">
            Your past conversations will show up here.
          </p>
        )}

        <ul className="sidebar__list">
          {conversations.map((c) => (
            <li key={c.id}>
              <button
                className={
                  c.id === activeId
                    ? "sidebar__chat is-active"
                    : "sidebar__chat"
                }
                onClick={() => onSelectConversation(c.id)}
                title={c.title}
              >
                {c.title}
              </button>
            </li>
          ))}
        </ul>
      </div>

      <div className="sidebar__footer">
        <Link to="/search" className="sidebar__footer-link">
          &larr; Back to search
        </Link>
        <div className="sidebar__profile">
          <span className="sidebar__profile-icon" aria-hidden="true">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="8" r="4" stroke="currentColor" strokeWidth="1.6" />
              <path
                d="M4 20c1.6-3.6 4.8-5.6 8-5.6s6.4 2 8 5.6"
                stroke="currentColor"
                strokeWidth="1.6"
                strokeLinecap="round"
              />
            </svg>
          </span>
          Profile
        </div>
      </div>
    </aside>
  );
}
