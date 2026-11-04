import { useState, type FormEvent } from "react";
import Icon from "./Icon";
import { SmallButton } from "./PageUI";

export type ManagedUser = {
  name: string;
  email: string;
  role: string;
  lastLogin: string;
};

export default function AdminCreateUserModal({
  onClose,
  onCreate,
}: {
  onClose: () => void;
  onCreate: (user: ManagedUser) => void;
}) {
  const [showPassword, setShowPassword] = useState(false);
  const role = "Doctor";

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    onCreate({
      name: `${form.get("firstName")} ${form.get("lastName")}`,
      email: String(form.get("email")),
      role,
      lastLogin: "Never",
    });
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-[#061d36]/35 p-4 backdrop-blur-[2px]"
      onMouseDown={(event) => event.target === event.currentTarget && onClose()}
    >
      <section aria-labelledby="create-account-title" aria-modal="true" className="max-h-[calc(100svh-2rem)] w-full max-w-[624px] overflow-y-auto rounded-[8px] bg-[#f4f6f6] shadow-[0_12px_40px_rgba(0,20,40,0.3)]" role="dialog">
        <header className="flex h-[60px] items-center justify-between bg-gradient-to-r from-[#00b9c5] to-[#0071b4] px-6 text-white">
          <h2 className="text-[23px] font-semibold" id="create-account-title">Create New Account</h2>
          <button aria-label="Close dialog" className="rounded p-1 hover:bg-white/15 focus-visible:outline-2 focus-visible:outline-white" onClick={onClose} type="button">
            <Icon className="h-5 w-5" name="close" />
          </button>
        </header>
        <form className="space-y-4 px-6 pb-5 pt-6" onSubmit={submit}>
          <p className="text-[14px] leading-[21px] text-[#102d58]">
            Create a physician account and email an invitation. The user must change their temporary password on first sign-in.
          </p>
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="space-y-1 text-[14px] font-semibold">Name<input className="h-[39px] w-full rounded-md border border-[#d6d9dc] bg-white px-3 font-normal outline-none focus:border-[#009bb4]" name="firstName" placeholder="Name" required /></label>
            <label className="space-y-1 text-[14px] font-semibold">Surname<input className="h-[39px] w-full rounded-md border border-[#d6d9dc] bg-white px-3 font-normal outline-none focus:border-[#009bb4]" name="lastName" placeholder="Surname" required /></label>
          </div>
          <label className="block space-y-1 text-[14px] font-semibold">Email address<input className="h-[39px] w-full rounded-md border border-[#d6d9dc] bg-white px-3 font-normal outline-none focus:border-[#009bb4]" name="email" placeholder="Email address" required type="email" /></label>
          <fieldset>
            <legend className="mb-1.5 text-[14px] font-semibold">Role</legend>
            <div className="grid grid-cols-2 gap-3">
              {(["Doctor", "Admin"] as const).map((option) => (
                <button
                  aria-pressed={role === option}
                  className={`h-[42px] rounded-md text-left px-4 text-[14px] font-bold ${role === option ? "border border-white bg-white shadow-[0_2px_4px_rgba(0,0,0,0.2)]" : "bg-[#dedfe0] text-[#73777a]"}`}
                  disabled={option === "Admin"}
                  key={option}
                  type="button"
                >
                  {option}
                </button>
              ))}
            </div>
          </fieldset>
          <label className="block space-y-1 text-[14px] font-semibold">Temporary password
            <span className="relative block">
              <input className="h-[39px] w-full rounded-md border border-[#d6d9dc] bg-white px-3 pr-11 font-normal outline-none focus:border-[#009bb4]" name="password" placeholder="Temporary password" required type={showPassword ? "text" : "password"} />
              <button aria-label={showPassword ? "Hide password" : "Show password"} className="absolute right-3 top-1/2 -translate-y-1/2" onClick={() => setShowPassword((value) => !value)} type="button">
                <Icon className="h-5 w-5" name="eye" />
              </button>
            </span>
          </label>
          <div className="flex flex-wrap items-center justify-between gap-3 pt-4">
            <SmallButton onClick={onClose} type="button">Cancel</SmallButton>
            <button className="min-h-[42px] rounded-full bg-gradient-to-r from-[#00bdc5] to-[#0071b4] px-4 text-[13px] font-bold text-white shadow-md hover:brightness-105 focus-visible:outline-2 focus-visible:outline-[#06234e]" type="submit">
              SEND INVITATION AND CREATE ACCOUNT
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
