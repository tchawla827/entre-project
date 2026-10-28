"""Rebuild and run the research project from one command.

Windows: py -3.12 run_project.py
POSIX:   python3.12 run_project.py

Requires Python 3.12, internet for the first data fetch, and a copy of this
repository including the original locally supplied DaFiF source files.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time
import venv


ROOT = Path(__file__).resolve().parent
ENV = ROOT / ".venv"
PYTHON = ENV / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
LOG = ROOT / "reports" / "setup" / "last_run.json"


def steps(python: Path, *, offline: bool) -> list[tuple[str, list[str]]]:
    exe = str(python)
    stages: list[tuple[str, list[str]]] = []
    if not offline:
        stages.append(("Fetch public data", [exe, "-m", "src.data_pipeline.cli", "fetch", "--all"]))
    stages.extend([
        ("Curate data", [exe, "-m", "src.data_pipeline.cli", "build", "--all"]),
        ("Validate data", [exe, "-m", "src.data_pipeline.cli", "validate", "--all"]),
        ("Report data", [exe, "-m", "src.data_pipeline.cli", "report", "--all"]),
        ("Train bounded study models", [exe, "-m", "src.models.cli", "all"]),
        ("Simulate air route", [exe, "-m", "src.digital_twin.cli", "simulate", "--all"]),
        ("Simulate sea route", [exe, "-m", "src.digital_twin.cli", "simulate", "--all", "--route", "sea"]),
        ("Analyze thermal twin", [exe, "-m", "src.digital_twin.cli", "analyze", "--all"]),
        ("Validate thermal twin", [exe, "-m", "src.digital_twin.cli", "validate", "--all"]),
        ("Integrate route experiments", [exe, "-m", "src.integration.cli", "run", "--all"]),
        ("Analyze integrated results", [exe, "-m", "src.integration.cli", "analyze", "--all"]),
        ("Validate integrated results", [exe, "-m", "src.integration.cli", "validate", "--all"]),
        ("Run regression tests", [exe, "-m", "pytest", "tests/setup", "tests/dashboard", "tests/integration",
                                  "tests/digital_twin", "tests/models", "tests/data_pipeline", "-q"]),
    ])
    return stages


def check_local_sources() -> None:
    required = [ROOT / "combined_dataset.csv", ROOT / "Data_IIT2023150" / "Data" / "Dataset"]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError("Original locally supplied source files missing: " + ", ".join(missing))


def check_offline_sources() -> None:
    required = [ROOT / "data/raw/discovery/dafif_article.bin",
                ROOT / "data/raw/external/catfish_storage_stability_package_level_data.csv",
                ROOT / "data/raw/external/coldroom_preprocessed.zip",
                ROOT / "data/raw/external/10C_OP.csv",
                ROOT / "data/raw/trout_selected/tvc_individual_measurements.csv"]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file()]
    if len(list((ROOT / "data/raw/dafif_official").glob("*.xlsx"))) < 63:
        missing.append("data/raw/dafif_official (63 sensor workbooks)")
    if len(list((ROOT / "data/raw/mpeda").glob("*.xlsx"))) < 3:
        missing.append("data/raw/mpeda (3 spreadsheets)")
    if len(list((ROOT / "data/raw/trout_selected").rglob("sensors/*.csv"))) < 210:
        missing.append("data/raw/trout_selected (210 sensor CSVs)")
    if missing:
        raise FileNotFoundError("Offline raw data incomplete: " + ", ".join(missing) + ". Rerun without --offline to fetch.")


def run_stage(name: str, command: list[str], history: list[dict]) -> None:
    print(f"\n[{len(history)+1}] {name}", flush=True)
    started = time.perf_counter()
    code = subprocess.run(command, cwd=ROOT, check=False).returncode
    history.append({"stage": name, "command": command, "exit_code": code,
                    "seconds": round(time.perf_counter() - started, 2)})
    if code:
        raise RuntimeError(f"{name} failed with exit code {code}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Install, rebuild, validate and launch the fisheries thermal dashboard")
    parser.add_argument("--offline", action="store_true", help="Use already downloaded raw sources")
    parser.add_argument("--skip-install", action="store_true", help="Use an existing .venv (for development)")
    parser.add_argument("--no-dashboard", action="store_true", help="Exit after rebuilding and testing")
    parser.add_argument("--dry-run", action="store_true", help="Print the stages without executing them")
    args = parser.parse_args(argv)

    if sys.version_info[:2] != (3, 12):
        parser.error("Python 3.12 is required for the pinned environment. Use py -3.12 or python3.12.")
    history: list[dict] = []
    if args.dry_run:
        for name, command in steps(PYTHON, offline=args.offline):
            print(f"{name}: {' '.join(command)}")
        if not args.no_dashboard:
            print(f"Launch dashboard: {PYTHON} -m streamlit run app.py")
        return 0

    try:
        check_local_sources()
        if args.offline:
            check_offline_sources()
        if not args.skip_install:
            if not PYTHON.is_file():
                print(f"Creating {ENV}", flush=True)
                venv.EnvBuilder(with_pip=True).create(ENV)
            run_stage("Install pinned dependencies", [str(PYTHON), "-m", "pip", "install", "-r", "requirements.txt"], history)
        elif not PYTHON.is_file():
            raise FileNotFoundError("--skip-install requires an existing .venv; rerun without that flag")
        for name, command in steps(PYTHON, offline=args.offline):
            run_stage(name, command, history)
    except (FileNotFoundError, RuntimeError, OSError) as exc:
        print(f"\nSetup stopped: {exc}", file=sys.stderr, flush=True)
        status = "FAILED"
    else:
        status = "PASS"
    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_text(json.dumps({"created_utc": datetime.now(timezone.utc).isoformat(),
                               "status": status, "offline": args.offline, "stages": history}, indent=2),
                   encoding="utf-8")
    print(f"\nSetup {status}. Stage log: {LOG.relative_to(ROOT)}", flush=True)
    if status != "PASS":
        return 1
    if not args.no_dashboard:
        print("\nOpening dashboard at http://localhost:8501 (Ctrl+C to stop)", flush=True)
        return subprocess.run([str(PYTHON), "-m", "streamlit", "run", "app.py"], cwd=ROOT, check=False).returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
