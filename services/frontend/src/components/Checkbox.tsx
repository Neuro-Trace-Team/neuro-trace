import Icon from "./Icon";

type CheckboxProps = {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: string;
  className?: string;
  disabled?: boolean;
  showLabel?: boolean;
};

export default function Checkbox({
  checked,
  onChange,
  label,
  className = "",
  disabled = false,
  showLabel = true,
}: CheckboxProps) {
  return (
    <label className={`inline-flex cursor-pointer items-center gap-2 text-sm text-[#173456] ${disabled ? "cursor-not-allowed opacity-55" : ""} ${className}`}>
      <input
        aria-label={label}
        checked={checked}
        className="peer sr-only"
        disabled={disabled}
        onChange={(event) => onChange(event.target.checked)}
        type="checkbox"
      />
      <span className="flex h-[18px] w-[18px] shrink-0 items-center justify-center rounded-[5px] border border-[#aebfc8] bg-white shadow-[inset_0_1px_2px_rgba(8,38,76,0.07)] transition peer-checked:border-[#008da6] peer-checked:bg-gradient-to-br peer-checked:from-[#00b7bf] peer-checked:to-[#0876b5] peer-focus-visible:outline peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-[#00a9c4] peer-disabled:bg-[#edf1f3]">
        {checked ? <Icon className="h-3.5 w-3.5 text-white" name="check" /> : <Icon className="h-3.5 w-3.5 text-transparent" name="check" />}
      </span>
      <span className={showLabel ? "" : "sr-only"}>{label}</span>
    </label>
  );
}
