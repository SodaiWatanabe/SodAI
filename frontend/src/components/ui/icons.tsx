import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement>;

const sharedProps = {
  fill: "none",
  stroke: "currentColor",
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  strokeWidth: 1.8,
  viewBox: "0 0 24 24",
};

export function MenuIcon(props: IconProps) {
  return (
    <svg aria-hidden="true" {...sharedProps} {...props}>
      <path d="M4 8h16M4 16h16" />
    </svg>
  );
}

export function CloseIcon(props: IconProps) {
  return (
    <svg aria-hidden="true" {...sharedProps} {...props}>
      <path d="m6 6 12 12M18 6 6 18" />
    </svg>
  );
}

export function PanelCloseIcon(props: IconProps) {
  return (
    <svg aria-hidden="true" {...sharedProps} {...props}>
      <rect x="3" y="4" width="18" height="16" rx="3" />
      <path d="M9 4v16m6-5-3-3 3-3" />
    </svg>
  );
}

export function PanelOpenIcon(props: IconProps) {
  return (
    <svg aria-hidden="true" {...sharedProps} {...props}>
      <rect x="3" y="4" width="18" height="16" rx="3" />
      <path d="M9 4v16m3-5 3-3-3-3" />
    </svg>
  );
}

export function PlusIcon(props: IconProps) {
  return (
    <svg aria-hidden="true" {...sharedProps} {...props}>
      <path d="M12 5v14M5 12h14" />
    </svg>
  );
}

export function LoginIcon(props: IconProps) {
  return (
    <svg aria-hidden="true" {...sharedProps} {...props}>
      <path d="M14 4h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-3M10 8l4 4-4 4m4-4H4" />
    </svg>
  );
}

export function UserPlusIcon(props: IconProps) {
  return (
    <svg aria-hidden="true" {...sharedProps} {...props}>
      <circle cx="9" cy="8" r="3" />
      <path d="M3.5 19a5.5 5.5 0 0 1 11 0M18 8v6m-3-3h6" />
    </svg>
  );
}

export function LogoutIcon(props: IconProps) {
  return (
    <svg aria-hidden="true" {...sharedProps} {...props}>
      <path d="M10 4H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h3m4-4 4-4-4-4m4 4H9" />
    </svg>
  );
}

export function ArrowLeftIcon(props: IconProps) {
  return (
    <svg aria-hidden="true" {...sharedProps} {...props}>
      <path d="m15 18-6-6 6-6" />
    </svg>
  );
}

export function CheckIcon(props: IconProps) {
  return (
    <svg aria-hidden="true" {...sharedProps} {...props}>
      <path d="m5 12 4 4L19 6" />
    </svg>
  );
}
