import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Resolve the src directory without relying on Node typings (path/__dirname).
const srcDir = decodeURIComponent(new URL('./src', import.meta.url).pathname).replace(
  /^\/([A-Za-z]:)/,
  '$1'
)

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@': srcDir },
  },
})
