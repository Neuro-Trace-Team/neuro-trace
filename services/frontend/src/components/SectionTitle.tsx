import type { ReactNode } from "react";

export default function SectionTitle({ children }: { children: ReactNode }) {
  return (
    <h2 className="mb-3 text-[22px] font-semibold leading-tight text-[#08264c] sm:text-[25px]">
      {children}
    </h2>
  );
}
