import { defineConfig, mergeConfig } from 'vitest/config'
import viteConfig from './vite.config'

export default defineConfig((env) =>
  mergeConfig(
    viteConfig(env),
    defineConfig({
      test: {
        environment: 'jsdom',
        include: ['src/**/*.spec.ts'],
        setupFiles: ['./src/test/setup.ts'],
        restoreMocks: true,
        unstubGlobals: true,
      },
    }),
  ),
)
