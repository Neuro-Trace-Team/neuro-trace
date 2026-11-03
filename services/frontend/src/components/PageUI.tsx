import type { ReactNode } from "react";

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

export function SmallButton({
  children,
  className = "",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      className={`inline-flex min-h-8 items-center justify-center gap-1.5 rounded-md border border-white/90 bg-white/80 px-3 py-1.5 text-[13px] font-semibold text-[#09264d] shadow-[0_2px_3px_rgba(0,0,0,0.2)] transition hover:bg-white focus-visible:outline-2 focus-visible:outline-[#00a9c4] disabled:cursor-not-allowed disabled:opacity-50 ${className}`}
      {...props}
    >
      {children}
    </button>
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
    <label className={`flex flex-col gap-1.5 text-[14px] font-semibold text-[#08264c] ${className}`} htmlFor={id}>
      {label}
      <input
        {...props}
        className={`h-9 rounded-md border border-[#d5d9db] bg-white/80 px-3 font-normal outline-none placeholder:text-[#858f93] focus:border-[#009bb4] focus:ring-2 focus:ring-[#00b7c8]/20 ${inputClassName}`}
        id={id}
      />
    </label>
  );
}
