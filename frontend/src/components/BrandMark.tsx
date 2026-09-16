export function BrandMark({ className = '' }: { className?: string }) {
  return <svg className={`brand-mark ${className}`} viewBox="0 0 48 48" fill="none" aria-hidden="true">
    <path d="M24 11C18 5 10 7 7 10v24c5-3 11-2 17 4V11Z" fill="currentColor" opacity=".28" />
    <path d="M24 11c6-6 14-4 17-1v24c-5-3-11-2-17 4V11Z" fill="currentColor" opacity=".7" />
    <path d="M24 37V14M12 15c3-1 6 0 8 2m-8 5c3-1 6 0 8 2m8-7c2-2 5-3 8-2m-8 9c2-2 5-3 8-2" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    <path d="m24 2 2 4-2 4-2-4 2-4Z" fill="currentColor" />
  </svg>;
}
