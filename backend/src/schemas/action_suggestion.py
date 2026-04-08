from pydantic import BaseModel, Field


class ActionSuggestion(BaseModel):
    topic: str
    display_label: str
    status: str
    coverage_type: str
    priority: str
    priority_score: float
    quality: str
    occurrences: int
    avg_coverage_score: float
    suggested_action: str
    has_existing_draft: bool
    ready_for_draft: bool
    draft_content: str | None = None
    last_seen_at: str = ""
    evidence_snippets: list[str] = []
    evidence_documents: list[str] = []
    evidence_document_ids: list[str] = []
    minutes_lost_per_occurrence: int
    estimated_time_lost_minutes: int
    estimated_time_saved_if_resolved_minutes: int


class RecentlyAppliedItem(BaseModel):
    topic: str
    display_label: str | None = None
    coverage_type: str
    chunks_created: int
    promoted_at: str
    occurrences: int
    estimated_time_saved_if_resolved_minutes: int


class QuickWin(BaseModel):
    topic: str
    display_label: str
    coverage_type: str
    priority: str
    priority_score: float
    occurrences: int
    estimated_time_saved_if_resolved_minutes: int
    summary: str


class Recommendation(BaseModel):
    kind: str
    title: str
    topic: str
    display_label: str
    reason: str
    estimated_time_saved_if_resolved_minutes: int
    occurrences: int
    coverage_type: str
    priority: str


class ActionSuggestionsResponse(BaseModel):
    suggestions: list[ActionSuggestion]
    recently_applied: list[RecentlyAppliedItem]
    quick_wins: list[QuickWin] = []
    recommendations: list[Recommendation] = []
    total: int


class ActionTopicRequest(BaseModel):
    topic: str = Field(..., min_length=3, max_length=500)
    draft_content: str | None = None


class TopicInsight(BaseModel):
    topic: str
    display_label: str | None = None
    coverage_type: str
    occurrences: int
    priority_score: float
    priority: str
    estimated_time_saved_if_resolved_minutes: int


class KnowledgeInsightsResponse(BaseModel):
    total_active_gaps: int
    high_priority_count: int
    coverage_rate: float
    recently_resolved: int
    total_queries_analyzed: int
    active_gaps: int
    resolved_gaps: int
    coverage_rate_7d: float
    estimated_time_lost_current_minutes: int
    estimated_time_saved_recent_minutes: int
    knowledge_health_score: int
    top_topics: list[TopicInsight]


class UndoResponse(BaseModel):
    topic: str
    status: str
