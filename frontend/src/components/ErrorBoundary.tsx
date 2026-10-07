import { Component, type ErrorInfo, type ReactNode } from 'react';

interface ErrorBoundaryState { failed: boolean }

/**
 * Replace a blank page with a way out when rendering fails. Conversations are
 * already stored, so reloading loses nothing.
 */
export class ErrorBoundary extends Component<{ children: ReactNode }, ErrorBoundaryState> {
  state: ErrorBoundaryState = { failed: false };

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error('ParsRAG interface error', error, info.componentStack);
  }

  render(): ReactNode {
    if (!this.state.failed) return this.props.children;
    const persian = (globalThis.document?.documentElement.lang ?? 'fa') !== 'en';
    return <main className="crash-screen" role="alert" dir={persian ? 'rtl' : 'ltr'}>
      <h1>{persian ? 'نمایش صفحه با خطا روبه‌رو شد' : 'Something went wrong while showing the page'}</h1>
      <p>{persian ? 'گفت‌وگوها و اسناد شما ذخیره شده‌اند. صفحه را دوباره بارگذاری کنید.' : 'Your conversations and documents are saved. Reload the page to continue.'}</p>
      <button type="button" className="button primary" onClick={() => window.location.reload()}>{persian ? 'بارگذاری دوباره' : 'Reload'}</button>
    </main>;
  }
}
