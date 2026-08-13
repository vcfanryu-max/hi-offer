import { BrandHeader } from "@/components/BrandHeader";
import { Hero } from "@/components/Hero";

export default function LandingPage() {
  return (
    <div className="page-shell landing-page">
      <BrandHeader />
      <Hero />
      <footer className="landing-footer">
        <span>Local-first</span>
        <span>数据留在你的电脑</span>
      </footer>
    </div>
  );
}

