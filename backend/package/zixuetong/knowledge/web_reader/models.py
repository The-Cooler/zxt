from __future__ import annotations

from pydantic import BaseModel, Field


class WebPageSnapshot(BaseModel):
    url: str
    final_url: str
    title: str = ""
    topic: str = ""
    text: str = ""
    html: str = ""
    content_hash: str = ""
    links: list[str] = Field(default_factory=list)
    depth: int = 0
    parent_url: str | None = None


class DiscoveredLink(BaseModel):
    url: str
    base_url: str
    parents: list[str] = Field(default_factory=list)
    similarity: float = 0.0
    topic: str = ""
    title: str = ""
    text: str = ""  # 页面文本内容
    html: str = ""  # 清理后的 HTML（已移除链接和图片）
    depth: int = 1
    status: str = "pending"
    selected: bool = False
    error: str | None = None


class CleanedWebPage(BaseModel):
    source_url: str
    title: str = ""
    path: str
    content_hash: str
    filename: str
    file_size: int


class WebReadSession(BaseModel):
    session_id: str
    db_id: str
    root_url: str
    max_depth: int | None = None
    root_snapshot: WebPageSnapshot
    discovered_map: dict[str, DiscoveredLink] = Field(default_factory=dict)
    selected_urls: list[str] = Field(default_factory=list)
    cleaned_pages: list[CleanedWebPage] = Field(default_factory=list)
    created_by: str
