import type { ReactNode } from "react";

type GlassPaneProps = {
  children: ReactNode;
  className?: string;
  as?: "div" | "section";
};

function GlassPane({ children, className = "", as: Component = "div" }: GlassPaneProps) {
  return (
    <Component
      className={`
        relative 
        rounded-[8px] 
        border border-white/25 
        bg-white/[0.00] bg-gradient-to-br from-white/40 via-white/15 to-white/25
        shadow-[inset_0_1px_1px_rgba(255,255,255,0.85),inset_0_-1px_1px_rgba(255,255,255,0.25),0_3px_8px_rgba(5,45,65,0.22),0_12px_30px_rgba(5,65,90,0.08)]
        backdrop-blur-[24px] backdrop-saturate-[135%]
        before:pointer-events-none before:absolute before:inset-0 before:rounded-[inherit]
        before:bg-gradient-to-b before:from-white/20 before:via-transparent before:to-transparent
        before:content-[''] ${className}`}
    >
      {children}
    </Component>
  );
}

export default GlassPane;
