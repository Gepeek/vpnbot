from flow_autopilot.models import Project
from flow_autopilot.prompt_engine import build_initial_frames, build_next_prompt, split_stages


def make_project(tmp_path):
    return Project(
        title="Test",
        concept="Repair timelapse",
        style="realistic",
        aspect_ratio="16:9",
        frame_count=3,
        stages_text="before\nmiddle\nfinal",
        folder=str(tmp_path),
    )


def test_split_stages_keeps_requested_count():
    assert split_stages("a\nb\nc\nd", 2) == ["a", "b"]


def test_build_initial_frames(tmp_path):
    project = make_project(tmp_path)
    frames = build_initial_frames(project)
    assert len(frames) == 3
    assert "Repair timelapse" in frames[0].prompt
    assert frames[0].stage == "before"


def test_build_next_prompt_uses_evaluation(tmp_path):
    project = make_project(tmp_path)
    project.frames = build_initial_frames(project)
    project.frames[0].evaluation = "Фактически видно: old wallpaper and dusty floor"
    prompt = build_next_prompt(project, 0)
    assert "old wallpaper" in prompt
    assert project.frames[1].status == "ready"
