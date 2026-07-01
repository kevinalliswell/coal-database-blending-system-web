/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_USE_MOCK?: string;
  readonly VITE_API_TARGET?: string;
}
interface ImportMeta {
  readonly env: ImportMetaEnv;
}
