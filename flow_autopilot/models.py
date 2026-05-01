from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
import json
import uuid


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


@dataclass
class FrameItem:
    index: int
    stage: str
    goal: str
    prompt: str = ""
    image_path: str = ""
    evaluation: str = ""
    notes: str = ""
    next_step: str = ""
    status: str = "planned"

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "stage": self.stage,
            "goal": self.goal,
            "prompt": self.prompt,
            "image_path": self.image_path,
            "evaluation": self.evaluation,
            "notes": self.notes,
            "next_step": self.next_step,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FrameItem":
        return cls(
            index=int(data.get("index", 0)),
            stage=str(data.get("stage", "")),
            goal=str(data.get("goal", "")),
            prompt=str(data.get("prompt", "")),
            image_path=str(data.get("image_path", "")),
            evaluation=str(data.get("evaluation", "")),
            notes=str(data.get("notes", "")),
            next_step=str(data.get("next_step", "")),
            status=str(data.get("status", "planned")),
        )


@dataclass
class AppSettings:
    vision_backend: str = "ollama"
    ollama_url: str = "http://localhost:11434/api/generate"
    ollama_model: str = "llava:7b"
    lm_studio_url: str = "http://localhost:1234/v1/chat/completions"
    lm_studio_model: str = "local-vision-model"
    flow_url: str = "https://labs.google/fx/tools/flow"
    chrome_profile_dir: str = "chrome-profile"
    prompt_field_selector: str = ""
    generate_button_selector: str = ""
    result_selector: str = ""
    generation_wait_seconds: int = 90

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppSettings":
        settings = cls()
        for key in settings.__dict__:
            if key in data:
                setattr(settings, key, data[key])
        return settings


@dataclass
class Project:
    title: str
    concept: str
    style: str
    aspect_ratio: str
    frame_count: int
    stages_text: str
    folder: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)
    continuity_memory: str = ""
    frames: list[FrameItem] = field(default_factory=list)
    settings: AppSettings = field(default_factory=AppSettings)

    @property
    def path(self) -> Path:
        return Path(self.folder) / "project.json"

    @property
    def images_dir(self) -> Path:
        return Path(self.folder) / "images"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "concept": self.concept,
            "style": self.style,
            "aspect_ratio": self.aspect_ratio,
            "frame_count": self.frame_count,
            "stages_text": self.stages_text,
            "folder": self.folder,
            "created_at": self.created_at,
            "updated_at": now_iso(),
            "continuity_memory": self.continuity_memory,
            "frames": [frame.to_dict() for frame in self.frames],
            "settings": self.settings.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Project":
        return cls(
            id=str(data.get("id", uuid.uuid4().hex[:10])),
            title=str(data.get("title", "Untitled")),
            concept=str(data.get("concept", "")),
            style=str(data.get("style", "")),
            aspect_ratio=str(data.get("aspect_ratio", "16:9")),
            frame_count=int(data.get("frame_count", 8)),
            stages_text=str(data.get("stages_text", "")),
            folder=str(data.get("folder", "")),
            created_at=str(data.get("created_at", now_iso())),
            updated_at=str(data.get("updated_at", now_iso())),
            continuity_memory=str(data.get("continuity_memory", "")),
            frames=[FrameItem.from_dict(item) for item in data.get("frames", [])],
            settings=AppSettings.from_dict(data.get("settings", {})),
        )

    def save(self) -> None:
        Path(self.folder).mkdir(parents=True, exist_ok=True)
        self.images_dir.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as file:
            json.dump(self.to_dict(), file, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path: str | Path) -> "Project":
        project_path = Path(path)
        with project_path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        project = cls.from_dict(data)
        if not project.folder:
            project.folder = str(project_path.parent)
        return project
