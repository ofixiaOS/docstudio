import type { JSONDataTypes } from '@adonisjs/core/types/transformers'

type PageProps<T> = T & Record<string, JSONDataTypes>

declare module '@adonisjs/inertia/types' {
  export interface InertiaPages extends Record<string, unknown> {
    'studio': PageProps<import('#types/page_props/studio').StudioProps>
  }
}

export {}
