/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL?: string
  readonly VITE_USER_ID?: string
  readonly VITE_DEFAULT_LAT?: string
  readonly VITE_DEFAULT_LON?: string
  readonly VITE_DEFAULT_LOCATION?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
