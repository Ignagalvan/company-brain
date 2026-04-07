from pydantic import BaseModel


class OptimizeSummary(BaseModel):
    estimated_time_lost_current_minutes: int
    estimated_time_saved_if_top_actions_completed: int
    active_gaps_count: int
    unused_documents_count: int
    documents_helping_count: int
    coverage_rate_7d: float
    knowledge_health_score: int


class OptimizeAction(BaseModel):
    id: str
    type: str
    title: str
    description: str
    impact_minutes: int
    impact_occurrences: int
    effort_estimate: str
    reason: str
    target_type: str
    target_id: str | None = None
    target_topic: str | None = None
    cta_label: str
    cta_href: str


class OptimizeResponse(BaseModel):
    summary: OptimizeSummary
    primary_action: OptimizeAction | None = None
    top_actions: list[OptimizeAction]
    quick_wins: list[OptimizeAction]
    document_actions: list[OptimizeAction]
    gap_actions: list[OptimizeAction]
