import { test } from '@japa/runner'
import PythonEngineService from '#services/engine/python_engine_service'
import fs from 'node:fs/promises'

test.group('Health check & Sidecar verification', () => {
  test('PythonEngineService.ping() should connect to Python sidecar successfully', async ({ assert }) => {
    const isHealthy = await PythonEngineService.ping()
    assert.isTrue(isHealthy, 'El motor Python sidecar debe responder ok')
  })

  test('GET /api/health should respond with host and sidecar status', async ({ client }) => {
    const response = await client.get('/api/health')

    response.assertStatus(200)
    response.assertBodyContains({
      host: 'AdonisJS 7',
      status: 'ok',
      sidecar: {
        engine: 'Python Docx & AI Engine',
        healthy: true,
      },
    })
  })

  test('PythonEngineService.exportDocx should generate valid DOCX with SHA-256 manifest', async ({ assert }) => {
    const htmlSample = `
      <h1>1. Introducción al Caso</h1>
      <p>Texto introductorio de prueba para verificación documental.</p>
      <h2>1.1 Alcance</h2>
      <p>Detalle del alcance del proyecto.</p>
      <h3>1.1.1 Especificaciones</h3>
      <p>Especificaciones técnicas.</p>
      <h4>1.1.1.1 Criterios Menores</h4>
      <p>Contenido bajo H4.</p>
      <div class="evidence-block">EVIDENCIA PENDIENTE: Captura de pantalla del sistema</div>
    `

    const result = await PythonEngineService.exportDocx({
      projectId: 'test_project_adonis',
      exportId: 'export_v1_test',
      htmlContent: htmlSample,
      title: 'Informe Técnico de Prueba',
      institution: 'Universidad Tecnológica',
      career: 'Ingeniería en Informática',
      author: 'DocStudio Tester',
    })

    assert.isString(result.filePath)
    assert.isTrue(result.sizeBytes > 0)
    assert.match(result.sha256, /^[a-f0-9]{64}$/, 'El hash debe ser un SHA-256 válido')

    // Verificar que el archivo existe físicamente
    const fileStat = await fs.stat(result.filePath)
    assert.isTrue(fileStat.isFile())
  })
})
