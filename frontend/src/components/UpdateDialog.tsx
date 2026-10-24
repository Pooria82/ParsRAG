import { useState } from 'react';
import { Check, Copy, Download, ExternalLink } from 'lucide-react';
import type { Language, UpdateStatus } from '../types';
import { translations } from '../i18n/translations';
import { releaseNotesText, updateCommand } from '../core/updates';
import { Dialog } from './Dialog';
import { ReleaseNotesText } from './ReleaseNotesText';

interface UpdateDialogProps {
  open: boolean;
  status: UpdateStatus;
  language: Language;
  onClose: () => void;
  /** Download the browser's conversations; the script backs up the server data. */
  onBackup: () => void;
  onSkip: (version: string) => void;
}

/** What a newer release brings, and the steps that back up and install it. */
export function UpdateDialog({ open, status, language, onClose, onBackup, onSkip }: UpdateDialogProps) {
  const t = translations[language];
  const [backedUp, setBackedUp] = useState(false);
  const [copied, setCopied] = useState(false);
  const latest = status.latest_version ?? '';
  const command = updateCommand(navigator.platform || navigator.userAgent);
  const copy = async () => {
    try { await navigator.clipboard.writeText(command); setCopied(true); } catch { setCopied(false); }
  };
  return <Dialog open={open} onClose={onClose} title={t.updateTitle.replace('{version}', latest)}
    subtitle={t.updateSubtitle.replace('{current}', status.current_version).replace('{latest}', latest)} closeLabel={t.close} className="update-dialog">
    <div className="dialog-body">
      <ol className="update-steps">
        <li><strong>{t.updateStepBackup}</strong><p>{t.updateStepBackupHint}</p>
          <button type="button" className="button secondary" onClick={() => { onBackup(); setBackedUp(true); }}>
            {backedUp ? <Check size={16} /> : <Download size={16} />}{backedUp ? t.updateBackedUp : t.exportBackup}</button></li>
        <li><strong>{t.updateStepRun}</strong><p>{t.updateStepRunHint}</p>
          <div className="update-command" aria-disabled={!backedUp || undefined}>
            <code dir="ltr">{command}</code>
            <button type="button" className="icon-button" disabled={!backedUp} onClick={() => void copy()} aria-label={t.copy} title={backedUp ? t.copy : t.updateBackupFirst}>
              {copied ? <Check size={15} /> : <Copy size={15} />}</button>
          </div>
          {!backedUp && <small>{t.updateBackupFirst}</small>}</li>
        <li><strong>{t.updateStepReload}</strong><p>{t.updateStepReloadHint}</p></li>
      </ol>
      <section className="update-releases" aria-label={t.updateChanges}>
        <h3>{t.updateChanges}</h3>
        {status.releases.map(release => <article key={release.version}>
          <header><strong dir="ltr">{release.version}</strong>
            {release.url && <a href={release.url} target="_blank" rel="noopener noreferrer">{t.updateOnGithub}<ExternalLink size={13} /></a>}</header>
          <ReleaseNotesText text={releaseNotesText(release, language)} language={language} />
        </article>)}
      </section>
      <div className="dialog-actions">
        <button type="button" className="button secondary" onClick={() => { onSkip(latest); onClose(); }}>{t.updateSkip}</button>
        <button type="button" className="button primary" onClick={onClose}>{t.close}</button>
      </div>
    </div>
  </Dialog>;
}
