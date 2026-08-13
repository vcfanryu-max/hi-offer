import Link from "next/link";

export function BrandMark() {
  return (
    <span className="brand-mark" aria-hidden="true">
      <svg viewBox="0 0 36 36">
        <path d="M8 10h20M6 15h24M10 20h18M8 25h20" />
        <path d="M12 6l-4 23M24 6l4 23" />
      </svg>
    </span>
  );
}

export function BrandHeader({ action }: { action?: { href: string; label: string } }) {
  return (
    <header className="brand-header">
      <Link href="/" className="brand-lockup" aria-label="返回 Resume Matcher 首页">
        <BrandMark />
        <span>Resume Matcher</span>
      </Link>
      {action ? (
        <Link className="header-action" href={action.href}>
          {action.label}
        </Link>
      ) : (
        <span className="local-badge">LOCAL · PRIVATE</span>
      )}
    </header>
  );
}
