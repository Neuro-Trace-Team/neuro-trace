function ButtonInline({ children, className, ...props }: { children: React.ReactNode; className?: string } & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      className={`self-end bg-transparent p-0 text-[14px] font-normal text-white/90 transition hover:text-white focus-visible:rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/80 ${className || ''}`}
      {...props}
    >
      {children}
    </button>
  );
}

export default ButtonInline;