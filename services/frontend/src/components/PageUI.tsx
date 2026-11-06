import type { ReactNode } from "react";
import InputSection from "./InputSection";

export function PageTitle({ children }: { children: ReactNode }) {
  return (
    <h1 className="mb-5 font-heading text-[30px] font-extrabold uppercase leading-tight tracking-[0.2px] text-[#06234e] sm:text-[34px]">
      {children}
    </h1>
  );
}

export function Surface({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={`rounded-[9px] border border-white/70 bg-white/[0.42] p-4 shadow-[0_3px_5px_rgba(0,0,0,0.22),inset_0_1px_0_rgba(255,255,255,0.6)] backdrop-blur-[8px] sm:p-5 ${className}`}
    >
      {children}
    </section>
  );
}

export function SectionTitle({ children }: { children: ReactNode }) {
  return (
    <h2 className="mb-3 text-[22px] font-semibold leading-tight text-[#08264c] sm:text-[25px]">
      {children}
    </h2>
  );
}

export function FormField({
  label,
  className = "",
  inputClassName = "",
  ...props
}: Omit<React.InputHTMLAttributes<HTMLInputElement>, "className"> & {
  label: string;
  className?: string;
  inputClassName?: string;
}) {
  const id = props.id ?? props.name ?? label.toLowerCase().replaceAll(" ", "-");
  return (
    <InputSection
      {...props}
      className={className}
      id={id}
      inputClassName={inputClassName}
      label={label}
    />
  );
}
