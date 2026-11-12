# Academic Demand Forecasting & Faculty/Section Allocation

A reproducible synthetic-data pipeline for forecasting course demand, proposing sections, assigning eligible faculty, and surfacing unmet demand and labelled exception scenarios.

## Features
- Master and dependent entities with deterministic, zero-padded IDs.
- 3 historical registration-interest windows; target-term demand forecast is derived from historical confirmed interest only.
- Faculty skill, availability/leave, weekly workload, room capacity and section planning constraints.
- Explainable unmet-demand reasons.
- CSV + JSON exports, SQL schema, data dictionary, validation summary, source manifest and SHA-256 checksums.
- Separate `ground_truth.csv/json` and isolated `anomaly_fixtures.csv/json`; anomaly labels are never used as forecast/allocation inputs. Negative fixtures document all five required failure modes without corrupting baseline tables.
- Fixed-seed reproducibility and starter/full scale configuration.

## Requirements
Python 3.10+ recommended. VS Code with Python extension.

## Run in VS Code / terminal
```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# Windows cmd:
.venv\Scripts\activate.bat
# macOS/Linux:
source .venv/bin/activate

python -m pip install -r requirements.txt
python -m src.planner --config config.json --out data
pytest -q
```

The default config uses `starter` scale for a quick first run. For the required full volume, edit `config.json` and change `"scale": "starter"` to `"scale": "full"`, then rerun the command. Full scale creates 100 programs, 1,000 courses, 500 faculty and 20,000 student plans. The same seed and generator logic are used at both scales.

## Output files
`data/` contains one CSV and JSON per entity/table, including `demand_forecast`, `unmet_demand`, and `ground_truth`, plus:
- `validation_summary.json`
- `source_manifest.json`
- `checksums.json`

## Reproducibility check
Run twice into separate directories:
```bash
python -m src.planner --config config.json --out data_run1
python -m src.planner --config config.json --out data_run2
```
Compare CSV checksums:
```bash
python -c "import json; a=json.load(open('data_run1/checksums.json')); b=json.load(open('data_run2/checksums.json')); print('REPRODUCIBLE:', a==b)"
```
The output includes no real student or employee personal information. All records are synthetic.

## Important design note
The five required anomaly types are represented in `ground_truth` as explicit, separately stored test labels. The valid baseline allocation tables are not silently corrupted. A production extension can add a dedicated `anomaly_fixtures` dataset to materialize invalid assignment rows for negative testing without contaminating baseline facts.

## GitHub submission checklist
1. Create a **public** GitHub repository.
2. Extract this project and open the folder in VS Code.
3. Run the commands above; inspect `validation_summary.json`.
4. Commit source, tests, schema, docs and optionally the generated starter data.
5. Push to GitHub and paste the repository URL into the submission form.

Do not commit `.venv/`, caches, or large generated full-scale exports unless the submission asks for them.
