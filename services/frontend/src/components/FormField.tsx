import InputSection from "./InputSection";

export default function FormField({
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
