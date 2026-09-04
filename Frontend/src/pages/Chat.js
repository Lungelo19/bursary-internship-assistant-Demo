import { useEffect, useRef, useState } from "react";
import { sendChatMessage } from "../api";
import Sidebar from "../components/Sidebar";
import Logo from "../components/Logo";
import renderMarkdown from "../lib/markdown";
import "./Chat.css";

const STORAGE_KEY = "tholapath_conversations";

const QUICK_ACTIONS = [
  {
    title: "Find bursaries for me",
    description: "Get bursaries that match your study interests.",
    prompt: "I'd like to find bursaries for what I'm studying.",
  },
  {
    title: "Check if I qualify",
    description: "Check marks, subjects, and requirements.",
    prompt: "Can you check whether I qualify for a bursary?",
  },
  {
    title: "How do I apply?",
    description: "See the steps, documents, and closing dates.",
    prompt: "How do I apply, and what documents will I need?",
  },
];

function loadConversations() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function makeTitle(text) {
  const trimmed = text.trim();
  return trimmed.length > 34 ? `${trimmed.slice(0, 34)}…` : trimmed;
}

export default function Chat() {
  const [conversations, setConversations] = useState(loadConversations);
  const [activeId, setActiveId] = useState(null);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const bottomRef = useRef(null);
  const inputRef = useRef(null);

  const active = conversations.find((c) => c.id === activeId) || null;

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations));
  }, [conversations]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [active?.messages?.length, loading]);

  function updateConversation(id, updater) {
    setConversations((prev) =>
      prev.map((c) => (c.id === id ? updater(c) : c))
    );
  }

  async function handleSend(e) {
    e.preventDefault();
    const text = input.trim();
    if (!text || loading) return;

    setError("");
    setInput("");

    let conversation = active;

    if (!conversation) {
      conversation = {
        id: crypto.randomUUID(),
        title: makeTitle(text),
        course: text,
        sessionId: null,
        messages: [],
      };
      setConversations((prev) => [conversation, ...prev]);
      setActiveId(conversation.id);
    }

    const conversationId = conversation.id;

    updateConversation(conversationId, (c) => ({
      ...c,
      messages: [...c.messages, { role: "user", content: text }],
    }));

    setLoading(true);

    try {
      const data = await sendChatMessage(
        conversation.course,
        text,
        conversation.sessionId
      );

      updateConversation(conversationId, (c) => ({
        ...c,
        sessionId: data.session_id,
        messages: [...c.messages, { role: "assistant", content: data.reply }],
      }));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  function handleNewConversation() {
    setActiveId(null);
    setInput("");
    setError("");
    inputRef.current?.focus();
  }

  function handleQuickAction(prompt) {
    setInput(prompt);
    inputRef.current?.focus();
  }

  return (
    <div className="chat-shell">
      <Sidebar
        conversations={conversations}
        activeId={activeId}
        onNewConversation={handleNewConversation}
        onSelectConversation={setActiveId}
      />

      <div className="chat-main">
        <div className="chat-topbar">
          <Logo size="sm" suffix="AI" />
          <div className="chat-topbar__lang">English</div>
        </div>

        {!active ? (
          <div className="chat-welcome">
            <div className="chat-welcome__icon">TP</div>
            <h1>Welcome to TholaPath Assistant</h1>
            <p>
              I can help you find bursaries, check requirements, and explain
              how to apply.
            </p>

            <div className="chat-welcome__cards">
              {QUICK_ACTIONS.map((action) => (
                <button
                  key={action.title}
                  className="quick-card"
                  onClick={() => handleQuickAction(action.prompt)}
                >
                  <h3>{action.title}</h3>
                  <p>{action.description}</p>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="chat-window">
            {active.messages.map((m, i) => (
              <div key={i} className={`bubble bubble--${m.role}`}>
                {m.role === "assistant" ? renderMarkdown(m.content) : m.content}
              </div>
            ))}
            {loading && (
              <div className="bubble bubble--assistant bubble--typing">
                Thinking…
              </div>
            )}
            <div ref={bottomRef} />
          </div>
        )}

        {error && <p className="form-error chat-error">{error}</p>}

        <form onSubmit={handleSend} className="chat-input-row">
          <input
            ref={inputRef}
            type="text"
            placeholder="Type your message…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={loading}
          />
          <button
            type="submit"
            className="btn btn--primary"
            disabled={!input.trim() || loading}
          >
            Send
          </button>
        </form>
      </div>
    </div>
  );
}
