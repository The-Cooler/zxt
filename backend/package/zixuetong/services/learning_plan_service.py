from __future__ import annotations

import re
from pathlib import Path

from fastapi import HTTPException

from zixuetong.agents.backends.sandbox.paths import _global_user_data_dir, ensure_workspace_default_files
from zixuetong.storage.postgres.models_business import User
from zixuetong.utils.paths import VIRTUAL_PATH_WORKSPACE, WORKSPACE_DIR_NAME

LEARNING_PROFILE_FILE_NAME = "learning-profile.md"
LEARNING_PLANS_DIR_NAME = "learning-plans"
LEARNING_PLANS_INDEX_FILE_NAME = "index.md"
NEW_TOPIC_PROMPT = "我想开始一个新的学习主题："
REMINDER_TIME_COLUMN = "提醒时间"
DISABLED_REMINDER_VALUES = {"", "关闭", "不提醒", "off", "none", "-"}
INACTIVE_PLAN_STATUSES = {"已完成", "完成", "暂停", "已暂停", "关闭", "取消"}


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


def _format_markdown_table_row(cells: list[str]) -> str:
    return f"| {' | '.join(cells)} |"


def _is_separator_row(cells: list[str]) -> bool:
    if not cells:
        return False
    return all(set(cell.replace(" ", "")) <= {"-", ":"} and "-" in cell for cell in cells)


def normalize_reminder_time(value: str | None) -> str:
    normalized = str(value or "").strip()
    if normalized.lower() in DISABLED_REMINDER_VALUES:
        return ""
    if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", normalized):
        raise ValueError("提醒时间必须使用 HH:MM 格式")
    return normalized


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
        reminder_index = column_map.get(REMINDER_TIME_COLUMN)
        raw_reminder_time = cells[reminder_index].strip() if reminder_index is not None else ""
        try:
            reminder_time = normalize_reminder_time(raw_reminder_time)
        except ValueError:
            reminder_time = ""
        plans.append(
            {
                "topic": topic,
                "file_path": cells[column_map["文件路径"]].strip(),
                "status": cells[column_map["状态"]].strip(),
                "reminder_time": reminder_time,
                # reminder_time 为空有两种来源：用户显式关闭，或从未设置。
                # 保留原始单元格内容以便前端区分，避免把「已关闭」显示为「未安排提醒」。
                "reminder_raw": raw_reminder_time,
                "updated_at": cells[column_map["最近更新时间"]].strip(),
            }
        )

    return plans


def _resolve_plan_path(root: Path, file_path: str) -> Path | None:
    normalized = str(file_path or "").strip().replace("\\", "/")
    virtual_prefix = f"{VIRTUAL_PATH_WORKSPACE.rstrip('/')}/"
    if normalized.startswith(virtual_prefix):
        normalized = normalized[len(virtual_prefix) :]
    elif normalized.startswith("/"):
        return None

    candidate = (root / normalized).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    if candidate.suffix.lower() != ".md":
        return None
    return candidate


def _read_plan_progress(root: Path, file_path: str) -> dict[str, object]:
    plan_path = _resolve_plan_path(root, file_path)
    if plan_path is None or not plan_path.is_file():
        return {
            "completed_tasks": 0,
            "total_tasks": 0,
            "progress_percent": 0,
            "next_task": "",
        }

    completed_tasks = 0
    tasks: list[tuple[bool, str]] = []
    task_pattern = re.compile(r"^\s*[-*]\s+\[([ xX])\]\s+(.+?)\s*$")
    for line in plan_path.read_text(encoding="utf-8").splitlines():
        match = task_pattern.match(line)
        if not match:
            continue
        completed = match.group(1).lower() == "x"
        task = match.group(2).strip()
        tasks.append((completed, task))
        if completed:
            completed_tasks += 1

    total_tasks = len(tasks)
    next_task = next((task for completed, task in tasks if not completed), "")
    progress_percent = round(completed_tasks / total_tasks * 100) if total_tasks else 0
    return {
        "completed_tasks": completed_tasks,
        "total_tasks": total_tasks,
        "progress_percent": progress_percent,
        "next_task": next_task,
    }


LEARNING_PROFILE_FIELDS = {
    "学习方向": "learning_direction",
    "学习偏好": "learning_preferences",
    "已有知识水平": "knowledge_level",
    "薄弱点": "weaknesses",
    "学习历史": "learning_history",
}


def get_learning_profile(user: User) -> dict[str, str]:
    profile = {field: "" for field in LEARNING_PROFILE_FIELDS.values()}
    profile_path = learning_workspace_root(user) / LEARNING_PROFILE_FILE_NAME
    if not profile_path.is_file():
        return profile

    current_field: str | None = None
    content: dict[str, list[str]] = {field: [] for field in profile}
    for line in profile_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            current_field = LEARNING_PROFILE_FIELDS.get(line[3:].strip())
            continue
        if current_field is not None:
            content[current_field].append(line)

    return {field: "\n".join(lines).strip() for field, lines in content.items()}


