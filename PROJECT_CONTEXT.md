# 🧠 PROJECT CONTEXT

## Nombre del proyecto

Company Brain

---

## Qué es

Company Brain es una plataforma SaaS B2B que centraliza el conocimiento interno de una empresa y permite consultarlo en lenguaje natural con respuestas respaldadas por evidencia real.

---

## Problema

Las empresas tienen su conocimiento distribuido en múltiples fuentes:

* Google Drive
* PDFs
* Emails
* Chats internos

Esto genera:

* pérdida de tiempo buscando información
* interrupciones constantes a empleados clave
* errores operativos
* dependencia de personas específicas

---

## Solución

Un sistema que:

* ingesta documentos automáticamente
* indexa el conocimiento
* permite hacer preguntas
* responde solo con información existente
* muestra evidencia (citas y fragmentos)

---

## Objetivo actual (V1)

Construir un MVP vendible que incluya:

* subida de documentos
* procesamiento (RAG)
* chat con evidencia
* panel de documentos
* multi-tenant seguro (RLS)

---

## Qué NO incluye V1

* automatización de acciones
* agentes autónomos
* analytics avanzados
* conflict detection
* integrations complejas

---

## Roadmap

### V1 (MVP)

* RAG funcional
* documentos
* chat con citas
* admin panel

---

### V1.5

* knowledge gap
* sugerencias de preguntas
* deep linking

---

### V2

* conflict detection
* confidence score
* activity insights
* reportes de valor

---

### V3 (futuro)

* action layer
* automatización
* agentes

---

## Arquitectura

* Backend: FastAPI
* DB: PostgreSQL + pgvector
* Arquitectura: monolito modular
* LLM abstraction
* multi-tenant con RLS
* procesamiento async

---

## Estructura del proyecto

```text
company-brain/
├── backend/
├── docs/
├── PROJECT_CONTEXT.md
└── README.md
```

---

## Principios del sistema

* nunca inventar respuestas
* toda respuesta debe tener evidencia
* seguridad desde el inicio
* simplicidad en V1
* escalabilidad progresiva

---

## Estado actual

* Fase 1: ✔ definida
* Fase 2: ✔ arquitectura lista
* Fase 3: ✔ UX definida
* Roadmap: ✔ definido
* Desarrollo: 🚧 iniciando V1

---

## Cómo trabajar en este proyecto

Este proyecto se desarrolla con soporte de IA (Claude Code).

El rol del desarrollador es:

* definir qué construir
* validar decisiones
* guiar al sistema

La IA se encarga de:

* generar código
* estructurar módulos
* implementar lógica

---

## Regla clave

> Primero construir un sistema útil (RAG), luego evolucionar a sistema inteligente (Agentes).

---
