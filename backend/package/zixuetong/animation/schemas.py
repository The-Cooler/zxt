from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


MAX_SCENES = 10
MAX_ACTIONS_PER_SCENE = 100
MAX_DURATION_SECONDS = 60


class AnimationElement(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    type: Literal["text", "box", "circle", "arrow", "formula"] = "box"
    label: str = Field(default="", max_length=120)
    x: float = Field(ge=0, le=100)
    y: float = Field(ge=0, le=100)
    width: float = Field(default=20, ge=4, le=80)
    height: float = Field(default=10, ge=4, le=60)
    color: str = Field(default="primary", max_length=32)


class AnimationAction(BaseModel):
    type: Literal["fade_in", "highlight", "move", "connect", "wait", "caption"]
    at: float = Field(ge=0)
    duration: float = Field(default=1.2, gt=0, le=10)
    element_id: str | None = Field(default=None, max_length=64)
    target_id: str | None = Field(default=None, max_length=64)
    text: str | None = Field(default=None, max_length=200)
    to: dict[str, float] | None = None


class AnimationScene(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    narration: str = Field(default="", max_length=500)
    duration_seconds: float = Field(default=8, gt=0, le=MAX_DURATION_SECONDS)
    elements: list[AnimationElement] = Field(default_factory=list, max_length=20)
    actions: list[AnimationAction] = Field(default_factory=list, max_length=MAX_ACTIONS_PER_SCENE)


class AnimationDemoArtifact(BaseModel):
    type: Literal["animation_demo"] = "animation_demo"
    version: Literal["1"] = "1"
    id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=120)
    subject: str = Field(default="general", max_length=64)
    renderer: Literal["html_canvas"] = "html_canvas"
    duration_seconds: float = Field(gt=0, le=MAX_DURATION_SECONDS)
    scenes: list[AnimationScene] = Field(min_length=1, max_length=MAX_SCENES)
    source: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def ensure_duration_matches_scenes(self):
        scene_duration = sum(scene.duration_seconds for scene in self.scenes)
        if scene_duration > MAX_DURATION_SECONDS:
            raise ValueError(f"动画总时长不能超过 {MAX_DURATION_SECONDS} 秒")
        self.duration_seconds = min(self.duration_seconds, scene_duration or self.duration_seconds)
        return self


class AnimationDemoRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    concept: str | None = Field(default=None, max_length=120)
    subject: str | None = Field(default=None, max_length=64)
    audience: str | None = Field(default=None, max_length=80)
    explanation_steps: list[str] = Field(default_factory=list, max_length=MAX_SCENES)
    thread_id: str | None = Field(default=None, max_length=128)
    source_message_id: int | None = None
    knowledge_base_ids: list[int] = Field(default_factory=list, max_length=20)

    @field_validator("explanation_steps")
    @classmethod
    def clean_steps(cls, steps: list[str]) -> list[str]:
        return [step.strip()[:300] for step in steps if isinstance(step, str) and step.strip()]


class AnimationDemoResponse(BaseModel):
    success: bool = True
    demo: AnimationDemoArtifact
