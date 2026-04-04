from pydantic import BaseModel, Field


class ActionSuggestion(BaseModel):
    topic: str
    coverage_type: str          # "none" | "partial"
    priority: str               # "high" | "medium"
    occurrences: int
    avg_coverage_score: float
    suggested_action: str       # "create_document" | "improve_document"
    has_existing_draft: bool
    ready_for_draft: bool


class ActionSuggestionsResponse(BaseModel):
    suggestions: list[ActionSuggestion]
    total: int


class ActionTopicRequest(BaseModel):
    topic: str = Field(..., min_length=3, max_length=500)
