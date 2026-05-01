from __future__ import annotations

from .models import FrameItem, Project


DEFAULT_REPAIR_STAGES = [
    "исходное состояние комнаты до ремонта",
    "демонтаж старой отделки и вынос лишних предметов",
    "черновая подготовка стен, пола и потолка",
    "выравнивание и грунтовка поверхностей",
    "укладка пола и основные отделочные работы",
    "покраска или финишная отделка стен",
    "установка мебели, света и деталей",
    "финальный чистый результат после ремонта",
]


def split_stages(stages_text: str, frame_count: int) -> list[str]:
    raw = [line.strip(" -\t") for line in stages_text.replace("→", "\n").splitlines()]
    stages = [line for line in raw if line]
    if not stages:
        stages = DEFAULT_REPAIR_STAGES[:]
    if len(stages) >= frame_count:
        return stages[:frame_count]
    while len(stages) < frame_count:
        stages.append(DEFAULT_REPAIR_STAGES[min(len(stages), len(DEFAULT_REPAIR_STAGES) - 1)])
    return stages


def build_initial_frames(project: Project) -> list[FrameItem]:
    stages = split_stages(project.stages_text, project.frame_count)
    total = len(stages)
    frames: list[FrameItem] = []
    for index, stage in enumerate(stages, start=1):
        goal = f"Кадр {index}/{total}: {stage}. Прогресс ремонта должен быть логичным и постепенным."
        prompt = build_prompt(project, stage=stage, goal=goal, index=index, total=total)
        frames.append(FrameItem(index=index, stage=stage, goal=goal, prompt=prompt))
    return frames


def build_prompt(
    project: Project,
    stage: str,
    goal: str,
    index: int,
    total: int,
    previous_description: str = "",
    correction: str = "",
) -> str:
    parts = [
        "Create one realistic cinematic still image for a YouTube repair timelapse.",
        f"Video concept: {project.concept.strip()}",
        f"Current frame: {index} of {total}. Repair stage: {stage.strip()}",
        f"Frame goal: {goal.strip()}",
        f"Visual style: {project.style.strip() or 'realistic documentary renovation timelapse, natural light, consistent room layout'}",
        f"Aspect ratio: {project.aspect_ratio.strip() or '16:9'}",
        "Keep the same room geometry, camera position, lens feel, main walls, windows, doors, floor orientation, and lighting direction across the sequence.",
        "Show a believable intermediate renovation state. Do not jump directly to the final result unless this is the final frame.",
        "No text overlays, no logos, no captions, no watermarks, no people unless explicitly requested.",
    ]
    if project.continuity_memory.strip():
        parts.append(f"Continuity memory to preserve: {project.continuity_memory.strip()}")
    if previous_description.strip():
        parts.append(f"Actual previous frame looked like: {previous_description.strip()}")
    if correction.strip():
        parts.append(f"Correction for this frame: {correction.strip()}")
    return "\n".join(parts)


def build_next_prompt(project: Project, current_index: int) -> str:
    if current_index < 0 or current_index >= len(project.frames) - 1:
        return ""
    current = project.frames[current_index]
    next_frame = project.frames[current_index + 1]
    previous_description = current.evaluation or current.notes
    correction = current.next_step or "Continue only one logical renovation step forward from the actual previous frame."
    next_frame.prompt = build_prompt(
        project,
        stage=next_frame.stage,
        goal=next_frame.goal,
        index=next_frame.index,
        total=len(project.frames),
        previous_description=previous_description,
        correction=correction,
    )
    next_frame.status = "ready"
    return next_frame.prompt


def build_analysis_instruction(project: Project, frame: FrameItem, previous: FrameItem | None) -> str:
    previous_text = ""
    if previous:
        previous_text = f"Previous planned stage: {previous.stage}\nPrevious evaluation: {previous.evaluation or previous.notes}"
    return f"""
You are a continuity supervisor for a YouTube repair timelapse.

Analyze the attached image against the planned frame.

Project concept: {project.concept}
Project style: {project.style}
Continuity memory: {project.continuity_memory}
Planned stage: {frame.stage}
Planned goal: {frame.goal}
{previous_text}

Return concise Russian text with these exact labels:
Фактически видно:
Совпадение с планом:
Проблемы последовательности:
Что сохранить:
Следующий шаг:
Оценка 1-10:
""".strip()


def update_continuity_memory(project: Project, evaluation: str) -> None:
    keep_lines = []
    capture = False
    for line in evaluation.splitlines():
        lowered = line.lower()
        if lowered.startswith("что сохранить"):
            capture = True
            keep_lines.append(line.split(":", 1)[-1].strip())
            continue
        if capture and ":" in line:
            break
        if capture:
            keep_lines.append(line.strip())
    additions = " ".join(part for part in keep_lines if part)
    if additions:
        current = project.continuity_memory.strip()
        project.continuity_memory = (current + "\n" + additions).strip() if current else additions
