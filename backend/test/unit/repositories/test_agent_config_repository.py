from __future__ import annotations

from types import SimpleNamespace

import pytest

from zixuetong.repositories.agent_config_repository import AgentConfigRepository


class _ScalarResult:
    def __init__(self, *, one=None, items=None):
        self._one = one
        self._items = items or []

    def scalar_one_or_none(self):
        return self._one

    def scalars(self):
        return SimpleNamespace(all=lambda: self._items)


class _FakeSession:
    def __init__(self, results):
        self.results = list(results)
        self.added = []
        self.commits = 0

    async def execute(self, _statement):
        return self.results.pop(0)

    def add(self, item):
        self.added.append(item)

    async def commit(self):
        self.commits += 1

    async def refresh(self, _item):
        return None


@pytest.mark.asyncio
async def test_get_or_create_default_uses_agent_as_only_scope():
    session = _FakeSession(
        [
            _ScalarResult(one=None),
            _ScalarResult(items=[]),
        ]
    )
    repo = AgentConfigRepository(session)

    config = await repo.get_or_create_default_for_agent(agent_id="ChatbotAgent", created_by="1")

    assert config.agent_id == "ChatbotAgent"
    assert config.name == "初始配置"
    assert config.is_default is True
    assert not hasattr(config, "department_id")
    assert session.added == [config]
    assert session.commits == 1


def test_belongs_to_agent_only_checks_agent_id():
    assert AgentConfigRepository.belongs_to_agent(SimpleNamespace(agent_id="ChatbotAgent"), "ChatbotAgent") is True
    assert AgentConfigRepository.belongs_to_agent(SimpleNamespace(agent_id="OtherAgent"), "ChatbotAgent") is False
