import React, { useRef, useState } from 'react';
import { FileText, UploadCloud, X, Loader2, CheckCircle2, AlertCircle, ChevronDown, ChevronUp } from 'lucide-react';
import { SessionDocument, Language } from '../types';
import { translations } from '../i18n/translations';

interface DocumentCenterProps {
  documents: SessionDocument[];
  onUploadFiles: (files: File[]) => void;
  onRemoveDocument: (docName: string) => void;
  language: Language;
  isUploading: boolean;
}

const MAX_DOCS = 5;

export const DocumentCenter: React.FC<DocumentCenterProps> = ({
  documents,
  onUploadFiles,
  onRemoveDocument,
  language,
  isUploading,
}) => {
  const t = translations[language];
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isCollapsed, setIsCollapsed] = useState(false);

  const canUpload = documents.length < MAX_DOCS;
  const remainingSlots = MAX_DOCS - documents.length;

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    if (canUpload) setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (!canUpload) return;

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const filesArray = Array.from(e.dataTransfer.files).slice(0, remainingSlots);
      onUploadFiles(filesArray);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const filesArray = Array.from(e.target.files).slice(0, remainingSlots);
      onUploadFiles(filesArray);
      e.target.value = '';
    }
  };

  return (
    <div
      style={{
        margin: '0.75rem 1rem 0.25rem 1rem',
        borderRadius: 'var(--radius-lg)',
        backgroundColor: 'var(--bg-surface)',
        border: '1px solid var(--border-subtle)',
        boxShadow: 'var(--shadow-sm)',
        transition: 'all var(--transition-normal)',
        overflow: 'hidden',
      }}
    >
      {/* Panel Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0.65rem 1rem',
          backgroundColor: 'var(--bg-card)',
          borderBottom: isCollapsed ? 'none' : '1px solid var(--border-subtle)',
          cursor: 'pointer',
          userSelect: 'none',
        }}
        onClick={() => setIsCollapsed(!isCollapsed)}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
          <div
            style={{
              padding: '0.35rem',
              borderRadius: 'var(--radius-sm)',
              background: 'rgba(16, 185, 129, 0.15)',
              color: 'var(--accent-emerald)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <FileText size={16} />
          </div>
          <span style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-primary)' }}>
            {t.docCenterTitle}
          </span>
          <span
            style={{
              fontSize: '0.75rem',
              padding: '0.15rem 0.5rem',
              borderRadius: 'var(--radius-full)',
              background: documents.length === MAX_DOCS ? 'rgba(239, 68, 68, 0.15)' : 'var(--bg-base)',
              color: documents.length === MAX_DOCS ? 'var(--accent-rose)' : 'var(--accent-emerald)',
              border: '1px solid var(--border-subtle)',
              fontWeight: 600,
            }}
          >
            {documents.length} / {MAX_DOCS}
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          {isUploading && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: 'var(--accent-blue)', fontSize: '0.75rem' }}>
              <Loader2 size={13} className="animate-spin" />
              <span>{t.docUploading}</span>
            </div>
          )}
          <button
            style={{
              padding: '0.2rem',
              color: 'var(--text-muted)',
              display: 'flex',
              alignItems: 'center',
            }}
          >
            {isCollapsed ? <ChevronDown size={16} /> : <ChevronUp size={16} />}
          </button>
        </div>
      </div>

      {/* Collapsible Content */}
      {!isCollapsed && (
        <div style={{ padding: '0.75rem 1rem' }}>
          {/* Active Documents List */}
          {documents.length > 0 && (
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
                gap: '0.5rem',
                marginBottom: canUpload ? '0.75rem' : '0',
              }}
            >
              {documents.map((doc, idx) => (
                <div
                  key={`${doc.name}-${idx}`}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '0.45rem 0.65rem',
                    borderRadius: 'var(--radius-md)',
                    backgroundColor: 'var(--bg-base)',
                    border: '1px solid var(--border-medium)',
                    fontSize: '0.8rem',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', minWidth: 0, flex: 1 }}>
                    <FileText size={15} style={{ color: 'var(--accent-blue)', flexShrink: 0 }} />
                    <span
                      style={{
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                        color: 'var(--text-primary)',
                        fontWeight: 500,
                      }}
                      title={doc.name}
                    >
                      {doc.name}
                    </span>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', flexShrink: 0 }}>
                    {doc.status === 'uploading' ? (
                      <span title={t.docUploading} style={{ display: 'flex' }}>
                        <Loader2 size={13} className="animate-spin" style={{ color: 'var(--accent-blue)' }} />
                      </span>
                    ) : doc.status === 'error' ? (
                      <span title={doc.errorMessage || t.docError} style={{ display: 'flex' }}>
                        <AlertCircle size={13} style={{ color: 'var(--accent-rose)' }} />
                      </span>
                    ) : (
                      <span title={t.docIndexed} style={{ display: 'flex' }}>
                        <CheckCircle2 size={13} style={{ color: 'var(--accent-emerald)' }} />
                      </span>
                    )}

                    <button
                      onClick={() => onRemoveDocument(doc.name)}
                      style={{
                        padding: '0.15rem',
                        color: 'var(--text-muted)',
                        borderRadius: 'var(--radius-sm)',
                        display: 'flex',
                        alignItems: 'center',
                      }}
                      onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--accent-rose)')}
                      onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--text-muted)')}
                      title={t.deleteDoc}
                    >
                      <X size={13} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Upload Dropzone */}
          {canUpload ? (
            <div
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              style={{
                border: `2px dashed ${isDragging ? 'var(--accent-blue)' : 'var(--border-highlight)'}`,
                borderRadius: 'var(--radius-md)',
                backgroundColor: isDragging ? 'rgba(59, 130, 246, 0.08)' : 'var(--bg-base)',
                padding: documents.length === 0 ? '1.25rem 1rem' : '0.75rem 1rem',
                textAlign: 'center',
                cursor: 'pointer',
                transition: 'all var(--transition-fast)',
              }}
            >
              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept=".pdf,.docx,.txt,.md"
                onChange={handleFileChange}
                style={{ display: 'none' }}
              />
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.35rem' }}>
                <UploadCloud
                  size={documents.length === 0 ? 24 : 18}
                  style={{ color: isDragging ? 'var(--accent-blue)' : 'var(--text-muted)' }}
                />
                <p style={{ fontSize: '0.82rem', fontWeight: 500, color: 'var(--text-primary)' }}>
                  {t.docDropzonePrompt}
                </p>
                <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                  {t.docDropzoneSub}
                </p>
              </div>
            </div>
          ) : (
            <div
              style={{
                padding: '0.6rem 0.8rem',
                borderRadius: 'var(--radius-md)',
                backgroundColor: 'rgba(239, 68, 68, 0.08)',
                border: '1px solid rgba(239, 68, 68, 0.25)',
                color: 'var(--text-secondary)',
                fontSize: '0.78rem',
                textAlign: 'center',
              }}
            >
              {t.docLimitReached}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
