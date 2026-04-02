# Architecture

## Objetivo de este documento

Definir la arquitectura actual del backend de Company Brain y las reglas que deben respetarse durante la implementación del V1.

Este documento es la fuente de verdad técnica.

---

## Objetivo técnico actual

Construir un backend V1 con FastAPI que permita:

- gestión de documentos (base mínima)
- base para RAG (sin complejidad aún)
- chat con evidencia (más adelante)
- multi-tenant seguro
- estructura simple y mantenible

---

## Principios de arquitectura

### 1. Monolito modular

Una sola aplicación, organizada por módulos.

Razón:
- rapidez de desarrollo
- menor complejidad
- control del MVP

---

### 2. Multi-tenant obligatorio

Toda entidad debe estar asociada a `organization_id`.

Esto no es opcional.

---

### 3. Seguridad desde el inicio

- aislamiento por organization_id
- preparado para RLS
- sin mezclar datos entre organizaciones

---

### 4. Simplicidad primero

No implementar cosas futuras ahora.

Evitar:
- abstracciones innecesarias
- patrones complejos
- capas extra

---

### 5. Escalabilidad progresiva

El sistema debe poder crecer, pero sin adelantarse.

---

## Estructura del backend

```text
backend/src/
├── api/
├── core/
├── models/
├── schemas/
├── services/
├── utils/
├── config.py
├── database.py
└── main.py