"""Stage the public GitHub repository from this working project."""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'dist' / 'github_repo'

def ignore(directory, names):
    path = Path(directory)
    excluded = {'__pycache__', '.pytest_cache', '.venv', '.tools', '.git'}
    if path.name == 'redesign':
        excluded.add('selected_run.zip')
    if path.name == 'setup':
        excluded.add('last_run.json')
    if path.name == 'presentation':
        excluded.update({'preview', 'contact_sheet.png'})
    return [name for name in names if name in excluded or name.endswith('.pyc')]

def main():
    if DEST.exists():
        raise FileExistsError(f'Repository staging directory exists: {DEST}')
    DEST.mkdir(parents=True)
    directories = ['.github', '.streamlit', 'configs', 'Data_IIT2023150', 'docs',
                   'figures', 'metadata', 'models', 'presentation', 'reports',
                   'results', 'scripts', 'src', 'tests']
    for directory in directories:
        shutil.copytree(ROOT / directory, DEST / directory, ignore=ignore)
    files = ['app.py', 'combined_dataset.csv', 'COMPLETE_README.MD', 'README.md',
             'requirements.txt', 'run_project.py',
             'Fisheries_Cold_Chain_Project.pptx', 'Fisheries_Cold_Chain_Project.pdf']
    for file in files:
        shutil.copy2(ROOT / file, DEST / file)
    (DEST / '.gitignore').write_text('''# Generated runtime and caches
.venv/
.tools/
__pycache__/
.pytest_cache/
*.pyc
*.part
dist/

# Downloaded and regenerated data; the runner rebuilds these
data/raw/
data/interim/
data/curated/
data/processed/
data/external_validation/

# Local run records
reports/setup/last_run.json
presentation/preview/
presentation/contact_sheet.png
''', encoding='utf-8')
    files = [p for p in DEST.rglob('*') if p.is_file()]
    print(f'{DEST}: {len(files)} files, {sum(p.stat().st_size for p in files)/1024**2:.1f} MiB before Git compression')

if __name__ == '__main__':
    main()
