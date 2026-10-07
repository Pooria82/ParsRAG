import { useRef, useState } from 'react';
import { AlertCircle, Check, FileText, FolderOpen, Loader2, LockKeyhole, Plus, Trash2, Upload } from 'lucide-react';
import type { SessionDocument, IngestionCapabilities, Language, RAGMode } from '../types';
import { translations } from '../i18n/translations';
import { DEFAULT_INGESTION_CAPABILITIES } from '../core/state';
import { Dialog } from './Dialog';

interface DocumentCenterProps {
  isOpen: boolean; onClose: () => void; documents: SessionDocument[];
  guided?: boolean;
  onUploadFiles: (files: File[]) => void; onRemoveFailed: (name: string) => void;
  onToggleDocument: (name: string) => void; onDeleteDocument: (name: string) => void; language: Language; isUploading: boolean;
  activeMode: RAGMode; error: string | null;
  capabilities?: IngestionCapabilities;
  reusableDocuments: Array<{ sourceSessionId: string; sourceTitle: string; name: string }>;
  onReuseDocument: (sourceSessionId: string, name: string) => void;
}

export function DocumentCenter({ isOpen, onClose, documents, onUploadFiles, onRemoveFailed, onToggleDocument, onDeleteDocument, reusableDocuments, onReuseDocument, language, isUploading, activeMode, error, capabilities = DEFAULT_INGESTION_CAPABILITIES, guided = false }: DocumentCenterProps) {
  const t = translations[language];
  const fileInput = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<string | null>(null);
  const full = documents.length >= capabilities.max_files_per_session;
  const sizeLabel = `${Math.round(capabilities.max_file_size_bytes / 1024 / 1024).toLocaleString(language)} MB`;
  const limitLabel = capabilities.max_files_per_session.toLocaleString(language);
  const limitReached = t.docLimitReached.replace('{count}', limitLabel);
  const dropzoneDetails = t.docDropzoneSub.replace('{size}', sizeLabel).replace('{count}', limitLabel);
  return <Dialog open={isOpen} guided={guided} onClose={onClose} title={t.docCenterTitle} subtitle={t.docCenterDesc} closeLabel={t.close} className="documents-dialog">
    <div className="documents-body">
      <input type="file" ref={fileInput} className="visually-hidden" tabIndex={-1} accept={capabilities.supported_extensions.join(',')} multiple aria-label={t.attach}
        onChange={event => { const files = Array.from(event.target.files ?? []); if (files.length) onUploadFiles(files); event.target.value = ''; }} />
      {!documents.length && <div className="document-empty"><span className="document-empty-art"><FileText size={34} /><span><Plus size={15} /></span></span><h3>{t.docEmptyTitle}</h3><p>{t.docEmptyDesc}</p></div>}
      <button data-tour="document-upload" className={'dropzone ' + (dragging ? 'is-dragging' : '')} disabled={full || isUploading}
        onClick={() => fileInput.current?.click()}
        onDragOver={event => { event.preventDefault(); if (!full && !isUploading) setDragging(true); }}
        onDragLeave={event => { if (!event.currentTarget.contains(event.relatedTarget as Node)) setDragging(false); }}
        onDrop={event => { event.preventDefault(); setDragging(false); if (!full && !isUploading) onUploadFiles(Array.from(event.dataTransfer.files)); }}>
        {isUploading ? <Loader2 className="spin" size={25} /> : <Upload size={25} />}
        <strong>{full ? limitReached : isUploading ? t.docUploading : t.docDropzonePrompt}</strong>
        {!full && !isUploading && <span className="browse-link">{t.docBrowse}</span>}
        <small>{dropzoneDetails}</small>
      </button>
      {(reusableDocuments.length > 0 || guided) && !full && <section className="reusable-documents" data-tour="document-reuse" aria-label={t.reuseDocumentsTitle}>
        <div className="document-list-heading"><span>{t.reuseDocumentsTitle}</span><small>{t.reuseDocumentsHint}</small></div>
        {reusableDocuments.length === 0 && <p className="tour-empty-hint">{language === 'fa' ? 'پس از نمایه‌سازی اولین سند، می‌توانید آن را در گفت‌وگوهای دیگر از اینجا انتخاب کنید.' : 'After indexing a document, you can select it here in another conversation.'}</p>}
        <div className="reusable-document-list">
          {reusableDocuments.map(item => <div className="reusable-document" key={`${item.sourceSessionId}:${item.name}`}>
            <FileText size={17} aria-hidden="true" />
            <span><bdi title={item.name}>{item.name}</bdi><small>{item.sourceTitle}</small></span>
            <button className="button secondary" disabled={isUploading} onClick={() => onReuseDocument(item.sourceSessionId, item.name)}>{t.reuseDocument}</button>
          </div>)}
        </div>
      </section>}
      {error && <p className="inline-error" role="alert"><AlertCircle size={16} />{error}</p>}
      {documents.length > 0 && <div data-tour="document-selection">
        <div className="document-list-heading"><span>{t.documents}</span><span>{documents.length.toLocaleString(language)} / {limitLabel}</span></div>
        <div className="document-list">
          {documents.map(doc => <div className={'document-row status-' + doc.status} key={doc.name}>
            <span className="document-file-icon"><FileText size={21} /><small>{doc.name.split('.').pop()?.toUpperCase()}</small></span>
            <div className="document-meta"><bdi title={doc.name}>{doc.name}</bdi><span>
              {doc.status === 'uploading' || doc.status === 'processing' ? <Loader2 size={12} className="spin" /> : doc.status === 'indexed' ? <Check size={12} /> : <AlertCircle size={12} />}
              {doc.status === 'uploading' ? t.docUploading : doc.status === 'processing' ? t.docProcessing : doc.status === 'indexed' ? t.docIndexed : t.docError}
              {doc.size ? <small dir="ltr">{(doc.size / 1024 / 1024).toFixed(1)} MB</small> : null}
            </span>
              {(doc.status === 'uploading' || doc.status === 'processing') && <UploadJourney status={doc.status} progress={doc.uploadProgress ?? 0} language={language} />}
              {doc.status === 'error' && <p>{doc.errorMessage === 'interrupted' ? t.interrupted : doc.errorMessage || t.uploadFailed}</p>}
            </div>
            {doc.status === 'indexed' && <input type="checkbox" checked={doc.enabled !== false}
              onChange={() => onToggleDocument(doc.name)} aria-label={t.docSelected + ': ' + doc.name} />}
            {doc.status === 'indexed' && (pendingDelete === doc.name ? <span className="document-delete-confirm"><button className="button secondary" onClick={() => setPendingDelete(null)}>{t.cancel}</button><button className="button danger" disabled={isUploading} onClick={() => { onDeleteDocument(doc.name); setPendingDelete(null); }}>{t.confirmDeleteDocument}</button></span> : <button className="icon-button danger-text" disabled={isUploading} onClick={() => setPendingDelete(doc.name)} aria-label={t.deleteDocument + ': ' + doc.name}><Trash2 size={16} /></button>)}
            {doc.status === 'error' && <button className="icon-button danger-text" onClick={() => onRemoveFailed(doc.name)} aria-label={t.removeFailed + ': ' + doc.name}><Trash2 size={16} /></button>}
          </div>)}
        </div>
        <p className="document-selection-hint">{t.docSelectionHint}</p>
      </div>}
      {guided && documents.length === 0 && <p className="tour-empty-hint" data-tour="document-selection">{language === 'fa' ? 'سندهای بارگذاری‌شده اینجا ظاهر می‌شوند؛ می‌توانید انتخابشان را تغییر دهید یا حذفشان کنید.' : 'Uploaded documents appear here; you can change their selection or delete them.'}</p>}
      {activeMode === 'llm-only' && <p className="info-note"><FolderOpen size={17} />{t.freeModeDocs}</p>}
    </div>
    <footer className="documents-footer"><LockKeyhole size={15} /><span>{t.docScope}</span></footer>
  </Dialog>;
}

function UploadJourney({ status, progress, language }: { status: 'uploading' | 'processing'; progress: number; language: Language }) {
  const t = translations[language];
  const activeIndex = status === 'uploading' ? 0 : 1;
  const steps = [t.uploadSteps.transfer, t.uploadSteps.processing, t.uploadSteps.ready];
  return <div className="upload-journey" role="status" aria-label={status === 'uploading' ? `${t.uploadProgress}: ${progress}%` : t.docProcessing}>
    {status === 'uploading' ? <div className="upload-progress"><progress max="100" value={progress} /><output>{progress.toLocaleString(language)}٪</output></div> : null}
    <ol>{steps.map((step, index) => <li key={step} data-state={index < activeIndex ? 'complete' : index === activeIndex ? 'active' : 'pending'}>
      <i aria-hidden="true">{index < activeIndex ? <Check size={10} /> : null}</i><span>{step}</span>
    </li>)}</ol>
  </div>;
}

