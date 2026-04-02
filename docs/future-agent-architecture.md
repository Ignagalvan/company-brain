# Future Agent Architecture

## Contexto

El sistema actual de Company Brain está diseñado como un motor de recuperación de conocimiento basado en RAG.

En esta etapa, el sistema:

- recibe una pregunta
- recupera información relevante
- genera una respuesta respaldada por evidencia

---

## Limitación del enfoque actual

El modelo actual es lineal:

```text
Pregunta → Recuperación → Respuesta