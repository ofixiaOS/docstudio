import { inject } from '@adonisjs/core'
import type { HttpContext } from '@adonisjs/core/http'
import type { PageObject } from '@adonisjs/inertia/types'
import PythonEngineService from '#services/engine/python_engine_service'
import type { StudioProps, ProjectSummaryDTO } from '#types/page_props/studio'
import db from '@adonisjs/lucid/services/db'

interface ProjectRow {
  id: string
  title: string
  institution: string | null
  career: string | null
  author_name: string | null
  updated_at: string
}

@inject()
export default class StudioController {
  /**
   * Vista principal del Studio (Inertia React)
   */
  public async index(ctx: HttpContext): Promise<string | PageObject<StudioProps>> {
    let projects: ProjectSummaryDTO[] = []

    try {
      const rows = await db.from('projects').select('*').orderBy('updated_at', 'desc')
      projects = (rows as ProjectRow[]).map((r) => ({
        id: r.id,
        title: r.title,
        institution: r.institution,
        career: r.career,
        authorName: r.author_name,
        updatedAt: r.updated_at,
      }))
    } catch {
      projects = []
    }

    const currentProject = projects.length > 0 ? projects[0] : null

    const props: StudioProps = {
      currentProject,
      allProjects: projects,
      sections: [],
      rubricCriteria: [],
      memories: [],
      aiModels: ['gemini-2.5-flash', 'gemini-2.5-pro', 'gemini-2.0-flash'],
      selectedModel: 'gemini-2.5-flash',
    }

    return ctx.inertia.render('studio', props)
  }

  /**
   * Endpoint de diagnóstico y salud del sistema
   */
  public async healthCheck({ response }: HttpContext) {
    const engineHealthy = await PythonEngineService.ping()
    let dbHealthy = false

    try {
      await db.rawQuery('SELECT 1')
      dbHealthy = true
    } catch {
      dbHealthy = false
    }

    return response.ok({
      status: engineHealthy && dbHealthy ? 'ok' : 'degraded',
      host: 'AdonisJS 7',
      sidecar: {
        engine: 'Python Docx & AI Engine',
        healthy: engineHealthy,
      },
      database: {
        type: 'SQLite (better-sqlite3 + WAL)',
        healthy: dbHealthy,
      },
    })
  }
}
