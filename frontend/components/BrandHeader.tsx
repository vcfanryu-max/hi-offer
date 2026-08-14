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
  const demoMode = process.env.NEXT_PUBLIC_DEMO_MODE === "true";
  return (
    <header className="brand-header">
      <Link href="/" className="brand-lockup" aria-label="返回 Hi Offer 首页">
        <BrandMark />
        <span>Hi Offer</span>
      </Link>
      {action ? (
        <Link className="header-action" href={action.href}>
          {action.label}
        </Link>
      ) : (
        <span className="local-badge">{demoMode ? "PORTFOLIO · DEMO" : "LOCAL · PRIVATE"}</span>
      )}
    </header>
  );
}
