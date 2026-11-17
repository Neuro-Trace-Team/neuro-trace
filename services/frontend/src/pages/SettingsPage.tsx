import { useEffect, useState, type FormEvent } from "react";
import ButtonPrimary from "../components/ButtonPrimary";
import ButtonSecondary from "../components/ButtonSecondary";
import InputSection from "../components/InputSection";
import PageTitle from "../components/PageTitle";
import SectionTitle from "../components/SectionTitle";
import Surface from "../components/Surface";
import { useAuth } from "../context/useAuth";
import { useToast } from "../context/useToast";
import { apiClient, getApiErrorMessage } from "../services/apiClient";
import { useNavigate } from "react-router-dom";
import type { ApiUser } from "../types/api.types";
import { mapApiUser } from "../services/api";

const accountFields = [
  { key: "firstName", label: "First Name" },
  { key: "lastName", label: "Last Name" },
  { key: "email", label: "Email address" },
] as const;

function SettingsPage() {
  const { user, updateUser, logout } = useAuth();
  const navigate = useNavigate();
  const [editing, setEditing] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const displayAppSettings = false; // Set to true to display app settings
  const { showToast } = useToast();
  const [theme, setTheme] = useState(() => {
    const savedTheme = localStorage.getItem("theme");
    return savedTheme === "dark" ? "Dark" : savedTheme === "light" ? "Light" : "System";
  });
  const [language, setLanguage] = useState("English");
  const [details, setDetails] = useState({
    firstName: user?.firstName || "",
    lastName: user?.lastName || "",
    email: user?.email || "",
  });

  useEffect(() => {
    localStorage.setItem("theme", theme.toLowerCase());
    window.dispatchEvent(new Event("neurotrace-theme"));
  }, [theme]);

  const saveField = async (key: (typeof accountFields)[number]["key"]) => {
    const fieldMap = {
      firstName: "first_name",
      lastName: "last_name",
      email: "email",
    } as const;
    setIsSaving(true);
    try {
      const { data } = await apiClient.patch<ApiUser>("/users/me", { [fieldMap[key]]: details[key] });
      const updatedUser = mapApiUser(data);
      updateUser(updatedUser);
      setDetails({
        firstName: updatedUser.firstName,
        lastName: updatedUser.lastName,
        email: updatedUser.email,
      });
      setEditing(null);
      showToast("Account details saved.", "success");
    } catch (saveError) {
      showToast(getApiErrorMessage(saveError, "Could not save account details."), "error");
    } finally {
      setIsSaving(false);
    }
  };

  const changePassword = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    try {
      await apiClient.post("/auth/change-password", {
        current_password: currentPassword,
        new_password: newPassword,
      });
      showToast("Password changed successfully. Please sign in with your new password.", "success");
      await logout(false);
      navigate("/auth/login", { replace: true });
    } catch (passwordError) {
      showToast(getApiErrorMessage(passwordError, "Could not change the password."), "error");
    }
  };

  const selectTheme = (selectedTheme: string) => {
    setTheme(selectedTheme);
  };

  return (
    <div className="mx-auto max-w-[1100px]">
      <PageTitle>Settings</PageTitle>
      <div className="grid gap-5 lg:grid-cols-[1.1fr_0.9fr]">
        <Surface className="border-white/80 bg-gradient-to-br from-white/65 to-[#e9f5f7]/55 shadow-[0_6px_18px_rgba(8,38,76,0.09)]">
          <SectionTitle>Account Details</SectionTitle>
          <div className="max-w-[600px] divide-y divide-white overflow-hidden rounded-xl border border-white/80 bg-white/45 px-4">
            {accountFields.map(({ key, label }) => (
              <div className="grid grid-cols-[minmax(95px,0.4fr)_minmax(0,1fr)_36px] items-center gap-3 py-3 text-[13px]" key={key}>
                <span className="font-medium text-[#52677b]">{label}</span>
                {editing === key ? (
                  <InputSection
                    autoFocus
                    className="min-w-0"
                    inputClassName="h-9 font-semibold text-[#102d58]"
                    label=""
                    onChange={(event) => setDetails((current) => ({ ...current, [key]: event.target.value }))}
                    onKeyDown={(event) => event.key === "Enter" && void saveField(key)}
                    name={`settings-${key}`}
                    type={key === "email" ? "email" : "text"}
                    value={details[key]}
                  />
                ) : (
                  <strong className="truncate text-[13px] text-[#102d58]">{details[key]}</strong>
                )}
                <ButtonSecondary
                  aria-label={`${editing === key ? "Save" : "Edit"} ${label}`}
                  className="!min-h-0 h-9 w-9 border-0 bg-transparent p-0 shadow-none"
                  disabled={isSaving}
                  icon={editing === key ? "check" : "edit"}
                  iconOnly
                  onClick={() => editing === key ? void saveField(key) : setEditing(key)}
                  type="button"
                />
              </div>
            ))}
            <div className="grid grid-cols-[minmax(95px,0.4fr)_minmax(0,1fr)_36px] items-center gap-3 py-3 text-[13px]">
              <span className="font-medium text-[#52677b]">Role</span>
              <strong className="text-[#102d58]">{user?.role === "admin" ? "Admin" : "Doctor"}</strong>
              <ButtonSecondary
                  aria-label={"Edit role"}
                  className="!min-h-0 h-9 w-9 border-0 bg-transparent p-0 shadow-none"
                  disabled
                  icon={"edit"}
                  iconOnly
                  onClick={() => showToast("Role cannot be changed.", "error")}
                  type="button"
                />
            </div>
          </div>
        </Surface>
        <Surface className="border-white/80 bg-gradient-to-br from-white/65 to-[#e9f5f7]/55 shadow-[0_6px_18px_rgba(8,38,76,0.09)]">
          <SectionTitle>Change Password</SectionTitle>
          <form className="grid max-w-[480px] gap-4" onSubmit={changePassword}>
            <InputSection autoComplete="current-password" label="Current password" name="current-password" onChange={(event) => setCurrentPassword(event.target.value)} required type="password" value={currentPassword} />
            <InputSection autoComplete="new-password" label="New password (at least 12 characters)" minLength={12} name="new-password" onChange={(event) => setNewPassword(event.target.value)} required type="password" value={newPassword} />
            <ButtonPrimary className="w-fit" disabled={isSaving} type="submit">Change password</ButtonPrimary>
          </form>
        </Surface>
        {displayAppSettings && (
        <Surface className="border-white/80 bg-gradient-to-br from-white/65 to-[#e9f5f7]/55 shadow-[0_6px_18px_rgba(8,38,76,0.09)] lg:col-span-2">
          <SectionTitle>App Settings</SectionTitle>
          <div className="grid gap-6 sm:grid-cols-2">
            <fieldset>
              <legend className="mb-2 text-[13px] font-semibold text-[#173456]">Language</legend>
              <div className="flex flex-wrap gap-2">
                {["English", "Polski"].map((option) => (
                  <ButtonSecondary
                    aria-pressed={language === option}
                    className={language === option ? "border-[#9adce3] bg-[#e8f8fa] text-[#07516a]" : ""}
                    key={option}
                    onClick={() => setLanguage(option)}
                    type="button"
                  >
                    {option}
                  </ButtonSecondary>
                ))}
              </div>
              </fieldset>
            <fieldset>
              <legend className="mb-2 text-[13px] font-semibold text-[#173456]">Color theme</legend>
              <div className="flex flex-wrap gap-2">
                {["System", "Light", "Dark"].map((option) => (
                  <ButtonSecondary
                    aria-pressed={theme === option}
                    className={theme === option ? "border-[#9adce3] bg-[#e8f8fa] text-[#07516a]" : ""}
                    key={option}
                    onClick={() => selectTheme(option)}
                    type="button"
                  >
                    {option}
                  </ButtonSecondary>
                ))}
              </div>
            </fieldset>
          </div>
        </Surface>)}
      </div>
    </div>
  );
}

export default SettingsPage;
