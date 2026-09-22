# DocStudio

**DocStudio** es un editor de documentos técnicos y académicos asistido por IA, local-first, con memoria de largo plazo persistente, RAG de fuentes locales, control de versiones y soporte para **MCP (Model Context Protocol)** para trabajar en conjunto con **Codex**, **Antigravity**, **Cursor** y otros IDEs.

El proyecto está diseñado para ser **universal y compartible con amigos y colegas**: no está restringido a ninguna institución ni impone sistemas de calificación punitivos. Funciona como un copiloto de calidad y estructuración que recuerda acuerdos, respeta tus decisiones y genera documentos de Word (DOCX) con acabado profesional.

---

## Características Principales

- **Editor Enriquecido y Copiloto Activo:** Editor basado en TipTap con soporte de títulos, listas, citas, bloques de código, tablas y figuras con pie de foto.
- **Acciones Sugeridas en el Chat:** Las propuestas de redacción del copiloto incluyen botones interactivos para insertar directamente el contenido en el documento con un clic.
- **Memoria de Largo Plazo Gobernable:**
  - Pestaña dedicada para ver, agregar y eliminar memorias de proyecto (`Preferencia`, `Decisión`, `Dato`).
  - Aprendizaje continuo durante el chat con embeddings vectoriales y búsqueda híbrida (FTS5 + similitud semántica).
- **Lista de Verificación y Cobertura (Sin Calificaciones Punitivas):** Interpreta pautas o rúbricas para desglosar criterios y entregables, funcionando como un checklist constructivo en vez de un calificador sancionador.
- **Modal de Capturas y Evidencias:** Sube capturas de pantalla con descripción/leyenda y asociación opcional a criterios de la pauta.
- **RAG Local de Fuentes:** Indexa material de estudio en PDF, DOCX, TXT y código fuente para alimentar el contexto del copiloto.
- **Historial de Versiones:** Snapshots automáticos y manuales con capacidad de restauración inmediata.
- **Exportación Word (DOCX) Profesional:** Exporta encabezados, listas, tablas nativas, bloques de código, citas y figuras con portada adaptable según el perfil del autor.
- **Integración MCP para IDEs y Codex:** Expone herramientas locales para que agentes en tu IDE puedan consultar el contexto del proyecto, registrar memorias, anexar código e insertar secciones.

---

## Inicio Rápido

Para iniciar la aplicación en Windows:

1. Haz doble clic en `iniciar_gamma.bat`, o ejecuta en PowerShell:
   ```powershell
   .\iniciar_gamma.ps1
   ```
2. El script de inicio preparará el entorno virtual de Python, instalará las dependencias necesarias, liberará puertos huérfanos si existieran y abrirá la interfaz en:
   ```
   http://127.0.0.1:5173
   ```
3. Backend disponible en `http://127.0.0.1:8765`.

---

## Configuración y Perfil de Usuario

Haz clic en el botón **"Ajustes"** en la barra superior para configurar:
- **Autor / Estudiante:** Tu nombre o el de tu equipo.
- **Institución / Universidad / Empresa:** Opcional (si se deja en blanco, la portada del documento se adapta de forma limpia).
- **Carrera / Área / Proyecto:** Especialidad o contexto.
- **Modelo de IA:** Selecciona entre `gemini-2.5-flash`, `gemini-2.5-pro` u otro modelo compatible.
- **Gemini API Key:** Tu clave personal (se almacena de forma segura en `backend/.env` y nunca se expone en texto plano en la interfaz).

---

## Integración con Codex e IDEs (MCP)

DocStudio incluye soporte nativo para agentes mediante STDIO:
- **Codex:** Configurado en `.codex/config.toml` (servidor `gamma_local`).
- **Antigravity / Cursor:** Configurado en `.agents/mcp_config.json`.

Herramientas MCP disponibles para agentes:
- `list_projects`: Lista los proyectos existentes en la base local.
- `get_project_context`: Lee el documento, pauta, fuentes, memorias y evidencias.
- `create_project`: Crea un nuevo proyecto con perfil personalizado.
- `remember_project_decision`: Guarda una decisión o acuerdo en la memoria de largo plazo.
- `search_project_sources`: Consulta el índice lexical FTS5 de fuentes.
- `update_section`: Actualiza o redacta un bloque en el documento creando una versión.
- `attach_artifact`: Copia archivos generados por el agente al proyecto.
- `register_execution`: Registra comandos ejecutados y sus resultados.
- `request_audit`: Ejecuta una verificación de cobertura de la pauta.

Los agentes se comunican directamente vía STDIO ejecutando `backend/scripts/gamma_mcp.py`.

---

## Privacidad y Datos Locales

- **Base de datos local:** Todo se almacena en SQLite WAL en `backend/data/docstudio.db`.
- **Archivos locales:** Fuentes, evidencias y versiones se guardan en `backend/data/projects/<project_id>`.
- **Git:** La carpeta `backend/data`, logs, secretos `.env` y entornos virtuales están completamente excluidos en `.gitignore`.
- La herramienta es **local-first**: la persistencia, búsqueda FTS5, versiones y exportación a DOCX funcionan offline. Cuando se utiliza la IA para análisis, redacción o embeddings, las consultas se envían exclusivamente a los endpoints oficiales de Google Gemini con tu API key.

---

## Desarrollo y Pruebas

```powershell
# Compilación estricta de TypeScript (Host AdonisJS + Frontend Inertia)
npm run typecheck

# Tests de integración del Host Web
npm run test

# Pruebas unitarias y de integración del Sidecar Python (53 tests)
cd backend
.\.venv\Scripts\python.exe -m pytest -q
```
