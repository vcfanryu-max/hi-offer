from pathlib import Path

from backend.ai.prompts.loader import TASKS, load_prompt

ROOT = Path(__file__).resolve().parents[1]
PROMPT_ROOT = ROOT / "backend" / "ai" / "prompts"


def test_only_canonical_six_prompt_directories_exist():
    directories = {path.name for path in PROMPT_ROOT.iterdir() if path.is_dir() and not path.name.startswith("__")}
    assert directories == {"resume_structure", "jd_analysis", "match_analysis", "hr_message", "resume_advice", "structured_repair"}
    assert directories == set(TASKS)
    assert not (ROOT / "prompt_library").exists()


def test_formal_prompt_versions_are_present_and_loaded_from_disk():
    expected = {"resume_structure": "v1", "jd_analysis": "v1", "match_analysis": "v2", "hr_message": "v2", "resume_advice": "v2", "structured_repair": "v1"}
    for task, version in expected.items():
        content = load_prompt(task, version)
        assert len(content) > 500
        assert "Output" in content or "输出" in content
