import { createRoot } from 'react-dom/client'
import { createInertiaApp } from '@inertiajs/react'
import { resolvePageComponent } from '@adonisjs/inertia/helpers'
import type { ReactElement } from 'react'

const appName = 'DocStudio'

void createInertiaApp({
  title: (title: string) => (title ? `${title} - ${appName}` : appName),
  resolve: async (name: string) => {
    return (await resolvePageComponent(
      `./pages/${name}.tsx`,
      import.meta.glob('./pages/**/*.tsx')
    )) as { default: { layout?: (children: ReactElement) => ReactElement } }
  },
  setup({ el, App, props }) {
    createRoot(el).render(<App {...props} />)
  },
  progress: {
    color: '#2563eb',
  },
})
