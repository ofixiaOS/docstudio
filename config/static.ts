import { defineConfig } from '@adonisjs/static'

const staticConfig = defineConfig({
  enabled: true,
  etag: true,
  lastModified: true,
  dotFiles: 'ignore',
})

export default staticConfig
