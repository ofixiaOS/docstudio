import { defineConfig } from '@adonisjs/shield'

const shieldConfig = defineConfig({
  csp: {
    enabled: false,
  },
  csrf: {
    enabled: true,
    exceptRoutes: ['/api/**'],
    enableXsrfCookie: true,
    methods: ['POST', 'PUT', 'PATCH', 'DELETE'],
  },
  hsts: {
    enabled: true,
    maxAge: '180 days',
  },
  contentTypeSniffing: {
    enabled: true,
  },
  xFrame: {
    enabled: true,
    action: 'DENY',
  },
})

export default shieldConfig
