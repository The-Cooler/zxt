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
    depth: int = 1
    status: str = "pending"
    selected: bool = False
    error: str | None = None


class WebReadSession(BaseModel):
    session_id: str
    db_id: str
    root_url: str
    max_depth: int | None = None
    root_snapshot: WebPageSnapshot
    discovered_map: dict[str, DiscoveredLink] = Field(default_factory=dict)
    selected_urls: list[str] = Field(default_factory=list)
    created_by: str
