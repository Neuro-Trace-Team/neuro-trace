import type { ReactNode } from "react";
import GlassPane from "./GlassPane";

export default function Surface({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <GlassPane as="section" className={`p-4 sm:p-5 ${className}`}>
      {children}
    </GlassPane>
  );
}
