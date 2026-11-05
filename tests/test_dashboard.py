"""
test_dashboard.py: every dashboard page renders without errors, on mock and "real" data.

Why this exists
---------------
The dashboard is the presentation's visual aid; a crash on stage is not an
option. Streamlit's AppTest runs the app headlessly (no browser) and reports
any exception. Data come from a temporary folder (GP4_DASHBOARD_DATA), never
from the project's data/ folder.
"""

import dataclasses

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from gp4.config import PROJECT_ROOT, load_config, verify_stimuli
from gp4.llm_client import MockClient
from gp4.run_experiment import run_experiment

APP = str(PROJECT_ROOT / "app" / "streamlit_app.py")
PAGES = ["1. Overview", "2. Original study", "3. AI-agent system", "4. Results", "5. Human vs AI",
         "6. Explore data", "7. Limitations"]


def make_data(root, scenario, as_real=False):
    """Create one mock run under root/mock (or a relabelled copy under root/real)."""
    config = dataclasses.replace(load_config(), mediation_bootstrap_samples=200)
    out = run_experiment(config, "main", MockClient(config, scenario, verify_stimuli()), dry_run=True,
                         echo=False, out_dir=root / "mock")
    if as_real:  # a stand-in for live data: same rows, dry_run False, in data/real
        (root / "real").mkdir()
        frame = pd.read_csv(out.csv_path)
        frame["dry_run"] = False
        frame["model"] = "gpt-4o-mini"
        frame.to_csv(root / "real" / out.csv_path.name, index=False)
        out.csv_path.unlink()


def render(monkeypatch, root, page):
    monkeypatch.setenv("GP4_DASHBOARD_DATA", str(root))
    at = AppTest.from_file(APP, default_timeout=120)
    at.run()
    at.sidebar.radio[0].set_value(page).run()
    return at


@pytest.mark.parametrize("scenario", ["fake_effect", "identical", "mixed"])
@pytest.mark.parametrize("page", PAGES)
def test_every_page_renders_on_mock_data_with_banner(monkeypatch, tmp_path, scenario, page):
    make_data(tmp_path, scenario)
    at = render(monkeypatch, tmp_path, page)
    assert not at.exception, at.exception
    assert any("MOCK DATA, NOT RESULTS" in e.value for e in at.error)


@pytest.mark.parametrize("page", PAGES)
def test_real_data_has_no_mock_banner(monkeypatch, tmp_path, page):
    make_data(tmp_path, "fake_effect", as_real=True)
    at = render(monkeypatch, tmp_path, page)
    assert not at.exception, at.exception
    assert not any("MOCK DATA" in e.value for e in at.error)


def test_no_data_message(monkeypatch, tmp_path):
    monkeypatch.setenv("GP4_DASHBOARD_DATA", str(tmp_path))
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    assert not at.exception and at.title[0].value == "No data yet"


def test_run_page_hidden_by_default(monkeypatch, tmp_path):
    make_data(tmp_path, "normal")
    at = render(monkeypatch, tmp_path, "1. Overview")
    assert "8. Run experiment" not in at.sidebar.radio[0].options


def test_smoke_file_gets_a_notice_and_main_is_preferred(monkeypatch, tmp_path):
    config = dataclasses.replace(load_config(), mediation_bootstrap_samples=200)
    client = MockClient(config, "normal", verify_stimuli())
    run_experiment(config, "main", client, dry_run=True, n_agents=12, echo=False, out_dir=tmp_path / "mock")
    import time
    time.sleep(1.1)  # the smoke file is newer
    run_experiment(config, "smoke", client, dry_run=True, echo=False, out_dir=tmp_path / "mock")
    monkeypatch.setenv("GP4_DASHBOARD_DATA", str(tmp_path))
    at = AppTest.from_file(APP, default_timeout=120)
    at.run()
    assert "| main |" in at.sidebar.selectbox[0].value  # main opens by default, even though smoke is newer
    labels = at.sidebar.selectbox[0].options
    at.sidebar.selectbox[0].set_value([l for l in labels if "| smoke |" in l][0]).run()
    assert not at.exception and any("SMOKE TEST" in w.value for w in at.warning)


def test_first_main_run_is_primary_and_repeats_are_flagged(monkeypatch, tmp_path):
    import time
    config = dataclasses.replace(load_config(), mediation_bootstrap_samples=200)
    client = MockClient(config, "normal", verify_stimuli())
    first = run_experiment(config, "main", client, dry_run=True, n_agents=12, echo=False, out_dir=tmp_path / "mock")
    time.sleep(1.1)
    run_experiment(config, "main", client, dry_run=True, n_agents=12, echo=False, out_dir=tmp_path / "mock")
    (tmp_path / "real").mkdir()
    for csv in sorted((tmp_path / "mock").glob("*.csv")):  # stand-ins for two live main runs
        frame = pd.read_csv(csv)
        frame["dry_run"] = False
        frame.to_csv(tmp_path / "real" / csv.name, index=False)
        csv.unlink()
    monkeypatch.setenv("GP4_DASHBOARD_DATA", str(tmp_path))
    at = AppTest.from_file(APP, default_timeout=120)
    at.run()
    selected = at.sidebar.selectbox[0].value
    assert "PRIMARY" in selected and first.run_id[:8] in selected.replace("-", "")
    repeat = [l for l in at.sidebar.selectbox[0].options if "repeat" in l][0]
    at.sidebar.selectbox[0].set_value(repeat).run()
    assert not at.exception and any("REPEAT RUN" in w.value for w in at.warning)
