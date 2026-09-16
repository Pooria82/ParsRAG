import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Bot, User, Copy, Check, ChevronDown, ChevronUp, FileText, Sparkles, Loader2 } from 'lucide-react';
import { Message, Citation, Language } from '../types';
import { translations } from '../i18n/translations';

interface ChatFeedProps {
  messages: Message[];
  language: Language;
  onSelectStarterPrompt: (prompt: string) => void;
  isGenerating: boolean;
}

export const ChatFeed: React.FC<ChatFeedProps> = ({
  messages,
  language,
  onSelectStarterPrompt,
  isGenerating,
}) => {
  const t = translations[language];
  const scrollEndRef = useRef<HTMLDivElement>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [expandedCitations, setExpandedCitations] = useState<Record<string, boolean>>({});

  useEffect(() => {
    scrollEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isGenerating]);

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const toggleCitations = (msgId: string) => {
    setExpandedCitations(prev => ({
      ...prev,
      [msgId]: !prev[msgId],
    }));
  };

  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: '1rem', display: 'flex', flexDirection: 'column' }}>
      {/* Empty State Hero */}
      {messages.length === 0 ? (
        <div
          style={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            maxWidth: '680px',
            margin: '0 auto',
            textAlign: 'center',
            padding: '2rem 1rem',
          }}
        >
          <div
            style={{
              width: '56px',
              height: '56px',
              borderRadius: 'var(--radius-lg)',
              background: 'linear-gradient(135deg, var(--accent-emerald), var(--accent-blue))',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#fff',
              marginBottom: '1.25rem',
              boxShadow: 'var(--shadow-md)',
            }}
          >
            <Sparkles size={28} />
          </div>

          <h2 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: '0.5rem' }}>
            {t.heroGreeting}
          </h2>
          <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', marginBottom: '2rem', maxWidth: '480px' }}>
            {t.heroDescription}
          </p>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
              gap: '0.75rem',
              width: '100%',
            }}
          >
            {t.starterPrompts.map((starter, idx) => (
              <div
                key={idx}
                onClick={() => onSelectStarterPrompt(starter.desc)}
                style={{
                  padding: '1rem',
                  borderRadius: 'var(--radius-md)',
                  backgroundColor: 'var(--bg-surface)',
                  border: '1px solid var(--border-subtle)',
                  textAlign: 'start',
                  cursor: 'pointer',
                  transition: 'all var(--transition-fast)',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = 'var(--bg-card-hover)';
                  e.currentTarget.style.borderColor = 'var(--accent-blue)';
                  e.currentTarget.style.transform = 'translateY(-2px)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = 'var(--bg-surface)';
                  e.currentTarget.style.borderColor = 'var(--border-subtle)';
                  e.currentTarget.style.transform = 'none';
                }}
              >
                <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.25rem' }}>
                  {starter.title}
                </div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', lineHeight: 1.4 }}>
                  {starter.desc}
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div style={{ maxWidth: '820px', width: '100%', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          {messages.map((msg) => {
            const isUser = msg.role === 'user';
            const hasCitations = msg.citations && msg.citations.length > 0;
            const isCitationsOpen = !!expandedCitations[msg.id];

            return (
              <div
                key={msg.id}
                style={{
                  display: 'flex',
                  gap: '0.75rem',
                  alignItems: 'flex-start',
                  flexDirection: isUser ? 'row-reverse' : 'row',
                }}
              >
                {/* Avatar */}
                <div
                  style={{
                    width: '32px',
                    height: '32px',
                    borderRadius: 'var(--radius-md)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0,
                    background: isUser
                      ? 'var(--accent-blue)'
                      : 'linear-gradient(135deg, var(--accent-emerald), var(--accent-blue))',
                    color: '#fff',
                    boxShadow: 'var(--shadow-sm)',
                  }}
                >
                  {isUser ? <User size={16} /> : <Bot size={16} />}
                </div>

                {/* Message Bubble Container */}
                <div
                  style={{
                    maxWidth: '80%',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: isUser ? 'flex-end' : 'flex-start',
                  }}
                >
                  <div
                    style={{
                      padding: '0.85rem 1.15rem',
                      borderRadius: isUser ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
                      backgroundColor: isUser ? 'var(--accent-blue)' : 'var(--bg-surface)',
                      color: isUser ? '#ffffff' : 'var(--text-primary)',
                      border: isUser ? 'none' : '1px solid var(--border-subtle)',
                      boxShadow: 'var(--shadow-sm)',
                      wordBreak: 'break-word',
                    }}
                    className={isUser ? '' : 'prose-content'}
                  >
                    {isUser ? (
                      <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.6, fontSize: '0.92rem' }}>
                        {msg.content}
                      </div>
                    ) : (
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {msg.content}
                      </ReactMarkdown>
                    )}
                  </div>

                  {/* Citations Accordion (Assistant Only) */}
                  {!isUser && hasCitations && (
                    <div
                      style={{
                        width: '100%',
                        marginTop: '0.5rem',
                        borderRadius: 'var(--radius-md)',
                        border: '1px solid var(--border-subtle)',
                        backgroundColor: 'var(--bg-base)',
                        overflow: 'hidden',
                      }}
                    >
                      <button
                        onClick={() => toggleCitations(msg.id)}
                        style={{
                          width: '100%',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          padding: '0.5rem 0.75rem',
                          fontSize: '0.78rem',
                          color: 'var(--accent-emerald)',
                          fontWeight: 600,
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                          <FileText size={14} />
                          <span>{t.citationsTitle} ({msg.citations!.length})</span>
                        </div>
                        {isCitationsOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                      </button>

                      {isCitationsOpen && (
                        <div style={{ padding: '0.5rem 0.75rem', display: 'flex', flexDirection: 'column', gap: '0.5rem', borderTop: '1px solid var(--border-subtle)' }}>
                          {msg.citations!.map((cit: Citation, idx: number) => (
                            <div
                              key={idx}
                              style={{
                                padding: '0.5rem',
                                borderRadius: 'var(--radius-sm)',
                                backgroundColor: 'var(--bg-card)',
                                border: '1px solid var(--border-subtle)',
                                fontSize: '0.75rem',
                              }}
                            >
                              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.3rem' }}>
                                <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                                  {cit.filename}
                                </span>
                                {cit.score > 0 && (
                                  <span
                                    style={{
                                      fontSize: '0.68rem',
                                      padding: '0.1rem 0.35rem',
                                      borderRadius: 'var(--radius-full)',
                                      background: 'rgba(16, 185, 129, 0.15)',
                                      color: 'var(--accent-emerald)',
                                      fontWeight: 600,
                                    }}
                                  >
                                    {Math.round(cit.score * 100)}% {t.similarityScore}
                                  </span>
                                )}
                              </div>
                              <p style={{ color: 'var(--text-muted)', lineHeight: 1.5, maxHeight: '120px', overflowY: 'auto' }}>
                                {cit.body}
                              </p>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Message Action Toolbar */}
                  {!isUser && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.35rem' }}>
                      <button
                        onClick={() => copyToClipboard(msg.content, msg.id)}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '0.3rem',
                          fontSize: '0.72rem',
                          color: 'var(--text-muted)',
                          padding: '0.2rem 0.4rem',
                          borderRadius: 'var(--radius-sm)',
                        }}
                        onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--text-primary)')}
                        onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--text-muted)')}
                      >
                        {copiedId === msg.id ? <Check size={12} style={{ color: 'var(--accent-emerald)' }} /> : <Copy size={12} />}
                        <span>{copiedId === msg.id ? t.copied : t.copyCode}</span>
                      </button>
                    </div>
                  )}
                </div>
              </div>
            );
          })}

          {/* Thinking / Searching Indicator */}
          {isGenerating && (
            <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
              <div
                style={{
                  width: '32px',
                  height: '32px',
                  borderRadius: 'var(--radius-md)',
                  background: 'linear-gradient(135deg, var(--accent-emerald), var(--accent-blue))',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#fff',
                }}
              >
                <Bot size={16} />
              </div>
              <div
                style={{
                  padding: '0.75rem 1rem',
                  borderRadius: '16px 16px 16px 4px',
                  backgroundColor: 'var(--bg-surface)',
                  border: '1px solid var(--border-subtle)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  fontSize: '0.85rem',
                  color: 'var(--accent-blue)',
                }}
              >
                <Loader2 size={15} className="animate-spin" />
                <span>{t.thinking}</span>
              </div>
            </div>
          )}

          <div ref={scrollEndRef} />
        </div>
      )}
    </div>
  );
};
