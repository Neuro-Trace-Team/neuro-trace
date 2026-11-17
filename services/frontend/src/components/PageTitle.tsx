import type { ReactNode } from "react";

export default function PageTitle({ children }: { children: ReactNode }) {
  return (
    <h1 className="mb-5 font-heading text-[30px] font-extrabold uppercase leading-tight tracking-[0.2px] text-[#06234e] sm:text-[34px]">
      {children}
    </h1>
  );
}
