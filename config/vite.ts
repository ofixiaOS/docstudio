import { fileURLToPath } from 'node:url'
import { defineConfig } from '@adonisjs/vite'

const viteBackendConfig = defineConfig({
  buildDirectory: 'public/assets',
  manifestFile: fileURLToPath(new URL('../public/assets/.vite/manifest.json', import.meta.url)),
  assetsUrl: '/assets',
  scriptAttributes: {
    defer: true,
  },
})

export default viteBackendConfig
