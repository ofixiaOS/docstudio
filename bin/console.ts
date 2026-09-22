/*
|--------------------------------------------------------------------------
| Ace entry point
|--------------------------------------------------------------------------
|
| The "console.ts" file is the entrypoint for booting the AdonisJS
| command-line framework and executing commands.
|
*/

await import('reflect-metadata')
const { Ignitor, prettyPrintError } = await import('@adonisjs/core')

/**
 * URL to the application root. AdonisJS need it to resolve
 * paths to file and directories for scaffolding commands
 */
const APP_ROOT = new URL('../', import.meta.url)

/**
 * The importer is used to import files in context of the
 * application.
 */
const IMPORTER = (filePath: string) => {
  if (filePath.startsWith('./') || filePath.startsWith('../')) {
    return import(new URL(filePath, APP_ROOT).href)
  }
  return import(filePath)
}

new Ignitor(APP_ROOT, { importer: IMPORTER })
  .tap((app) => {
    app.booting(async () => {
      await import('#start/env')
    })
    app.listen('SIGTERM', () => {
      void app.terminate()
    })
    app.listenIf(app.managedByPm2, 'SIGINT', () => {
      void app.terminate()
    })
  })
  .ace()
  .handle(process.argv.splice(2))
  .then(() => {})
  .catch(async (error) => {
    process.exitCode = 1
    await prettyPrintError(error)
  })
