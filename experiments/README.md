# Experiments Guide

This folder is used for thesis experiment data collection.

## 1) Prepare sample set

Create your own code files and register them in `sample_index.csv`.

Columns:
- `sample_id`: unique id
- `category`: `normal` / `wrong` / `boundary` / `plagiarism`
- `assignment_type`: `process` / `file` / `memory`
- `source_file`: path to local code file
- `expected_status`: expected judge status, e.g. `AC`, `WA`, `CE`, `TLE`
- `notes`: optional comments

## 2) Start services

Run:

```bash
docker-compose up -d --build
```

## 3) Collect benchmark

Run:

```bash
python experiments/run_benchmark.py --base-url http://localhost:8080/api --samples experiments/sample_index.csv --output experiments/results_run1.csv
```

You can run multiple rounds (`results_run2.csv`, `results_run3.csv`) for average values.

## 4) Fill thesis metrics table

Use `metrics_template.csv` to summarize:
- average evaluation latency
- success rate
- plagiarism detection precision/recall (if labeled)
- estimated teacher time reduction

