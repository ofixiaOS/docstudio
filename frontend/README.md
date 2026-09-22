# DocStudio Frontend

Cliente web local-first para **DocStudio**, construido con React 19, Vite y Tiptap.

---

## Estructura de la Interfaz

- **`Header.jsx`**: Barra superior con navegación de pasos, estado de conexión local y botón de **Ajustes & Perfil**.
- **`ApiKeyModal.jsx`**: Modal de configuración de autor/estudiante, institución, carrera, modelo Gemini y API key enmascarada.
- **`ProjectSidebar.jsx`**: Explorador lateral de proyectos locales con búsqueda e indicador de salud de SQLite WAL.
- **`UploadView.jsx`**: Importación de pautas, rúbricas o temas con carga de archivos y extracción preliminar.
- **`OutlineView.jsx`**: Estructurador de índice y lista de verificación antes de redactar.
- **`EditorView.jsx`**: Entorno principal de redacción:
  - **Editor TipTap**: Títulos, listas, citas, código, tablas, negrita, cursiva e imágenes.
  - **Panel Copiloto**:
    - *Pauta / Verificación:* Checklist de cobertura con retroalimentación constructiva.
    - *Copiloto (Chat):* Conversación contextual con botones de acción para insertar sugerencias directamente al documento.
    - *Memoria:* Vista y administración CRUD de acuerdos, decisiones técnicas y preferencias.
    - *Fuentes:* Material de estudio adjunto y capturas de pantalla registradas.
  - **Modal de Evidencias:** Formulario para etiquetar leyendas y asociar capturas antes de insertarlas.
  - **Historial de Versiones:** Diálogo para restaurar snapshots previos.

---

## Comandos

```powershell
npm run dev     # Servidor de desarrollo Vite en http://127.0.0.1:5173
npm run lint    # Verificación estática ultra-rápida con Oxlint
npm run build   # Compilación para producción (dist/)
```

