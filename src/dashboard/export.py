"""Downloads derived only from the currently executed API result."""
import io
import json
import zipfile
import pandas as pd

from .service import channel_summary, event_rows, stage_rows


def selected_files(result: dict, baseline: dict, channel: str, reference: float) -> dict[str, bytes]:
    summary = channel_summary(result, channel, reference)
    base = channel_summary(baseline, channel, reference)
    summary["baseline_run_id"] = base["run_id"]
    summary["baseline_degree_hours"] = base["degree_hours"]
    summary["delta_degree_hours"] = summary["degree_hours"] - base["degree_hours"]
    summary["relative_delta_fraction"] = summary["delta_degree_hours"] / base["degree_hours"] if base["degree_hours"] else None
    trace = [{**row, "selected_channel": channel, "selected_reference_c": reference} for row in result["trace"]]
    bundle = {"schema_version": 1, "selection": {"channel": channel, "reference_c": reference},
              "selected_result": result, "baseline_result": baseline, "selected_summary": summary}
    return {"trace.csv": pd.DataFrame(trace).to_csv(index=False).encode("utf-8-sig"),
            "stages.csv": pd.DataFrame(stage_rows(result, channel, reference)).to_csv(index=False).encode("utf-8-sig"),
            "events.csv": pd.DataFrame(event_rows(result)).to_csv(index=False).encode("utf-8-sig"),
            "summary.csv": pd.DataFrame([summary]).to_csv(index=False).encode("utf-8-sig"),
            "complete_result.json": json.dumps(bundle, indent=2, allow_nan=False).encode("utf-8")}


def zip_bytes(files: dict[str, bytes]) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, payload in files.items():
            archive.writestr(name, payload)
        archive.writestr("README.txt", "Simulated thermal exposure only. Fish spoilage is NOT_CALIBRATED.\n"
                         "Temperatures are Celsius; exposure is degree-hours above a selected comparison reference.\n"
                         "Scenario timestamps are arbitrary UTC epochs, not actual shipment times.\n")
    return stream.getvalue()
