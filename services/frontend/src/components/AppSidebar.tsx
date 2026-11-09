import { useId, useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import type { UserRole } from "../types/user.types";
import { useAuth } from "../context/useAuth";
import ButtonNavigation from "./ButtonNavigation";
import ButtonSecondary from "./ButtonSecondary";
import GlassPane from "./GlassPane";
import { useToast } from "../context/useToast";

const doctorLinks = [
  { label: "Home", path: "/doctor", icon: "home" },
  { label: "Examinations", path: "/doctor/examinations", icon: "examinations" },
  { label: "Enter new examination", path: "/doctor/examinations/new", icon: "new-examination" },
] as const;

const adminLinks = [
  { label: "Home", path: "/admin", icon: "home" },
  { label: "Database", path: "/admin/database", icon: "database" },
  { label: "Users", path: "/admin/users", icon: "users" },
  { label: "Activity log", path: "/admin/activity-log", icon: "activity" },
] as const;

export default function AppSidebar({ role }: { role: UserRole }) {
  const { logout } = useAuth();
  const { showToast } = useToast();
  const navigate = useNavigate();
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const navigationId = useId();
  const roleLinks = role === "admin" ? adminLinks : doctorLinks;


  const logoutAndNavigate = () => {
    void logout()
      .catch(() => {
        showToast("You were signed out on this device, but the backend session could not be revoked.", "error");
      })
      .finally(() => navigate("/auth/login", { replace: true }));
  };

  return (
    <aside className="sticky top-0 z-20 h-screen w-full shrink-0 md:min-h-svh md:w-[200px]">
      <GlassPane className="
      h-full flex flex-col gap-4 rounded-t-none rounded-b-[14px] 
      px-4 py-3 md:min-h-svh 
      md:gap-8 md:rounded-none md:border-y-0 md:border-l-0 md:border-r 
      md:px-[18px] md:pb-6 md:pt-10">
        <header className="flex items-center justify-between md:justify-center">
          <NavLink
            aria-label="NeuroTrace home"
            className="flex h-12 w-12 items-center justify-center md:h-[104px] md:w-[104px]"
            onClick={() => setIsMenuOpen(false)}
            to={role === "admin" ? "/admin" : "/doctor"}
          >
            <img alt="" className="h-full w-full object-contain" src="/favicon-light.svg" />
          </NavLink>
          <ButtonSecondary
            aria-controls={navigationId}
            aria-expanded={isMenuOpen}
            aria-label={isMenuOpen ? "Close navigation menu" : "Open navigation menu"}
            className="h-11 w-11 border-0 bg-transparent p-0 text-brand-navy shadow-none hover:bg-white/45 hover:text-brand-navy md:hidden"
            iconOnly
            onClick={() => setIsMenuOpen((open) => !open)}
            type="button"
          >
            <span
              aria-hidden="true"
              className="relative flex h-6 w-6 flex-col justify-center gap-[5px]"
            >
              <span
                className={`h-[2px] w-full rounded-full bg-current transition-transform ${
                  isMenuOpen ? "translate-y-[7px] rotate-45" : ""
                }`}
              />
              <span
                className={`h-[2px] w-full rounded-full bg-current transition-opacity ${
                  isMenuOpen ? "opacity-0" : ""
                }`}
              />
              <span
                className={`h-[2px] w-full rounded-full bg-current transition-transform ${
                  isMenuOpen ? "-translate-y-[7px] -rotate-45" : ""
                }`}
              />
            </span>
          </ButtonSecondary>
        </header>

        <nav
          aria-label="Main navigation"
          className={`${isMenuOpen ? "flex" : "hidden"} flex-col gap-12 md:flex`}
          id={navigationId}
        >
          <div className="flex flex-col gap-2">
            {roleLinks.map(({ label, path, icon }) => (
              <ButtonNavigation
                key={path}
                icon={icon}
                onNavigate={() => setIsMenuOpen(false)}
                to={path}
              >
                {label}
              </ButtonNavigation>
            ))}
          </div>

          <div className="flex flex-col gap-2">
            <ButtonNavigation
              icon="settings"
              onNavigate={() => setIsMenuOpen(false)}
              to="/settings"
            >
              Settings
            </ButtonNavigation>
            <ButtonNavigation className="border-0" icon="logout" onClick={logoutAndNavigate}>
              Log out
            </ButtonNavigation>
          </div>
        </nav>
      </GlassPane>
    </aside>
  );
}
