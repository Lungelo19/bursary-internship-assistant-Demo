import { Link, useLocation } from "react-router-dom";
import Logo from "./Logo";
import "./SiteHeader.css";

const NAV_LINKS = [
  { to: "/", label: "Home" },
  { to: "/search", label: "Search" },
  { to: "/chat", label: "Chat" },
];

export default function SiteHeader({ variant = "full", backTo, backLabel }) {
  const { pathname } = useLocation();

  return (
    <header className="site-header">
      <div className="site-header__inner">
        <Link to="/" className="site-header__logo">
          <Logo suffix={variant === "simple" ? "AI" : null} />
        </Link>

        {variant === "full" && (
          <nav className="site-header__nav">
            {NAV_LINKS.map((link) => (
              <Link
                key={link.to}
                to={link.to}
                className={
                  pathname === link.to
                    ? "site-header__link is-active"
                    : "site-header__link"
                }
              >
                {link.label}
              </Link>
            ))}
          </nav>
        )}

        {variant === "full" && (
          <div className="site-header__lang">English</div>
        )}
      </div>

      {backTo && (
        <div className="site-header__subrow">
          <Link to={backTo} className="site-header__back">
            &larr; {backLabel || "Back"}
          </Link>
        </div>
      )}
    </header>
  );
}
