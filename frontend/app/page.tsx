import { BrandHeader } from "@/components/BrandHeader";
import { Hero } from "@/components/Hero";

export default function LandingPage() {
  const demoMode = process.env.NEXT_PUBLIC_DEMO_MODE === "true";
  return (
    <div className="page-shell landing-page">
      <BrandHeader />
      <Hero />
      <footer className="landing-footer">
        <span>{demoMode ? "PORTFOLIO DEMO" : "Local-first"}</span>
        <span>{demoMode ? "虚构数据 · 无上传 · 无模型费用" : "数据留在你的电脑"}</span>
      </footer>
    </div>
  );
}