def save_learning_profile(user: User, profile: dict[str, str]) -> dict[str, str]:
    normalized = {field: str(profile.get(field, "")).strip() for field in LEARNING_PROFILE_FIELDS.values()}
    sections = ["# 学习用户画像", ""]
    for title, field in LEARNING_PROFILE_FIELDS.items():
        sections.extend([f"## {title}", normalized[field], ""])

    profile_path = learning_workspace_root(user) / LEARNING_PROFILE_FILE_NAME
    profile_path.write_text("\n".join(sections).rstrip() + "\n", encoding="utf-8")
    return normalized


def get_learning_overview(user: User) -> dict:
    root = learning_workspace_root(user)
    profile_path = root / LEARNING_PROFILE_FILE_NAME
    index_path = root / LEARNING_PLANS_DIR_NAME / LEARNING_PLANS_INDEX_FILE_NAME

    plans: list[dict[str, object]] = []
    if index_path.is_file():
        for plan in _parse_learning_plan_index(index_path.read_text(encoding="utf-8")):
            plans.append({**plan, **_read_plan_progress(root, plan["file_path"])})

    return {
        "profile_exists": profile_path.is_file(),
        "index_exists": index_path.is_file(),
        "plans": plans,
        "new_topic_prompt": NEW_TOPIC_PROMPT,
    }


def set_learning_plan_reminder(user: User, file_path: str, reminder_time: str | None) -> dict[str, object]:
    normalized_time = normalize_reminder_time(reminder_time)
    root = learning_workspace_root(user)
    index_path = root / LEARNING_PLANS_DIR_NAME / LEARNING_PLANS_INDEX_FILE_NAME
    if not index_path.is_file():
        raise HTTPException(status_code=404, detail="学习计划总表不存在")

    target_path = _resolve_plan_path(root, file_path)
    if target_path is None:
        raise HTTPException(status_code=400, detail="学习计划路径无效")

    lines = index_path.read_text(encoding="utf-8").splitlines()
    header_index: int | None = None
    headers: list[str] = []
    for index, line in enumerate(lines):
        cells = _split_markdown_table_row(line)
        if all(column in cells for column in ("主题", "文件路径", "状态", "最近更新时间")):
            header_index = index
            headers = cells
            break
    if header_index is None:
        raise HTTPException(status_code=422, detail="学习计划总表格式无效")

    original_headers = list(headers)
    reminder_index = headers.index(REMINDER_TIME_COLUMN) if REMINDER_TIME_COLUMN in headers else headers.index("最近更新时间")
    adding_column = REMINDER_TIME_COLUMN not in headers
    if adding_column:
        headers.insert(reminder_index, REMINDER_TIME_COLUMN)
        lines[header_index] = _format_markdown_table_row(headers)

    path_index = headers.index("文件路径")
    matched_plan: dict[str, object] | None = None
    for index in range(header_index + 1, len(lines)):
        cells = _split_markdown_table_row(lines[index])
        if not cells:
            if index > header_index + 1:
                break
            continue
        if _is_separator_row(cells):
            if adding_column and len(cells) == len(original_headers):
                cells.insert(reminder_index, "---")
                lines[index] = _format_markdown_table_row(cells)
            continue
        if len(cells) < len(original_headers):
            cells.extend([""] * (len(original_headers) - len(cells)))
        if adding_column:
            cells.insert(reminder_index, "关闭")
        elif len(cells) < len(headers):
            cells.extend([""] * (len(headers) - len(cells)))

        row_path = _resolve_plan_path(root, cells[path_index])
        if row_path == target_path:
            cells[reminder_index] = normalized_time or "关闭"
            matched_plan = {
                "topic": cells[headers.index("主题")],
                "file_path": cells[path_index],
                "status": cells[headers.index("状态")],
                "reminder_time": normalized_time,
                "updated_at": cells[headers.index("最近更新时间")],
            }
        lines[index] = _format_markdown_table_row(cells)

    if matched_plan is None:
        raise HTTPException(status_code=404, detail="学习计划不存在")

    index_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return {**matched_plan, **_read_plan_progress(root, str(matched_plan["file_path"]))}


def get_due_learning_plans(user: User, current_time: str) -> list[dict[str, object]]:
    plans = get_learning_overview(user)["plans"]
    return [
        plan
        for plan in plans
        if plan["reminder_time"]
        and str(plan["reminder_time"]) <= current_time
        and str(plan["status"]).strip() not in INACTIVE_PLAN_STATUSES
    ]


def build_learning_reminder(plan: dict[str, object]) -> tuple[str, str]:
    topic = str(plan["topic"])
    completed = int(plan["completed_tasks"])
    total = int(plan["total_tasks"])
    next_task = str(plan["next_task"])
    title = f"学习提醒：{topic}"

    if total and next_task:
        body = f"“{topic}”已完成 {completed}/{total} 项（{plan['progress_percent']}%）。下一步：{next_task}。"
    elif total and completed == total:
        body = f"“{topic}”的任务清单已全部完成，请进行复盘并更新计划状态。"
    else:
        body = f"到了“{topic}”的计划学习时间，请根据当前进度继续学习并记录本次进展。"
    return title, body
