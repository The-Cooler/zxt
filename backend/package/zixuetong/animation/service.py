from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime

from zixuetong.animation.schemas import (
    MAX_DURATION_SECONDS,
    AnimationAction,
    AnimationDemoArtifact,
    AnimationDemoRequest,
    AnimationElement,
    AnimationScene,
)


def _short_text(value: str, fallback: str, limit: int = 80) -> str:
    text = re.sub(r"\s+", " ", (value or "").strip())
    if not text:
        return fallback
    return text[:limit]


def _infer_steps(request: AnimationDemoRequest) -> list[str]:
    if request.explanation_steps:
        return request.explanation_steps[:6]

    query = request.query.strip()
    parts = [part.strip() for part in re.split(r"[。！？!?；;\n]+", query) if part.strip()]
    if len(parts) >= 2:
        return parts[:6]

    concept = _short_text(request.concept or request.query, "这个知识点", 48)
    return [
        f"先识别 {concept} 中的关键对象。",
        "再观察这些对象之间如何发生变化或传递影响。",
        "最后把变化过程串起来，得到可以复述的理解路径。",
    ]


def _build_scene(index: int, step: str, total: int) -> AnimationScene:
    scene_id = f"s{index + 1}"
    previous_label = "已知" if index == 0 else f"步骤 {index}"
    current_label = f"步骤 {index + 1}"
    next_label = "结论" if index == total - 1 else f"步骤 {index + 2}"
    y = 46

    elements = [
        AnimationElement(id=f"{scene_id}-previous", type="box", label=previous_label, x=10, y=y, color="muted"),
        AnimationElement(id=f"{scene_id}-current", type="box", label=current_label, x=40, y=y, color="primary"),
        AnimationElement(id=f"{scene_id}-next", type="box", label=next_label, x=70, y=y, color="accent"),
        AnimationElement(
            id=f"{scene_id}-caption",
            type="text",
            label=_short_text(step, "说明", 42),
            x=10,
            y=78,
            width=80,
            height=12,
            color="text",
        ),
    ]
    actions = [
        AnimationAction(type="fade_in", at=0, duration=0.6, element_id=f"{scene_id}-previous"),
        AnimationAction(type="fade_in", at=0.6, duration=0.6, element_id=f"{scene_id}-current"),
        AnimationAction(
            type="connect",
            at=1.2,
            duration=0.8,
            element_id=f"{scene_id}-previous",
            target_id=f"{scene_id}-current",
        ),
        AnimationAction(type="highlight", at=2.0, duration=1.4, element_id=f"{scene_id}-current"),
        AnimationAction(type="fade_in", at=3.0, duration=0.6, element_id=f"{scene_id}-next"),
        AnimationAction(
            type="connect",
            at=3.5,
            duration=0.8,
            element_id=f"{scene_id}-current",
            target_id=f"{scene_id}-next",
        ),
        AnimationAction(type="caption", at=4.2, duration=2.4, element_id=f"{scene_id}-caption", text=step),
    ]
    return AnimationScene(
        title=f"第 {index + 1} 步",
        narration=step,
        duration_seconds=7,
        elements=elements,
        actions=actions,
    )


def create_animation_demo(request: AnimationDemoRequest) -> AnimationDemoArtifact:
    steps = _infer_steps(request)
    scenes = [_build_scene(index, step, len(steps)) for index, step in enumerate(steps)]
    duration = min(sum(scene.duration_seconds for scene in scenes), MAX_DURATION_SECONDS)
    concept = _short_text(request.concept or request.query, "知识点", 48)

    return AnimationDemoArtifact(
        id=f"anim_{uuid.uuid4().hex[:12]}",
        title=f"{concept} 的动画演示",
        subject=request.subject or "general",
        duration_seconds=duration,
        scenes=scenes,
        source={
            "query": request.query,
            "thread_id": request.thread_id,
            "source_message_id": request.source_message_id,
            "knowledge_base_ids": request.knowledge_base_ids,
            "audience": request.audience,
            "created_at": datetime.now(UTC).isoformat(),
        },
    )
