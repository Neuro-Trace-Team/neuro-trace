import { useRef, useState, type ChangeEventHandler, type InputHTMLAttributes } from "react";
import ButtonSecondary from "./ButtonSecondary";
import Icon, { type IconName } from "./Icon";

type InputSectionProps = Omit<InputHTMLAttributes<HTMLInputElement>, "type" | "className" | "onChange"> & {
    label?: string;
    type?: React.HTMLInputTypeAttribute;
    icon?: IconName;
    className?: string;
    inputClassName?: string;
    onChange?: ChangeEventHandler<HTMLInputElement>;
    onClear?: () => void;
};

function InputSection({
    onChange,
    label = "",
    name,
    placeholder = "",
    type = "text",
    autoComplete,
    required,
    className,
    inputClassName = "",
    icon,
    value,
    onClear,
    ...inputProps
}: InputSectionProps) {
    const [passwordVisible, setPasswordVisible] = useState(false);
    const inputRefInternal = useRef<HTMLInputElement>(null);
    const isSearch = type === "search";
    const isPassword = type === "password";
    const leadingIcon = icon ?? (isSearch ? "search" : undefined);

    const clearSearch = () => {
        if (onClear) {
            onClear();
            return;
        }
        const input = inputRefInternal.current;
        if (!input) return;
        const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
        setter?.call(input, "");
        input.dispatchEvent(new Event("input", { bubbles: true }));
    };
    return (
        <div className={`flex min-w-0 flex-col gap-1 ${className ?? ""}`}>
            {label && <label htmlFor={name} className="text-[14px] font-semibold leading-[18px] text-[#08264c]">{label}</label>}
            <span className="relative block min-w-0">
                {leadingIcon && <Icon className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#718096]" name={leadingIcon} />}
                <input
                    {...inputProps}
                    autoComplete={autoComplete}
                    className={`h-10 w-full rounded-lg border border-[#d6e1e6] bg-white/80 px-3 text-[13px] text-[#173456] shadow-[inset_0_1px_3px_rgba(8,38,76,0.08)] outline-none transition placeholder:text-[#8997a2] focus:border-[#00a9c4] focus:ring-2 focus:ring-[#00b7c8]/15 disabled:cursor-not-allowed disabled:bg-[#e9eef0] disabled:text-[#84919b] ${leadingIcon ? "pl-10" : ""} ${isPassword || isSearch ? "pr-11" : ""} ${inputClassName}`}
                    id={name}
                    name={name}
                    onChange={onChange}
                    placeholder={placeholder}
                    ref={inputRefInternal}
                    required={required}
                    type={isPassword && passwordVisible ? "text" : type}
                    value={value}
                />
                {isPassword && (
                    <ButtonSecondary
                        aria-label={passwordVisible ? "Hide password" : "Show password"}
                        className="absolute right-1 top-1/2 h-8 w-8 -translate-y-1/2 border-0 bg-transparent p-0 shadow-none"
                        icon={passwordVisible ? "eyeOff" : "eye"}
                        iconOnly
                        onClick={() => setPasswordVisible((visible) => !visible)}
                        type="button"
                    />
                )}
                {isSearch && Boolean(value) && (
                    <ButtonSecondary
                        aria-label="Clear search"
                        className="absolute right-1 top-1/2 h-8 w-8 -translate-y-1/2 border-0 bg-transparent p-0 shadow-none"
                        icon="close"
                        iconOnly
                        onClick={clearSearch}
                        type="button"
                    />
                )}
            </span>
        </div>
    );
}

export default InputSection;