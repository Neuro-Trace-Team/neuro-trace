/// <reference types="vite/client" />
/// <reference types="vite-plugin-svgr/client" />

interface ImportMetaEnv {
  readonly VITE_BACKEND_URL?: string;
}

declare module "*.svg" {
  import type { FC, SVGProps } from "react";
  export const ReactComponent: FC<SVGProps<SVGSVGElement>>;
  const src: string;
  export default src;
}