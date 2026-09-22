import { spawn, type ChildProcess } from 'node:child_process'
import path from 'node:path'
import fs from 'node:fs/promises'
import crypto from 'node:crypto'
import app from '@adonisjs/core/services/app'
import logger from '@adonisjs/core/services/logger'

export interface ExportDocxOptions {
  projectId: string
  exportId: string
  htmlContent: string
  title?: string
  institution?: string
  career?: string
  author?: string
}

export interface ExportResult {
  filePath: string
  sha256: string
  sizeBytes: number
}

export default class PythonEngineService {
  /**
   * Resuelve la ruta al ejecutable de Python del entorno virtual.
   */
  public static getPythonExecutable(): string {
    const isWindows = process.platform === 'win32'
    const venvPath = isWindows
      ? app.makePath('backend/.venv/Scripts/python.exe')
      : app.makePath('backend/.venv/bin/python')
    return venvPath
  }

  /**
   * Ejecuta un comando en el motor Python gobernado por un timeout estricto
   * y limpieza garantizada de timers (Patrón PuppeteerHelper de OFIXIA).
   */
  public static async executeWithTimeout<T = string>(
    scriptArgs: string[],
    options: {
      stdinData?: string
      timeoutMs?: number
      cwd?: string
    } = {}
  ): Promise<T> {
    const timeoutMs = options.timeoutMs ?? 30000
    const pythonBin = this.getPythonExecutable()
    const cwd = options.cwd ?? app.makePath('backend')

    let timeoutHandle: NodeJS.Timeout | undefined
    let child: ChildProcess | undefined

    try {
      const execPromise = new Promise<T>((resolve, reject) => {
        child = spawn(pythonBin, scriptArgs, {
          cwd,
          stdio: ['pipe', 'pipe', 'pipe'],
          env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
        })

        let stdout = ''
        let stderr = ''

        child.stdout?.on('data', (chunk) => {
          stdout += chunk.toString('utf-8')
        })

        child.stderr?.on('data', (chunk) => {
          stderr += chunk.toString('utf-8')
        })

        child.on('error', (err) => {
          reject(new Error(`[PYTHON_ENGINE_ERROR] Fallo al iniciar subproceso: ${err.message}`))
        })

        child.on('close', (code) => {
          if (code !== 0) {
            reject(
              new Error(
                `[PYTHON_ENGINE_FAILURE] Código de salida ${code}: ${stderr.trim() || stdout.trim()}`
              )
            )
          } else {
            try {
              const trimmed = stdout.trim()
              if (
                (trimmed.startsWith('{') && trimmed.endsWith('}')) ||
                (trimmed.startsWith('[') && trimmed.endsWith(']'))
              ) {
                resolve(JSON.parse(trimmed) as T)
              } else {
                resolve(trimmed as unknown as T)
              }
            } catch {
              resolve(stdout as unknown as T)
            }
          }
        })

        if (options.stdinData && child.stdin) {
          child.stdin.write(options.stdinData, 'utf-8')
          child.stdin.end()
        }
      })

      const timeoutPromise = new Promise<never>((_, reject) => {
        timeoutHandle = setTimeout(() => {
          if (child && !child.killed) {
            logger.warn(`[PYTHON_ENGINE] Matando proceso Python por timeout (${timeoutMs}ms)`)
            child.kill('SIGKILL')
          }
          reject(
            new Error(
              `E_ENGINE_TIMEOUT: La operación del motor Python excedió el límite de ${timeoutMs}ms`
            )
          )
        }, timeoutMs)
      })

      return await Promise.race([execPromise, timeoutPromise])
    } finally {
      if (timeoutHandle) {
        clearTimeout(timeoutHandle)
      }
    }
  }

  /**
   * Exporta un documento HTML a DOCX de alta fidelidad, aplicando
   * direccionamiento por contenido e inmutabilidad (Regla #6).
   */
  public static async exportDocx(options: ExportDocxOptions): Promise<ExportResult> {
    const exportsDir = app.makePath(`backend/data/projects/${options.projectId}/exports`)
    await fs.mkdir(exportsDir, { recursive: true })

    const outputFilePath = path.join(exportsDir, `${options.exportId}.docx`)

    const script = `
import sys, json
from docx_exporter import create_docx_document
from app.html_utils import parse_html_to_sections

data = json.loads(sys.stdin.read())
sections = parse_html_to_sections(data.get('htmlContent', ''))

doc_data = {
    'title': data.get('title', 'Documento'),
    'institution': data.get('institution'),
    'career': data.get('career'),
    'author': data.get('author'),
    'sections': sections,
}

create_docx_document(doc_data, data['outputFilePath'])
print(json.dumps({'status': 'ok'}))
`

    await this.executeWithTimeout(
      ['-c', script],
      {
        stdinData: JSON.stringify({
          ...options,
          outputFilePath,
        }),
        timeoutMs: 45000,
      }
    )

    const fileBuffer = await fs.readFile(outputFilePath)
    const sha256 = crypto.createHash('sha256').update(fileBuffer).digest('hex')

    return {
      filePath: outputFilePath,
      sha256,
      sizeBytes: fileBuffer.length,
    }
  }

  /**
   * Health-check del motor Python sidecar.
   */
  public static async ping(): Promise<boolean> {
    try {
      const result = await this.executeWithTimeout<string>(
        ['-c', "import sys; print('ok')"],
        { timeoutMs: 5000 }
      )
      return result.trim() === 'ok'
    } catch {
      return false
    }
  }
}
