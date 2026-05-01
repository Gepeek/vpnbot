from __future__ import annotations

from pathlib import Path
from typing import Any
import base64
import json
import urllib.error
import urllib.request

from .models import FrameItem, Project
from .prompt_engine import build_analysis_instruction


class VisionError(RuntimeError):
    pass


def encode_image(path: str | Path) -> str:
    with Path(path).open("rb") as file:
        return base64.b64encode(file.read()).decode("ascii")


def post_json(url: str, payload: dict[str, Any], timeout: int = 180) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise VisionError(f"Не удалось подключиться к локальной модели: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise VisionError("Локальная модель вернула не JSON-ответ.") from exc


def analyze_with_ollama(project: Project, frame: FrameItem, previous: FrameItem | None) -> str:
    if not frame.image_path:
        raise VisionError("У кадра не указан путь к изображению.")
    prompt = build_analysis_instruction(project, frame, previous)
    payload = {
        "model": project.settings.ollama_model,
        "prompt": prompt,
        "images": [encode_image(frame.image_path)],
        "stream": False,
    }
    response = post_json(project.settings.ollama_url, payload)
    text = response.get("response")
    if not text:
        raise VisionError(f"Ollama не вернул текст анализа: {response}")
    return str(text).strip()


def analyze_with_lm_studio(project: Project, frame: FrameItem, previous: FrameItem | None) -> str:
    if not frame.image_path:
        raise VisionError("У кадра не указан путь к изображению.")
    prompt = build_analysis_instruction(project, frame, previous)
    image = encode_image(frame.image_path)
    payload = {
        "model": project.settings.lm_studio_model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image}"}},
                ],
            }
        ],
        "temperature": 0.2,
        "max_tokens": 800,
    }
    response = post_json(project.settings.lm_studio_url, payload)
    try:
        return str(response["choices"][0]["message"]["content"]).strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise VisionError(f"LM Studio не вернул текст анализа: {response}") from exc


def analyze_frame(project: Project, frame_index: int) -> str:
    if frame_index < 0 or frame_index >= len(project.frames):
        raise VisionError("Кадр не найден.")
    frame = project.frames[frame_index]
    previous = project.frames[frame_index - 1] if frame_index > 0 else None
    backend = project.settings.vision_backend.lower().strip()
    if backend == "ollama":
        return analyze_with_ollama(project, frame, previous)
    if backend in {"lmstudio", "lm_studio", "lm studio"}:
        return analyze_with_lm_studio(project, frame, previous)
    raise VisionError(f"Неизвестный vision backend: {project.settings.vision_backend}")
