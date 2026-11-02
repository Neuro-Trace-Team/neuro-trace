import { useState, type FormEvent } from "react";
import ButtonPrimary from "./ButtonPrimary";
import ButtonSecondary from "./ButtonSecondary";
import InputSection from "./InputSection";
import Modal from "./Modal";
import { getApiErrorMessage } from "../services/apiClient";
import { useToast } from "../context/useToast";

export type CreateUserInput = {
  first_name: string;
  last_name: string;
  email: string;
  password: string;
  role: "DOCTOR";
};

export default function AdminCreateUserModal({
  onClose,
  onCreate,
}: {
  onClose: () => void;
  onCreate: (user: CreateUserInput) => Promise<void>;
}) {
  const role = "Doctor";
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { showToast } = useToast();

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setIsSubmitting(true);
    try {
      await onCreate({
      first_name: String(form.get("firstName")),
      last_name: String(form.get("lastName")),
      email: String(form.get("email")),
      password: String(form.get("password")),
      role: "DOCTOR",
      });
      showToast("Doctor account created successfully.", "success");
    } catch (createError) {
      showToast(getApiErrorMessage(createError, "Could not create the account."), "error");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal
      className="max-w-[624px]"
      description="Create a physician account."
      onClose={onClose}
      title="Create New Account"
    >
      <form className="space-y-4" onSubmit={submit}>
          <p className="text-[14px] leading-[21px] text-[#102d58]">
            Create a physician account with a temporary password. The backend does not send invitation emails.
          </p>
          <div className="grid gap-4 sm:grid-cols-2">
            <InputSection label="Name" name="firstName" placeholder="Name" required />
            <InputSection label="Surname" name="lastName" placeholder="Surname" required />
          </div>
          <InputSection label="Email address" name="email" placeholder="Email address" required type="email" />
          <fieldset>
            <legend className="mb-1.5 text-[14px] font-semibold">Role</legend>
            <div className="grid grid-cols-2 gap-3">
              {(["Doctor", "Admin"] as const).map((option) => (
                <ButtonSecondary
                  aria-pressed={role === option}
                  className={`h-[42px] justify-start text-left ${role === option ? "border-[#9adce3] bg-[#e8f8fa] text-[#07516a]" : ""}`}
                  disabled={option === "Admin"}
                  key={option}
                  type="button"
                >
                  {option}
                </ButtonSecondary>
              ))}
            </div>
          </fieldset>
          <InputSection label="Temporary password" minLength={12} name="password" placeholder="At least 12 characters" required type="password" />
          <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
            <ButtonSecondary onClick={onClose} type="button">Cancel</ButtonSecondary>
            <ButtonPrimary disabled={isSubmitting} type="submit">
              {isSubmitting ? "CREATING ACCOUNT..." : "CREATE ACCOUNT"}
            </ButtonPrimary>
          </div>
      </form>
    </Modal>
  );
}
