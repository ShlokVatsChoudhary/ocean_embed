import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The tests exercise real DOM behaviour (effects and fetch orchestration), so they
// run under jsdom rather than a hand-rolled stub.
const test = {
  environment: 'jsdom',
  globals: true,
  include: ['tests/**/*.test.{js,jsx}'],
  restoreMocks: true,
  setupFiles: ['tests/setup.js'],
}

// The console runs alongside the original frontend so the two can be compared.
// 5173 = original, 5174 = console.
export default defineConfig({
  test,
  plugins: [react()],
  server: { host: 'localhost', port: 5174, strictPort: true },
  preview: { host: 'localhost', port: 4174, strictPort: true },
})
