/** The release this page was built from: the project's VERSION, set in a meta tag by Vite. */
export const APP_VERSION = (typeof document !== 'undefined'
  && document.querySelector<HTMLMetaElement>('meta[name="parsrag-version"]')?.content) || '0.0.0';
