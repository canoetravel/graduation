import argparse
import csv
import json
import time
import urllib.request
from pathlib import Path


def read_samples(path: Path):
    with path.open("r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        return list(reader)


def read_code(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def post_json(url: str, payload: dict):
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}
    )
    start = time.perf_counter()
    with urllib.request.urlopen(request) as response:
        response_text = response.read().decode("utf-8")
        status_code = response.getcode()
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    return status_code, json.loads(response_text), elapsed_ms


def run(base_url: str, samples_csv: Path, output_csv: Path):
    samples = read_samples(samples_csv)
    results = []
    judge_url = f"{base_url.rstrip('/')}/judge"

    for row in samples:
        source_path = Path(row["source_file"])
        code = read_code(source_path)
        payload = {
            "code": code,
            "timeout": 3,
            "assignment_type": row["assignment_type"],
        }

        try:
            http_status, data, elapsed_ms = post_json(judge_url, payload)
            result = {
                "sample_id": row["sample_id"],
                "category": row["category"],
                "assignment_type": row["assignment_type"],
                "expected_status": row["expected_status"],
                "http_status": http_status,
                "actual_status": data.get("status", ""),
                "score": data.get("score", 0),
                "latency_ms": round(elapsed_ms, 2),
                "ok": str(data.get("status", "") == row["expected_status"]),
                "notes": row.get("notes", ""),
            }
        except Exception as exc:
            result = {
                "sample_id": row["sample_id"],
                "category": row["category"],
                "assignment_type": row["assignment_type"],
                "expected_status": row["expected_status"],
                "http_status": "",
                "actual_status": "ERROR",
                "score": 0,
                "latency_ms": "",
                "ok": "False",
                "notes": f"request failed: {exc}",
            }
        results.append(result)

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as file:
        fields = [
            "sample_id",
            "category",
            "assignment_type",
            "expected_status",
            "http_status",
            "actual_status",
            "score",
            "latency_ms",
            "ok",
            "notes",
        ]
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(results)

    print(f"done: {output_csv}")


def main():
    parser = argparse.ArgumentParser(description="Run judge benchmark samples")
    parser.add_argument("--base-url", required=True, help="API base URL, e.g. http://localhost:8080/api")
    parser.add_argument("--samples", required=True, help="Path to sample_index.csv")
    parser.add_argument("--output", required=True, help="Output CSV path")
    args = parser.parse_args()

    run(args.base_url, Path(args.samples), Path(args.output))


if __name__ == "__main__":
    main()
