/*
|--------------------------------------------------------------------------
| Routes file
|--------------------------------------------------------------------------
*/

import router from '@adonisjs/core/services/router'

const StudioController = () => import('#controllers/studio_controller')

router.get('/', [StudioController, 'index'])
router.get('/api/health', [StudioController, 'healthCheck'])
