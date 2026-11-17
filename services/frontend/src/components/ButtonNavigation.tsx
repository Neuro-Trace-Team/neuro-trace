import type { CSSProperties, MouseEventHandler, ReactNode } from "react";
import { NavLink } from "react-router-dom";
import auditIcon from "../assets/icon-activity.svg?raw";
import systemIcon from "../assets/icon-system.svg?raw";
import examinationsIcon from "../assets/icon-examinations.svg?raw";
import homeIcon from "../assets/icon-home.svg?raw";
import logoutIcon from "../assets/icon-logout.svg?raw";
import newExaminationIcon from "../assets/icon-new-examination.svg?raw";
import settingsIcon from "../assets/icon-settings.svg?raw";
import usersIcon from "../assets/icon-users.svg?raw";

const navigationIcons = {
  audit: auditIcon,
  system: systemIcon,
  examinations: examinationsIcon,
  home: homeIcon,
  logout: logoutIcon,
  "new-examination": newExaminationIcon,
  settings: settingsIcon,
  users: usersIcon,
} as const;

type NavigationIcon = keyof typeof navigationIcons;

type ButtonNavigationProps = {
  children: ReactNode;
  className?: string;
  disabled?: boolean;
  icon: NavigationIcon;
} & (
  | {
      to: string;
      onNavigate?: MouseEventHandler<HTMLAnchorElement>;
    }
  | {
      to?: undefined;
      onClick: MouseEventHandler<HTMLButtonElement>;
    }
);

const baseClassName =
  "flex min-h-11 w-full items-center border border-0 gap-3 rounded-lg px-3 text-left text-md font-bold text-brand-navy transition-colors hover:bg-white/55 hover:shadow-[0_2px_4px_rgba(0,30,60,0.16)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-cyan";
const selectedClassName =
  "border border-white bg-white/50 shadow-[0_2px_4px_rgba(0,30,60,0.50)] text-brand-navy hover:bg-white/50 hover:shadow-[0_2px_4px_rgba(0,30,60,0.50)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-cyan";

export default function ButtonNavigation(props: ButtonNavigationProps) {
  const { children, className = "", disabled = false, icon } = props;
  const classes = (isSelected = false) =>
    `${baseClassName} ${isSelected && !disabled ? selectedClassName : ""} ${
      disabled ? "cursor-not-allowed opacity-50 hover:bg-transparent" : ""
    } ${className}`;
  const iconSource = navigationIcons[icon];
  const iconDataUrl = `data:image/svg+xml,${encodeURIComponent(iconSource)}`;
  const renderIcon = (isSelected = false) =>
    isSelected && !disabled ? (
      <span
        aria-hidden="true"
        className="h-[21px] w-[21px] shrink-0 bg-gradient-to-r from-brand-cyan to-brand-blue"
        style={
          {
            maskImage: `url("${iconDataUrl}")`,
            maskMode: "alpha",
            maskPosition: "center",
            maskRepeat: "no-repeat",
            maskSize: "contain",
            WebkitMaskImage: `url("${iconDataUrl}")`,
            WebkitMaskPosition: "center",
            WebkitMaskRepeat: "no-repeat",
            WebkitMaskSize: "contain",
          } as CSSProperties
        }
      />
    ) : (
      <img
        alt=""
        aria-hidden="true"
        className="h-[21px] w-[21px] shrink-0 object-contain"
        src={iconDataUrl}
      />
    );

  if (props.to === undefined) {
    return (
      <button
        className={classes()}
        disabled={disabled}
        onClick={props.onClick}
        type="button"
      >
        {renderIcon()}
        <span>{children}</span>
      </button>
    );
  }

  return (
    <NavLink
      aria-disabled={disabled || undefined}
      className={({ isActive }) => classes(isActive)}
      end
      onClick={(event) => {
        if (disabled) {
          event.preventDefault();
          return;
        }
        props.onNavigate?.(event);
      }}
      tabIndex={disabled ? -1 : undefined}
      to={props.to}
    >
      {({ isActive }) => (
        <>
          {renderIcon(isActive)}
          <span>{children}</span>
        </>
      )}
    </NavLink>
  );
}
