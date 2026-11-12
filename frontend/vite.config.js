import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The API defaults to port 8000; set FIRSTLOOK_API to point the dev server elsewhere.
const api = process.env.FIRSTLOOK_API || 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { '/api': api } },
})
