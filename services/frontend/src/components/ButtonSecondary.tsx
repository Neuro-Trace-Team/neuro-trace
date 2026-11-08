import type { ButtonHTMLAttributes, ReactNode, Ref } from "react";
import Icon, { type IconName } from "./Icon";

type ButtonSecondaryProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  children?: ReactNode;
  className?: string;
  icon?: IconName;
  iconPosition?: "start" | "end";
  iconOnly?: boolean;
  ref?: Ref<HTMLButtonElement>;
};

export default function ButtonSecondary({
  children,
  className = "",
  icon,
  iconPosition = "start",
  iconOnly = false,
  ref,
  ...props
}: ButtonSecondaryProps) {
  return (
    <button
      className={`inline-flex min-h-9 items-center justify-center gap-2 rounded-lg border border-[#d6e1e6] bg-white/75 px-3 py-1.5 text-sm font-semibold text-[#173456] shadow-[0_1px_2px_rgba(8,38,76,0.06)] transition duration-150 hover:border-[#9bcbd2] hover:bg-[#effafb] hover:text-[#07516a] active:scale-[0.98] active:bg-[#dff4f5] active:shadow-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#00a9c4] focus-visible:ring-offset-2 disabled:pointer-events-none disabled:cursor-not-allowed disabled:bg-[#edf1f3] disabled:text-[#84919b] disabled:shadow-none motion-reduce:transition-none ${iconOnly ? "w-9 px-0" : ""} ${className}`}
      ref={ref}
      {...(iconOnly && !children && icon ? { "aria-label": props["aria-label"] ?? icon } : {})}
      {...props}
    >
      {icon && iconPosition === "start" && <Icon className="h-4 w-4 shrink-0" name={icon} />}
      {children}
      {icon && iconPosition === "end" && <Icon className="h-4 w-4 shrink-0" name={icon} />}
    </button>
  );
}
