type InputSectionProps = {
    onChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
    label: string;
    name: string;
    placeholder: string;
    type?: React.HTMLInputTypeAttribute;
    autoComplete?: string;
    required?: boolean;
    className?: string;
};

function InputSection({
    onChange,
    label,
    name,
    placeholder,
    type = "text",
    autoComplete,
    required,
    className,
}: InputSectionProps) {
    return (
        <div className={`flex flex-col gap-[3px] ${className || ''}`}>
            <label htmlFor={name} className="text-[14px] font-semibold leading-[18px] text-[#08264c]">
                {label}
            </label>
            <input
                type={type}
                id={name}
                name={name}
                placeholder={placeholder}
                autoComplete={autoComplete}
                required={required}
                onChange={onChange}
                className="h-8 w-full rounded-[7px] border border-white/70 bg-white/65 px-[10px] text-[14px] leading-none text-[#17384e] shadow-[inset_0_1px_2px_rgba(6,37,75,0.08)] placeholder:text-[#858f93] focus:border-[#008eae] focus:outline-none focus:ring-2 focus:ring-[#00b7c8]/25"
            />
        </div>
    );
}

export default InputSection;