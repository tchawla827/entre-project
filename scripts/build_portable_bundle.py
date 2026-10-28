"""Package this project and a relocatable Python runtime for Windows x64.

Run using the project's working Python 3.12 environment. This build command
requires package access; the resulting RUN_PROJECT.cmd does not.
"""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / 'dist'
BUNDLE = DIST / 'Fisheries Cold Chain'
RUNTIME = BUNDLE / '.runtime'

LAUNCHER = r'''@echo off
setlocal
cd /d "%~dp0"
title Fisheries Cold Chain
set PYTHONHOME=
set PYTHONPATH=
set PYTHONNOUSERSITE=1
set PYTHONUTF8=1
set STREAMLIT_SERVER_HEADLESS=true
set STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
echo Fisheries Cold Chain - full rebuild and dashboard
echo.
if not exist ".runtime\python.exe" (
    echo The bundled Python runtime is missing. Extract the entire ZIP first.
    pause
    exit /b 1
)
echo Preparing the local Python environment...
".runtime\python.exe" -m venv --without-pip --system-site-packages ".venv"
if errorlevel 1 goto failed
".runtime\python.exe" run_project.py --offline --skip-install %*
if errorlevel 1 goto failed
exit /b 0
:failed
echo.
echo Setup stopped. Review the error above and reports\setup\last_run.json.
pause
exit /b 1
'''

QUICK_LAUNCHER = r'''@echo off
setlocal
cd /d "%~dp0"
title Fisheries Cold Chain Dashboard
set PYTHONHOME=
set PYTHONPATH=
set PYTHONNOUSERSITE=1
set PYTHONUTF8=1
set STREAMLIT_SERVER_HEADLESS=true
set STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
if not exist ".runtime\python.exe" (
    echo Extract the entire ZIP before running this launcher.
    pause
    exit /b 1
)
".runtime\python.exe" -m venv --without-pip --system-site-packages ".venv"
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m streamlit run app.py
if errorlevel 1 goto failed
exit /b 0
:failed
echo The dashboard stopped with an error. Review the message above.
pause
exit /b 1
'''

START = '''FISHERIES COLD CHAIN - WINDOWS PORTABLE PROJECT

1. Extract this entire folder to a normal local folder (not inside the ZIP).
2. Double-click RUN_PROJECT.cmd.
3. Wait for the data/model/simulation checks, then open http://localhost:8501
   if your browser does not open automatically.

Python 3.12, application dependencies, original local data, acquired raw data,
curated tables, source code, trained models, saved results and presentation
are included. No Python installation or data download is required.
This package targets 64-bit Windows. It is not a macOS/Linux runtime.

RUN_PROJECT.cmd rebuilds the data, fits the supported study models, regenerates
simulations and analyses, runs the test suite, then starts the dashboard.
Training code already exists in src/models; the runner executes that code.
Leave the terminal open while using the dashboard. Press Ctrl+C to stop.

For later use, OPEN_DASHBOARD.cmd opens the included saved results without
rebuilding. To rebuild without starting the dashboard, run in a command prompt:
    RUN_PROJECT.cmd --no-dashboard

Do not copy an old .venv into this folder. The launchers create a fresh local
environment against the bundled runtime, including after moving the folder.
Do not delete .runtime or data/raw. Windows may show .runtime as a hidden folder.

The presentation and COMPLETE_README.MD are included as saved deliverables.
The default runner rebuilds the application/research outputs; it does not rewrite
the README or regenerate the presentation. The presentation builder is included
under presentation; its PDF renderer needs Microsoft PowerPoint on Windows.

Scientific scope: simulated thermal exposure, with limited study-specific models.
Actual fresh-fish spoilage prediction remains blocked by missing paired data.
See COMPLETE_README.MD for the full technical account and source attribution.

Portable-package verification is in PORTABLE_BUILD_VERIFICATION.json and
PORTABLE_MANIFEST.json. The embedded Python retains its licenses.
'''

