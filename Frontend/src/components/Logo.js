import "./Logo.css";

export default function Logo({ suffix, size = "md" }) {
  return (
    <span className={`logo logo--${size}`}>
      <span className="logo__badge">TP</span>
      <span className="logo__word">
        TholaPath
        {suffix && <span className="logo__suffix">{suffix}</span>}
      </span>
    </span>
  );
}
