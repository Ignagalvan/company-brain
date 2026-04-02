
---

## `docs/project-context.md`

```md
# Project Context

## Nombre del proyecto

Company Brain

---

## Qué es

Company Brain es una plataforma SaaS B2B que centraliza el conocimiento interno de una empresa y permite consultarlo en lenguaje natural con respuestas respaldadas por evidencia real.

No es un chatbot genérico. Es un sistema de búsqueda semántica confiable para empresas.

---

## Problema

En la mayoría de las organizaciones, el conocimiento interno está distribuido en múltiples fuentes y formatos:

- Google Drive
- PDFs
- documentación interna
- emails
- chats
- archivos compartidos

Esto genera:

- pérdida de tiempo buscando información
- interrupciones a personas clave
- errores operativos
- dependencia de conocimiento informal
- dificultad para validar respuestas

---

## Solución

Company Brain busca convertirse en la memoria operativa confiable de una organización.

El sistema debe permitir:

- incorporar conocimiento interno
- procesarlo para recuperación semántica
- responder preguntas en lenguaje natural
- respaldar cada respuesta con evidencia
- mantener seguridad y aislamiento por organización

---

## Objetivo actual

Construir el backend V1 (MVP) con foco en una primera versión vendible, simple y técnicamente sólida.

---

## Alcance de V1

Incluye:

- subida de documentos
- almacenamiento de metadata de documentos
- procesamiento base para RAG
- chat con evidencia
- panel de documentos
- multi-tenant seguro
- organization_id como eje de aislamiento
- Row Level Security (RLS)

---

## Qué NO incluye V1

No forma parte de esta etapa:

- agentes autónomos
- automatización de acciones
- conflict detection
- analytics avanzados
- integrations complejas
- workflows multi-step
- orchestration agéntica

---

## Roadmap de alto nivel

### V1

- documentos
- procesamiento RAG
- chat con citas
- panel base de administración
- seguridad multi-tenant

### V1.5

- knowledge gap
- sugerencias de preguntas
- deep linking a fuentes

### V2

- conflict detection
- confidence score
- activity insights
- reportes de valor

### V3

- action layer
- tool calling
- automatización
- agentic workflows

---

## Arquitectura base

- Backend: FastAPI
- Base de datos: PostgreSQL
- Vector store: pgvector
- Arquitectura: monolito modular
- Multi-tenant con organization_id
- RLS
- abstracción de LLM
- procesamiento async

---

## Principios del producto

- nunca inventar respuestas
- toda respuesta debe tener evidencia
- seguridad desde el inicio
- simplicidad en V1
- enfoque incremental
- primero utilidad, luego sofisticación

---

## Regla de crecimiento

Primero construir una capa de conocimiento confiable.  
Después evolucionar hacia ejecución, automatización y agentes.

---

## Estado actual

Proyecto en implementación activa del backend V1.

Actualmente ya está resuelto:

- base técnica del backend
- configuración centralizada
- conexión async a PostgreSQL
- Alembic configurado
- migraciones funcionando
- contenedor PostgreSQL en Docker
- módulo `documents` base implementado
- CRUD de documentos funcionando
- upload de archivos funcionando
- pruebas realizadas desde Swagger

Próximo objetivo inmediato:

- extracción de texto desde PDFs subidos
- luego procesamiento base del contenido
- después embeddings y recuperación semántica

---