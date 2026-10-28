from pathlib import Path

import pytest

import run_project


def test_plan_orders_every_phase_and_can_skip_fetch():
    online = run_project.steps(Path("python"), offline=False)
    offline = run_project.steps(Path("python"), offline=True)
    assert online[0][0] == "Fetch public data"
    assert offline[0][0] == "Curate data"
    names = [name for name, _ in online]
    assert names.index("Train bounded study models") < names.index("Integrate route experiments")
    assert names[-2:] == ["Validate integrated results", "Run regression tests"]
    assert all(command[0] == "python" for _, command in online)


def test_missing_local_inputs_fail_clearly(monkeypatch, tmp_path):
    monkeypatch.setattr(run_project, "ROOT", tmp_path)
    with pytest.raises(FileNotFoundError, match="Original locally supplied source files missing"):
        run_project.check_local_sources()


def test_missing_offline_raw_data_fail_clearly(monkeypatch, tmp_path):
    monkeypatch.setattr(run_project, "ROOT", tmp_path)
    with pytest.raises(FileNotFoundError, match="Rerun without --offline"):
        run_project.check_offline_sources()
