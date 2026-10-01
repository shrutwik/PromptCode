import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
export default defineConfig({
  plugins: [react()],
  test: {
    environmentMatchGlobs: [['tests/client.test.tsx','jsdom'],['tests/**/*.test.ts','node']],
    include: ['tests/**/*.{test.ts,test.tsx}'],
  },
});
