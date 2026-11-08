import type { ButtonHTMLAttributes, ReactNode } from "react";
import Icon, { type IconName } from "./Icon";

type ButtonPrimaryProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  children: ReactNode;
  className?: string;
  icon?: IconName;
  iconPosition?: "start" | "end";
};

function ButtonPrimary({
  children,
  className = "",
  icon,
  iconPosition = "start",
  ...props
}: ButtonPrimaryProps) {
  return (
    <button
      className={`inline-flex min-h-10 items-center justify-center gap-2 rounded-lg bg-gradient-to-r from-[#00aeb8] to-[#0876b5] px-4 py-2 text-sm font-bold text-white shadow-[0_2px_5px_rgba(0,87,135,0.18)] transition duration-150 hover:brightness-105 hover:shadow-[0_4px_10px_rgba(0,87,135,0.22)] active:translate-y-px active:brightness-95 active:shadow-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#06234e] focus-visible:ring-offset-2 disabled:pointer-events-none disabled:translate-y-0 disabled:cursor-not-allowed disabled:opacity-50 disabled:shadow-none motion-reduce:transition-none ${className}`}
      {...props}
    >
      {icon && iconPosition === "start" && <Icon className="h-4 w-4 shrink-0" name={icon} />}
      {children}
      {icon && iconPosition === "end" && <Icon className="h-4 w-4 shrink-0" name={icon} />}
    </button>
  );
}

export default ButtonPrimary;