# Documents Module

## Objetivo del módulo

El módulo `documents` es responsable de gestionar la base mínima de documentos en la V1 de Company Brain.

En esta etapa, su función principal es representar y administrar los documentos cargados por una organización.

---

## Alcance actual

La versión mínima del módulo incluye solamente la base necesaria para soportar el MVP.

Incluye:

- registrar documentos
- listar documentos
- obtener información básica de un documento
- eliminar documentos si aplica al flujo definido
- almacenar metadata necesaria para su gestión

---

## Qué NO incluye todavía

Este módulo no debe incluir aún:

- embeddings
- chunking
- extracción compleja de contenido
- OCR
- pipelines avanzados
- scoring semántico
- clasificación automática
- análisis inteligente del documento
- integraciones complejas con terceros

Todo eso pertenece a etapas posteriores o a otros componentes del sistema.

---

## Propósito dentro del sistema

El módulo `documents` cumple dos funciones iniciales:

### 1. Gestión documental básica

Permitir que una organización tenga documentos registrados y administrables dentro del sistema.

### 2. Base para procesamiento posterior

Servir como entidad raíz para futuras etapas de procesamiento RAG.

En otras palabras, primero existe el documento como recurso administrable.  
Después vendrá su procesamiento.

---

## Responsabilidades

El módulo debe encargarse de:

- representar documentos en base de datos
- validar entradas y salidas del dominio documents
- exponer endpoints HTTP básicos
- encapsular lógica de negocio simple asociada a documentos
- respetar aislamiento por organización

---

## Límites del módulo

El módulo no debe asumir responsabilidades de:

- retrieval
- generación de respuestas
- orquestación de procesamiento complejo
- lógica de chat
- lógica de embeddings

---

## Diseño mínimo recomendado

Para V1 mínima, el módulo puede estar compuesto por:

- model
- schema
- router
- service

Esto alcanza para mantener separación de responsabilidades sin sobreingeniería.

---

## Archivos esperados

Ejemplo de estructura mínima:

```text
backend/src/
├── api/
│   └── documents.py
├── models/
│   └── document.py
├── schemas/
│   └── document.py
└── services/
    └── document_service.py

---

## Estado actual del módulo

Actualmente el módulo `documents` ya cuenta con:

- CRUD completo funcionando
- endpoints:
  - POST /documents
  - GET /documents
  - GET /documents/{id}
  - DELETE /documents/{id}
- endpoint adicional:
  - POST /documents/upload (subida real de archivos)

Funcionalidad implementada:

- almacenamiento de metadata en PostgreSQL
- upload de archivos a carpeta local `uploads/`
- generación de nombre único por archivo
- estado del documento (`pending`, `uploaded`)
- pruebas realizadas desde Swagger

---

## Próximo paso del módulo

- extracción de texto desde archivos PDF
- preparación para procesamiento posterior (RAG)