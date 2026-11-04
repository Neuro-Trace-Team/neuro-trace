import { useState } from "react";
import Icon from "../components/Icon";
import { PageTitle, SectionTitle, Surface } from "../components/PageUI";
import { useAuth } from "../context/AuthContext";

const accountFields = [
  { key: "firstName", label: "First Name" },
  { key: "lastName", label: "Last Name" },
  { key: "email", label: "Email address" },
  { key: "password", label: "Password" },
] as const;

function SettingsPage() {
  const { user } = useAuth();
  const [editing, setEditing] = useState<string | null>(null);
  const [theme, setTheme] = useState(() => {
    const savedTheme = localStorage.getItem("theme");
    return savedTheme === "dark" ? "Dark" : savedTheme === "light" ? "Light" : "System";
  });
  const [language, setLanguage] = useState("English");
  const [details, setDetails] = useState({
    firstName: user?.firstName || "Alice",
    lastName: user?.lastName || "Smith",
    email: user?.email || "email123@gmail.com",
    password: "********",
  });

  return (
    <div className="mx-auto max-w-[1100px]">
      <PageTitle>Settings</PageTitle>
      <div className="space-y-5">
        <Surface className="min-h-[315px]">
          <SectionTitle>Account Details</SectionTitle>
          <div className="mt-7 max-w-[480px] space-y-4">
            {accountFields.map(({ key, label }) => (
              <div className="grid grid-cols-[105px_minmax(0,1fr)_32px] items-center gap-3 text-[13px]" key={key}>
                <span>{label}:</span>
                {editing === key ? (
                  <input
                    autoFocus
                    className="h-8 min-w-0 rounded border border-[#d1d8db] bg-white/80 px-2 font-semibold outline-none focus:border-[#00a9c4]"
                    onChange={(event) => setDetails((current) => ({ ...current, [key]: event.target.value }))}
                    onKeyDown={(event) => event.key === "Enter" && setEditing(null)}
                    type={key === "password" ? "password" : key === "email" ? "email" : "text"}
                    value={details[key]}
                  />
                ) : (
                  <strong className="truncate text-[13px]">{details[key]}</strong>
                )}
                <button
                  aria-label={`${editing === key ? "Save" : "Edit"} ${label}`}
                  className="rounded p-1 text-[#09264d] hover:bg-white/60 focus-visible:outline-2 focus-visible:outline-[#00a9c4]"
                  onClick={() => setEditing(editing === key ? null : key)}
                  type="button"
                >
                  <Icon className="h-4 w-4" name={editing === key ? "check" : "edit"} />
                </button>
              </div>
            ))}
            <div className="grid grid-cols-[105px_minmax(0,1fr)_32px] items-center gap-3 text-[13px]">
              <span>Role:</span>
              <strong>{user?.role === "admin" ? "Admin" : "Doctor"}</strong>
              <Icon className="h-4 w-4 text-[#aeb8c0]" name="edit" />
            </div>
          </div>
        </Surface>
        <Surface className="min-h-[205px]">
          <SectionTitle>App Settings</SectionTitle>
          <div className="mt-7 space-y-4">
            <label className="flex items-center gap-5 text-[13px]">
              <span className="w-[68px]">Language:</span>
              <select className="h-8 min-w-[138px] rounded-full bg-white/80 px-3 font-bold text-[#09264d] outline-none focus:ring-2 focus:ring-[#00a9c4]" onChange={(event) => setLanguage(event.target.value)} value={language}>
                <option>English</option><option>Polski</option>
              </select>
            </label>
            <label className="flex items-center gap-5 text-[13px]">
              <span className="w-[68px]">Theme:</span>
              <select
                className="h-8 min-w-[138px] rounded-full bg-white/80 px-3 font-bold text-[#09264d] outline-none focus:ring-2 focus:ring-[#00a9c4]"
                onChange={(event) => {
                  setTheme(event.target.value);
                  localStorage.setItem("theme", event.target.value.toLowerCase());
                  document.documentElement.dataset.theme = event.target.value.toLowerCase();
                  document.documentElement.classList.toggle(
                    "dark",
                    event.target.value === "Dark" ||
                      (event.target.value === "System" &&
                        window.matchMedia("(prefers-color-scheme: dark)").matches),
                  );
                }}
                value={theme}
              >
                <option>System</option><option>Light</option><option>Dark</option>
              </select>
            </label>
          </div>
        </Surface>
      </div>
    </div>
  );
}

export default SettingsPage;
