import { NavLink, useNavigate } from "react-router-dom";
import type { UserRole } from "../types/user.types";
import { useAuth } from "../context/AuthContext";
import Icon from "./Icon";

const doctorLinks = [
  { label: "Home", path: "/doctor", icon: "home" },
  { label: "Examinations", path: "/doctor/examinations", icon: "grid" },
  { label: "Enter new examination", path: "/doctor/examinations/new", icon: "add" },
] as const;

const adminLinks = [
  { label: "Home", path: "/admin", icon: "home" },
  { label: "Database", path: "/admin/database", icon: "database" },
  { label: "Users", path: "/admin/users", icon: "users" },
  { label: "Activity log", path: "/admin/activity-log", icon: "activity" },
] as const;

export default function AppSidebar({ role }: { role: UserRole }) {
  const { logout } = useAuth();
  const navigate = useNavigate();
  const links = role === "admin" ? adminLinks : doctorLinks;

  const logoutAndNavigate = () => {
    logout();
    navigate("/auth/login", { replace: true });
  };

  return (
    <aside className="relative z-20 flex w-full shrink-0 flex-col border-b border-white/80 bg-white/55 px-4 py-3 shadow-[0_0_16px_rgba(10,40,60,0.08)] backdrop-blur-md md:min-h-svh md:w-[200px] md:border-b-0 md:border-r md:px-[18px] md:pb-6 md:pt-10">
      <NavLink
        aria-label="NeuroTrace home"
        className="mx-auto mb-2 flex h-12 w-12 items-center justify-center md:mb-8 md:h-[104px] md:w-[104px]"
        to={role === "admin" ? "/admin" : "/doctor"}
      >
        <img alt="" className="h-full w-full object-contain" src="/favicon-light.svg" />
      </NavLink>
      <nav aria-label="Main navigation" className="flex gap-1 overflow-x-auto md:flex-1 md:flex-col md:gap-1.5">
        {links.map(({ label, path, icon }) => (
          <NavLink
            end
            key={path}
            to={path}
            className={({ isActive }) =>
              `flex min-h-[42px] shrink-0 items-center gap-2 rounded-lg px-2 text-[15px] font-semibold transition-colors md:px-2 ${
                isActive
                  ? "border border-white/85 bg-white/45 text-[#06234e] shadow-[0_2px_4px_rgba(0,30,60,0.22)]"
                  : "text-[#09264d] hover:bg-white/45"
              }`
            }
          >
            <Icon className="h-[21px] w-[21px] shrink-0" name={icon} />
            <span className="whitespace-nowrap md:whitespace-normal md:leading-4">{label}</span>
          </NavLink>
        ))}
        <NavLink
          to="/settings"
          className={({ isActive }) =>
            `mt-0 flex min-h-[42px] shrink-0 items-center gap-2 rounded-lg px-2 text-[15px] font-semibold transition-colors md:mt-auto ${
              isActive
                ? "border border-white/85 bg-white/45 shadow-[0_2px_4px_rgba(0,30,60,0.22)]"
                : "hover:bg-white/45"
            }`
          }
        >
          <Icon className="h-[21px] w-[21px] shrink-0" name="settings" />
          <span>Settings</span>
        </NavLink>
        <button
          className="flex min-h-[42px] shrink-0 items-center gap-2 rounded-lg px-2 text-[15px] font-semibold hover:bg-white/45 focus-visible:outline-2 focus-visible:outline-[#00a9c4]"
          onClick={logoutAndNavigate}
          type="button"
        >
          <Icon className="h-[21px] w-[21px] shrink-0" name="logout" />
          <span>Log out</span>
        </button>
      </nav>
    </aside>
  );
}
