from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException

from zixuetong.agents.backends.sandbox.paths import _global_user_data_dir, ensure_workspace_default_files
from zixuetong.storage.postgres.models_business import User
from zixuetong.utils.paths import WORKSPACE_DIR_NAME

LEARNING_PROFILE_FILE_NAME = "learning-profile.md"
LEARNING_PLANS_DIR_NAME = "learning-plans"
LEARNING_PLANS_INDEX_FILE_NAME = "index.md"
NEW_TOPIC_PROMPT = "我想开始一个新的学习主题："


def learning_workspace_root(user: User) -> Path:
    try:
        user_data_root = _global_user_data_dir(str(user.id)).resolve()
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="Access denied") from exc

    root = user_data_root / WORKSPACE_DIR_NAME
    if root.is_symlink():
        raise HTTPException(status_code=403, detail="Access denied")
    root.mkdir(parents=True, exist_ok=True)
    resolved_root = root.resolve()
    try:
        resolved_root.relative_to(user_data_root)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="Access denied") from exc
    ensure_workspace_default_files(resolved_root)
    return resolved_root


def _split_markdown_table_row(line: str) -> list[str]:
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return []
    return [cell.strip() for cell in stripped.strip("|").split("|")]


def _is_separator_row(cells: list[str]) -> bool:
    if not cells:
        return False
    return all(set(cell.replace(" ", "")) <= {"-", ":"} and "-" in cell for cell in cells)


def _parse_learning_plan_index(content: str) -> list[dict[str, str]]:
    plans: list[dict[str, str]] = []
    headers: list[str] | None = None
    column_map: dict[str, int] = {}
    required_columns = ["主题", "文件路径", "状态", "最近更新时间"]

    for line in content.splitlines():
        cells = _split_markdown_table_row(line)
        if not cells:
            continue
        if _is_separator_row(cells):
            continue
        if headers is None:
            candidate_map = {name: index for index, name in enumerate(cells)}
            if not all(name in candidate_map for name in required_columns):
                continue
            headers = cells
            column_map = candidate_map
            continue

        if len(cells) < len(headers):
            cells.extend([""] * (len(headers) - len(cells)))

        topic = cells[column_map["主题"]].strip()
        if not topic:
            continue
        plans.append(
            {
                "topic": topic,
                "file_path": cells[column_map["文件路径"]].strip(),
                "status": cells[column_map["状态"]].strip(),
                "updated_at": cells[column_map["最近更新时间"]].strip(),
            }
        )

    return plans


def get_learning_overview(user: User) -> dict:
    root = learning_workspace_root(user)
    profile_path = root / LEARNING_PROFILE_FILE_NAME
    index_path = root / LEARNING_PLANS_DIR_NAME / LEARNING_PLANS_INDEX_FILE_NAME

    plans: list[dict[str, str]] = []
    if index_path.is_file():
        plans = _parse_learning_plan_index(index_path.read_text(encoding="utf-8"))

    return {
        "profile_exists": profile_path.is_file(),
        "index_exists": index_path.is_file(),
        "plans": plans,
        "new_topic_prompt": NEW_TOPIC_PROMPT,
    }
