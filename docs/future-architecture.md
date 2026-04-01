# 🧠 Evolución Futura: Arquitectura Agéntica (Agentic Workflows)

## Contexto

El sistema actual (Company Brain) está diseñado como un motor de recuperación de conocimiento basado en RAG (Retrieval-Augmented Generation).

En esta etapa, el sistema:

* recibe una pregunta
* recupera información relevante
* genera una respuesta con evidencia

---

## Limitación del modelo actual

El modelo RAG es lineal:

```text
Pregunta → Recuperación → Respuesta
```

Este enfoque no permite:

* ejecutar acciones
* planificar pasos intermedios
* interactuar con múltiples fuentes dinámicamente
* mantener estado operativo complejo

---

## Evolución Objetivo

El sistema evolucionará hacia un modelo de:

# 👉 Agentic Workflows

Donde el sistema podrá:

* razonar sobre el problema
* decidir qué herramientas usar
* ejecutar acciones
* observar resultados
* iterar hasta resolver la tarea

---

## Nuevo Modelo de Ejecución

```text
Pensar → Actuar → Observar → Iterar
```

---

## Componentes Futuros

### 1. Agent Orchestrator

Responsabilidad:

* coordinar el flujo de ejecución
* decidir el siguiente paso
* manejar el loop de razonamiento

Ejemplo:

```json
{
  "action": "search_documents",
  "query": "política de viajes",
  "next_step": "validar_costos"
}
```

---

### 2. Tool Registry (Sistema de Herramientas)

El sistema incorporará herramientas que el agente puede utilizar:

Ejemplos:

* search_tool → búsqueda semántica (RAG actual)
* drive_tool → interacción con Google Drive
* email_tool → envío de correos
* ticket_tool → creación de tareas (Jira, etc.)

---

### 3. Tool Execution Layer

Responsabilidad:

* ejecutar las herramientas solicitadas por el agente
* devolver resultados estructurados

---

### 4. Memoria Operativa (Short-Term Memory)

Se diferenciarán dos tipos de memoria:

#### Largo plazo:

* documentos vectorizados (RAG)

#### Corto plazo:

* contexto activo de la conversación
* estado intermedio del agente

Posibles implementaciones futuras:

* base de datos (conversations/messages extendidos)
* cache en memoria (ej. Redis)

---

### 5. LLM con Tool Calling

El sistema evolucionará para que el modelo no solo genere texto, sino decisiones estructuradas:

Ejemplo:

```json
{
  "tool": "search_tool",
  "parameters": {
    "query": "política de vacaciones"
  }
}
```

---

## Relación con la Arquitectura Actual

La arquitectura actual ya está preparada para esta evolución gracias a:

* modularidad
* separación por servicios
* LLM abstraction layer
* sistema de RAG desacoplado

---

## Estrategia de Implementación

### Etapa actual (V1):

* sistema RAG tradicional
* respuestas con evidencia

---

### Etapa intermedia (V2 - Action Layer):

* tool calling básico
* ejecución de acciones simples

---

### Etapa avanzada:

* agente autónomo
* ejecución multi-step
* workflows completos

---

## Decisión Arquitectónica

⚠️ Esta arquitectura **NO se implementa en la V1**.

Se documenta para:

* evitar rediseños futuros
* guiar decisiones técnicas
* mantener coherencia en el crecimiento del sistema

---

## Principio clave

> “Primero resolver un problema bien (RAG), luego evolucionar hacia ejecución (Agentes).”

---

## Estado

🟢 Definido como evolución futura
🟢 Alineado con roadmap del producto
🟢 No implementado en la versión actual
