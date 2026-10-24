import type { Language, ReleaseNote } from '../types';
import { translations } from '../i18n/translations';
import { Dialog } from './Dialog';
import { ReleaseNotesText } from './ReleaseNotesText';

/** Shown once after an update: what changed in every version since the last one seen. */
export function WhatsNewDialog({ notes, currentVersion, language, onClose }: {
  notes: ReleaseNote[]; currentVersion: string; language: Language; onClose: () => void;
}) {
  const t = translations[language];
  return <Dialog open onClose={onClose} title={t.whatsNewTitle.replace('{version}', currentVersion)} closeLabel={t.close} className="whats-new-dialog">
    <div className="dialog-body">
      {notes.map(note => <section key={note.version} className="whats-new-version">
        {notes.length > 1 && <h3 dir="ltr">{note.version}</h3>}
        <ReleaseNotesText text={note.notes} language={language} />
      </section>)}
      <div className="dialog-actions"><button type="button" className="button primary" data-autofocus onClick={onClose}>{t.whatsNewDone}</button></div>
    </div>
  </Dialog>;
}
