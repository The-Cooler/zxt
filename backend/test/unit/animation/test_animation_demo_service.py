import os

import pytest

os.environ.setdefault("SILICONFLOW_API_KEY", "test-key")

from zixuetong.animation import AnimationDemoRequest, create_animation_demo
from zixuetong.animation.schemas import AnimationDemoArtifact


def test_create_animation_demo_builds_valid_artifact():
    demo = create_animation_demo(
        AnimationDemoRequest(
            query="用动画解释二分查找",
            concept="二分查找",
            subject="algorithm",
            explanation_steps=[
                "先确定有序数组和目标值。",
                "比较中间元素并排除一半区间。",
                "重复缩小区间直到找到目标。",
            ],
        )
    )

    assert demo.type == "animation_demo"
    assert demo.renderer == "html_canvas"
    assert demo.subject == "algorithm"
    assert demo.title == "二分查找 的动画演示"
    assert len(demo.scenes) == 3
    assert demo.duration_seconds <= 60
    AnimationDemoArtifact.model_validate(demo.model_dump())


def test_create_animation_demo_infers_steps_when_missing():
    demo = create_animation_demo(AnimationDemoRequest(query="链式法则为什么要先求内层再求外层？", concept="链式法则"))

    assert len(demo.scenes) >= 1
    assert demo.scenes[0].elements
    assert demo.scenes[0].actions


def test_create_animation_demo_limits_explanation_steps():
    demo = create_animation_demo(
        AnimationDemoRequest(
            query="解释一个很长的过程",
            concept="复杂过程",
            explanation_steps=[f"步骤 {index}" for index in range(10)],
        )
    )

    assert len(demo.scenes) == 6


def test_animation_demo_rejects_too_long_total_duration():
    scene = create_animation_demo(
        AnimationDemoRequest(query="短动画", concept="短动画", explanation_steps=["第一步"])
    ).scenes[0]

    with pytest.raises(ValueError):
        AnimationDemoArtifact(
            id="demo",
            title="超长动画",
            duration_seconds=60,
            scenes=[scene.model_copy(update={"duration_seconds": 30}) for _ in range(3)],
        )
