function ButtonPrimary({ children, className, ...props }: { children: React.ReactNode; className?: string } & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      className={`h-[42px] w-full rounded-[17px] bg-gradient-to-r from-[#03bdc8] to-[#006db4] px-4 text-[16px] font-bold text-white shadow-[0_3px_6px_rgba(0,100,160,0.2)] transition hover:brightness-105 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#06234e] focus-visible:ring-offset-2 ${className || ''}`}
      {...props}
    >
      {children}
    </button>
  );
}

export default ButtonPrimary;