def ignore(directory, names):
    return [n for n in names if n in {'__pycache__', '.pytest_cache', '.git'} or n.endswith('.pyc')]

def stage():
    if sys.platform != 'win32' or sys.version_info[:2] != (3, 12):
        raise RuntimeError('Build with the working Windows Python 3.12 interpreter.')
    if BUNDLE.exists():
        raise FileExistsError(f'Build directory already exists: {BUNDLE}')
    BUNDLE.mkdir(parents=True)
    dirs = ['.streamlit', 'configs', 'data', 'Data_IIT2023150', 'docs', 'figures',
            'metadata', 'models', 'presentation', 'reports', 'results', 'scripts',
            'src', 'tests']
    for directory in dirs:
        shutil.copytree(ROOT / directory, BUNDLE / directory, ignore=ignore)
    files = ['.gitignore', 'app.py', 'combined_dataset.csv', 'COMPLETE_README.MD',
             'README.md', 'requirements.txt', 'run_project.py',
             'Fisheries_Cold_Chain_Project.pptx', 'Fisheries_Cold_Chain_Project.pdf']
    files += [p.name for p in ROOT.glob('*PROMPT.md')]
    for name in files:
        shutil.copy2(ROOT / name, BUNDLE / name)
    runtime_source = Path(sys.base_prefix)
    if not (runtime_source / 'python.exe').is_file():
        raise FileNotFoundError('The full base interpreter was not found.')
    shutil.copytree(runtime_source, RUNTIME, ignore=ignore)
    subprocess.run([sys.executable, '-m', 'pip', 'install', '--no-compile',
                    '--only-binary=:all:', '--target', str(RUNTIME / 'Lib/site-packages'),
                    '-r', str(ROOT / 'requirements.txt'), 'python-pptx==1.0.2'], check=True)
    (BUNDLE / 'RUN_PROJECT.cmd').write_text(LAUNCHER, encoding='ascii', newline='\r\n')
    (BUNDLE / 'OPEN_DASHBOARD.cmd').write_text(QUICK_LAUNCHER, encoding='ascii', newline='\r\n')
    (BUNDLE / 'START_HERE.txt').write_text(START, encoding='ascii')
    print(f'Staged portable project: {BUNDLE}', flush=True)

def pack():
    # A virtual environment created during validation is machine/path specific.
    # It is deliberately excluded; the launcher recreates it after extraction.
    files = sorted(p for p in BUNDLE.rglob('*') if p.is_file()
                   and '.venv' not in p.relative_to(BUNDLE).parts
                   and '__pycache__' not in p.parts and '.pytest_cache' not in p.parts
                   and not p.name.endswith('.pyc'))
    rows = [{'path': p.relative_to(BUNDLE).as_posix(), 'bytes': p.stat().st_size,
             'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in files]
    manifest = BUNDLE / 'PORTABLE_MANIFEST.json'
    manifest.write_text(json.dumps({'platform': 'Windows x64', 'python': '3.12',
                                   'files': rows}, indent=2), encoding='utf-8')
    files.append(manifest)
    archive = DIST / 'Fisheries_Cold_Chain_Windows.zip'
    with ZipFile(archive, 'w', ZIP_DEFLATED, compresslevel=6) as z:
        for p in files:
            z.write(p, (Path(BUNDLE.name) / p.relative_to(BUNDLE)).as_posix())
    with ZipFile(archive) as z:
        assert z.testzip() is None
    sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    (DIST / 'Fisheries_Cold_Chain_Windows.zip.sha256').write_text(sha+'  '+archive.name+'\n')
    print(json.dumps({'archive':str(archive),'files':len(files),
                      'size_mib':round(archive.stat().st_size/1024**2,2),'sha256':sha}),flush=True)

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('operation', choices=['stage','pack'])
    args=parser.parse_args()
    stage() if args.operation == 'stage' else pack()
