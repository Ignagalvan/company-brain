
---

## `docs/decisions.md`

```md
# Decisions

Este documento registra decisiones arquitectónicas y de producto que ya fueron tomadas para evitar inconsistencias durante el desarrollo.

---

## 2026-04-01 - Arquitectura base del backend

### Decisión

El backend de Company Brain se construye como un monolito modular con FastAPI.

### Razón

Permite avanzar rápido en el MVP, reducir complejidad operativa y mantener el sistema entendible mientras se valida el producto.

---

## 2026-04-01 - Enfoque multi-tenant desde V1

### Decisión

El sistema será multi-tenant desde el inicio usando `organization_id` y Row Level Security (RLS).

### Razón

El aislamiento entre organizaciones es parte central del producto y no puede quedar para más adelante sin generar rediseño riesgoso.

---

## 2026-04-01 - V1 enfocada en trusted knowledge retrieval

### Decisión

La V1 se limita a documentos, procesamiento RAG, chat con evidencia y panel básico.

### Razón

El objetivo es validar una capa confiable de acceso al conocimiento antes de sumar automatización o inteligencia operativa.

---

## 2026-04-01 - No agentes en V1

### Decisión

No implementar agentes autónomos, tool calling complejo ni workflows multi-step en la versión actual.

### Razón

Eso pertenece a una etapa futura. Adelantarlo ahora agrega complejidad y desvía el foco del MVP.

---

## 2026-04-01 - Evidencia obligatoria en respuestas

### Decisión

Toda respuesta del sistema debe poder respaldarse con evidencia recuperable.

### Razón

La confiabilidad del producto depende de que el usuario pueda verificar de dónde sale cada respuesta.

---

## 2026-04-01 - Trabajo guiado por documentación

### Decisión

Las decisiones de arquitectura y alcance deben quedar documentadas y servir como fuente de verdad para desarrollo asistido por IA.

### Razón

Esto mejora consistencia, reduce desvíos y baja el costo de contexto entre sesiones y herramientas.

---

## 2026-04-01 - Implementación incremental por módulos

### Decisión

El sistema se construirá módulo por módulo, comenzando por `documents`.

### Razón

Permite validar cada pieza con foco, evitar sobreingeniería y mantener control sobre el crecimiento del backend.

--- 

---

## 2026-04-02 - Upload de archivos en V1

### Decisión

Implementar subida de archivos en disco local usando carpeta `uploads/`.

### Razón

Permite validar rápidamente el flujo de documentos sin introducir complejidad de almacenamiento externo (S3/GCS) en esta etapa.

---

## 2026-04-02 - Estado del documento

### Decisión

Agregar campo `status` en documentos con valores como `pending` y `uploaded`.

### Razón

Permite preparar el sistema para futuros pasos de procesamiento (extracción, embeddings, etc.) sin modificar el modelo más adelante.