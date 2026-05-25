from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from yuxi.agents.backends.sandbox import paths as workspace_paths
from yuxi.services import learning_plan_service as svc


def test_learning_overview_returns_empty_when_files_are_missing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(workspace_paths.conf, "save_dir", str(tmp_path))

    overview = svc.get_learning_overview(SimpleNamespace(id="user-1"))

    assert overview == {
        "profile_exists": False,
        "index_exists": False,
        "plans": [],
        "new_topic_prompt": "我想开始一个新的学习主题：",
    }


def test_learning_overview_parses_registered_markdown_plans(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(workspace_paths.conf, "save_dir", str(tmp_path))
    user = SimpleNamespace(id="user-1")
    root = svc.learning_workspace_root(user)
    (root / "learning-profile.md").write_text("# 画像\n", encoding="utf-8")
    plans_dir = root / "learning-plans"
    plans_dir.mkdir(parents=True)
    (plans_dir / "index.md").write_text(
        "\n".join(
            [
                "# 学习计划",
                "",
                "| 主题 | 文件路径 | 状态 | 最近更新时间 |",
                "| --- | --- | --- | --- |",
                "| Java | /home/gem/user-data/workspace/learning-plans/java.md | 进行中 | 2026-06-08 |",
                "| 机器学习 | learning-plans/ml.md | 暂停 | 2026-06-01 |",
                "",
            ]
        ),
        encoding="utf-8",
    )

    overview = svc.get_learning_overview(user)

    assert overview["profile_exists"] is True
    assert overview["index_exists"] is True
    assert overview["plans"] == [
        {
            "topic": "Java",
            "file_path": "/home/gem/user-data/workspace/learning-plans/java.md",
            "status": "进行中",
            "updated_at": "2026-06-08",
        },
        {
            "topic": "机器学习",
            "file_path": "learning-plans/ml.md",
            "status": "暂停",
            "updated_at": "2026-06-01",
        },
    ]


def test_learning_workspace_root_rejects_invalid_user_id(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(workspace_paths.conf, "save_dir", str(tmp_path))

    with pytest.raises(HTTPException) as exc_info:
        svc.learning_workspace_root(SimpleNamespace(id="../other-user"))

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_chatbot_agent_metadata_describes_learning_assistant() -> None:
    from yuxi.agents.buildin.chatbot.graph import ChatbotAgent

    info = await ChatbotAgent().get_info(include_configurable_items=False)

    assert info["name"] == "学习助手"
    assert "学习计划" in info["description"]
    assert any("学习" in example or "知识库" in example for example in info["metadata"]["examples"])
