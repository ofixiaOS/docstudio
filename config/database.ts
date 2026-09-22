import app from '@adonisjs/core/services/app'
import { defineConfig } from '@adonisjs/lucid'

const dbConfig = defineConfig({
  connection: 'sqlite',
  connections: {
    sqlite: {
      client: 'better-sqlite3',
      connection: {
        filename: app.makePath('backend/data/docstudio.db'),
      },
      useNullAsDefault: true,
      pool: {
        afterCreate: (conn: { pragma: (p: string) => void }, done: (err: null, conn: unknown) => void) => {
          conn.pragma('journal_mode = WAL')
          conn.pragma('foreign_keys = ON')
          done(null, conn)
        },
      },
    },
  },
})

export default dbConfig
