# 🚀 Company Brain

Sistema SaaS B2B para centralizar el conocimiento interno de las empresas y responder preguntas con evidencia verificable.

---

## 🧠 Problema

Las empresas tienen su conocimiento distribuido en múltiples lugares (Google Drive, PDFs, emails, chats), lo que genera:

* pérdida de tiempo
* interrupciones constantes
* errores operativos
* dependencia de empleados clave

---

## 💡 Solución

Company Brain actúa como la memoria colectiva de la empresa:

* centraliza documentos
* permite consultas en lenguaje natural
* responde con evidencia real
* evita alucinaciones

---

## 🎯 Objetivo actual

Construir un MVP (V1) que permita:

* subir documentos
* procesarlos (RAG)
* hacer preguntas
* obtener respuestas con fuentes
* gestionar información

---

## 🧱 Arquitectura

* FastAPI
* PostgreSQL + pgvector
* Monolito modular
* LLM abstraction
* Multi-tenant con RLS

---

## 📂 Estructura

```text
company-brain/
├── backend/
├── docs/
├── PROJECT_CONTEXT.md
└── README.md
```

---

## 🗺️ Roadmap

### V1

* ingesta de documentos
* chat con evidencia
* panel de administración

### V1.5

* knowledge gap
* sugerencias
* deep linking

### V2

* conflict detection
* confidence score
* analytics

---

## 📌 Estado

* Fase 1: ✔
* Fase 2: ✔
* Fase 3: ✔
* Roadmap: ✔
* Desarrollo: iniciando

---

## 🚀 Visión

```text
Company Brain → Action Layer → Autonomous Ops → Company Intelligence
```
