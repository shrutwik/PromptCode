from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class InterviewChallengeCard(BaseModel):
    slug: str
    title: str
    type: str
    stack: str
    difficulty: str
    estimated_minutes: int
    summary: str


class InterviewChallengeDetail(InterviewChallengeCard):
    readme: str
    test_command: str
    entry_files: list[str] = Field(default_factory=list)
    command_ids: list[str] = Field(
        default_factory=lambda: ["run_tests", "run_targeted_tests", "run_benchmark"]
    )


class StartSessionRequest(BaseModel):
    challenge_slug: str
    owner_token: str | None = None


class EarlierStep(BaseModel):
    index: int
    kind: str
    title: str
    body: str


class LevelStepResponse(BaseModel):
    index: int
    total: int
    kind: str
    title: str
    body: str
    problem: str
    guide: list[str] = Field(default_factory=list)
    can_advance: bool
    is_last: bool
    earlier: list[EarlierStep] = Field(default_factory=list)


class SessionResponse(BaseModel):
    id: UUID
    challenge_slug: str
    status: str
    owner_token: str
    attempt_number: int = 1
    started_at: datetime
    submitted_at: datetime | None = None
    expires_at: datetime | None = None
    elapsed_ms: int = 0
    timer_running: bool = False
    timer_lease_ms: int = 0


class SessionTimerRequest(BaseModel):
    action: str = Field(pattern="^(resume|heartbeat|pause)$")
    editor_token: str = Field(min_length=16, max_length=64)


class SessionFeedbackRequest(BaseModel):
    realism: int = Field(ge=1, le=5)
    difficulty: int = Field(ge=1, le=5)
    text: str = Field(default="", max_length=2000)
    ai_as_expected: int | None = Field(default=None, ge=1, le=5)
    confusing_or_broken: bool | None = None
    most_like_real_interview: bool | None = None


class SessionFeedbackResponse(BaseModel):
    ok: bool = True


class AbandonSessionRequest(BaseModel):
    reason: str = Field(default="", max_length=256)


class HumanReviewRequest(BaseModel):
    notes: str = Field(default="", max_length=4000)
    category_observations: dict[str, Any] = Field(default_factory=dict)
    disagreement: bool = False
    observed_difficulty: str | None = None
    observed_time_minutes: float | None = None
    reviewer: str = Field(default="internal", max_length=128)


class ChallengeProgressCard(InterviewChallengeCard):
    progress: str = "not_started"  # not_started | in_progress | completed
    attempt_count: int = 0
    best_score: float | None = None
    latest_session_id: UUID | None = None
    active_session_id: UUID | None = None


class DashboardSessionItem(BaseModel):
    id: UUID
    challenge_slug: str
    challenge_title: str | None = None
    status: str
    attempt_number: int = 1
    started_at: datetime
    submitted_at: datetime | None = None
    total_score: float | None = None


class DashboardStatsResponse(BaseModel):
    sessions: list[DashboardSessionItem]
    completed: int = 0
    avg_score: float | None = None
    avg_correctness: float | None = None
    avg_exploration: float | None = None
    avg_ai_judgment: float | None = None
    avg_verification: float | None = None
    trends: list[str] = Field(default_factory=list)
    trends_note: str | None = None


class FileEntry(BaseModel):
    path: str
    size: int


class FileContentResponse(BaseModel):
    path: str
    content: str
    revision: int = 0


class WorkspaceBootstrapResponse(BaseModel):
    session: SessionResponse
    files: list[FileEntry]
    level: LevelStepResponse | None = None
    readme: FileContentResponse | None = None


class SaveFileRequest(BaseModel):
    content: str
    base_revision: int | None = Field(default=None, ge=0)
    source: str = "candidate"  # candidate | ai | mixed
    additions: int | None = None
    deletions: int | None = None


class EventRequest(BaseModel):
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)


class EventResponse(BaseModel):
    id: UUID
    event_type: str
    payload: dict[str, Any]
    created_at: datetime


class AIChatRequest(BaseModel):
    message: str
    attached_paths: list[str] = Field(default_factory=list)
    include_test_output: bool = False
    selected_text: str | None = None
    test_output: str | None = None


class AIChatResponse(BaseModel):
    reply: str
    provider: str
    model: str
    proposed_edits: list[dict[str, Any]] = Field(default_factory=list)
    latency_ms: int = 0
    rejected_attachments: list[str] = Field(default_factory=list)
    error_code: str | None = None


class AIApplyRequest(BaseModel):
    path: str
    content: str
    disposition: str = "accepted"  # accepted | modified | rejected
    proposed_content: str | None = None
    base_revision: int | None = None


class TestRunRequest(BaseModel):
    command_id: str = "run_tests"


class TestRunResponse(BaseModel):
    advisory: bool = True
    authoritative: bool = False
    feedback_kind: str = "advisory_practice"
    ok: bool
    exit_code: int
    stdout: str
    stderr: str
    command: str
    duration_ms: int = 0
    mode: str = "full"
    counts: dict[str, Any] = Field(default_factory=dict)
    isolation: str = "host"
    timed_out: bool = False
    command_id: str = "run_tests"
    runner: str = "local"
    error_code: str | None = None


class DiffSummaryResponse(BaseModel):
    files_changed: list[dict[str, Any]]
    additions: int
    deletions: int
    file_count: int


class DiffFileResponse(BaseModel):
    path: str
    unified: str


class DefendAnswerRequest(BaseModel):
    index: int = Field(ge=0, le=4)
    answer: str = Field(min_length=1, max_length=4000)


class DefendQuestionsResponse(BaseModel):
    questions: list[dict[str, Any]]
    answers: dict[str, Any] = Field(default_factory=dict)


class EvaluationResponse(BaseModel):
    advisory: bool = True
    authoritative: bool = False
    feedback_kind: str = "advisory_practice"
    assessment: dict[str, Any] | None = None
    total_score: float
    rubric: dict[str, Any]
    metrics: dict[str, Any]
    insights: list[Any]
    test_summary: dict[str, Any]
    defend_questions: list[Any]
    timeline: list[EventResponse]
    went_well: list[Any] = Field(default_factory=list)
    improve: list[Any] = Field(default_factory=list)
    recovery_moments: list[Any] = Field(default_factory=list)
    signals: list[Any] = Field(default_factory=list)
    diff_summary: dict[str, Any] | None = None
    scoring_version: str = "v1"
    challenge_version: str | None = None
    steps: dict[str, Any] | None = None
    previous_attempt: dict[str, Any] | None = None
