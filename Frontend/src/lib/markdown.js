import { Fragment } from "react";

// The chat model is nudged (see backend/bursary/chat_agent.py's system
// prompt) toward a small, predictable subset of markdown: **bold**,
// "- " bullet lines, and bare URLs. Pulling in a full markdown library
// for that would be overkill, so this renders just those, plus
// paragraph breaks on blank lines. Anything it doesn't recognise is
// left as plain text rather than mangled.

const URL_PATTERN = /(https?:\/\/[^\s)]+)/g;
const BOLD_PATTERN = /\*\*(.+?)\*\*/g;

function renderInline(text, keyPrefix) {
  // Split on bold markers first, then linkify whatever's left.
  const boldParts = text.split(BOLD_PATTERN);

  return boldParts.map((part, i) => {
    const isBold = i % 2 === 1;
    const nodes = linkify(part, `${keyPrefix}-${i}`);
    return isBold ? (
      <strong key={`${keyPrefix}-b-${i}`}>{nodes}</strong>
    ) : (
      <Fragment key={`${keyPrefix}-t-${i}`}>{nodes}</Fragment>
    );
  });
}

function linkify(text, keyPrefix) {
  const parts = text.split(URL_PATTERN);

  return parts.map((part, i) => {
    if (part.match(URL_PATTERN)) {
      return (
        <a
          key={`${keyPrefix}-l-${i}`}
          href={part}
          target="_blank"
          rel="noreferrer"
          className="chat-link"
        >
          {part}
        </a>
      );
    }
    return part;
  });
}

export default function renderMarkdown(content) {
  if (!content) return null;

  const blocks = content.trim().split(/\n{2,}/);

  return blocks.map((block, blockIndex) => {
    const lines = block.split("\n").filter((l) => l.trim() !== "");
    const isList = lines.length > 0 && lines.every((l) => /^[-*]\s+/.test(l.trim()));

    if (isList) {
      return (
        <ul className="chat-list" key={`b-${blockIndex}`}>
          {lines.map((line, i) => (
            <li key={i}>{renderInline(line.trim().replace(/^[-*]\s+/, ""), `b${blockIndex}-i${i}`)}</li>
          ))}
        </ul>
      );
    }

    return (
      <p key={`b-${blockIndex}`}>
        {lines.map((line, i) => (
          <Fragment key={i}>
            {i > 0 && <br />}
            {renderInline(line, `b${blockIndex}-l${i}`)}
          </Fragment>
        ))}
      </p>
    );
  });
}
