"""End-to-end CLI demo: builds a master signature for one gear from
known-good simulated units, then runs a healthy unit and a faulty unit through
the analysis pipeline, printing a PASS/FAIL report for each. Demonstrates the
full Phase 1 pipeline with no hardware and no web UI."""

from __future__ import annotations

import argparse
import json

import numpy as np

from analysis_engine.grading.parameters import default_full_scale_by_param
from analysis_engine.ordermatrix.gear_math import GearTeeth, compute_gear_orders
from analysis_engine.pipeline import analyze_dc_record, build_masters_from_trials, compute_trial_parameters
from nvh_simulator.faults import Fault
from nvh_simulator.generators import generate_dc_record

# MODEL-A gear geometry, taken from the reference system's Master Entry screen.
GEAR_R = compute_gear_orders("R", GearTeeth(drive_shaft=12, idler_shaft_1=36, layshaft=32), gear_ratio=3.753)

SAMPLE_RATE_HZ = 5000.0
RPM_START, RPM_END = 1000.0, 2500.0
DURATION_S = 4.0
FULL_SCALE_BY_PARAM = default_full_scale_by_param()


def _report_dict(label: str, result) -> dict:
    return {
        "unit": label,
        "gear": result.gear_label,
        "direction": result.direction,
        "result": "PASS" if result.passed else "FAIL",
        "fail_reason_codes": result.fail_reason_codes,
        "stats": {
            "mean": result.parameters["Mean Avg"],
            "rms": result.parameters["RMS Avg"],
            "crest": result.parameters["Crest Avg"],
            "kurtosis": result.parameters["Kurtosis Avg"],
        },
        "crash_noise_peak_band_rms": result.crash_noise.peak_band_rms,
        "slippage_dropout_fraction": result.slippage.dropout_fraction,
    }


def run_demo(n_trials: int = 30, seed: int = 0) -> list[dict]:
    rng = np.random.default_rng(seed)

    trial_parameters = []
    for _ in range(n_trials):
        sig = generate_dc_record(GEAR_R, RPM_START, RPM_END, DURATION_S, SAMPLE_RATE_HZ, rng=rng)
        trial_parameters.append(compute_trial_parameters(sig.channels["vib_a"], sig.time_s, sig.rpm, GEAR_R))
    masters = build_masters_from_trials(trial_parameters, FULL_SCALE_BY_PARAM)

    reports = []

    healthy = generate_dc_record(GEAR_R, RPM_START, RPM_END, DURATION_S, SAMPLE_RATE_HZ, rng=rng)
    healthy_result = analyze_dc_record(
        healthy.channels["vib_a"], healthy.time_s, healthy.rpm, SAMPLE_RATE_HZ, "R", "RU", GEAR_R, masters
    )
    reports.append(_report_dict("healthy-unit", healthy_result))

    crash_fault = Fault(kind="crash_noise", start_s=2.0, end_s=2.3, amplitude=8.0)
    faulty = generate_dc_record(
        GEAR_R, RPM_START, RPM_END, DURATION_S, SAMPLE_RATE_HZ, rng=rng, faults=[crash_fault]
    )
    faulty_result = analyze_dc_record(
        faulty.channels["vib_a"],
        faulty.time_s,
        faulty.rpm,
        SAMPLE_RATE_HZ,
        "R",
        "RU",
        GEAR_R,
        masters,
        crash_noise_band_hz=(500.0, 2000.0),
        crash_noise_threshold=0.5,
    )
    reports.append(_report_dict("crash-noise-unit", faulty_result))

    slip_fault = Fault(kind="slippage", start_s=1.0, end_s=3.0, drop_to=0.05)
    slipped = generate_dc_record(
        GEAR_R, RPM_START, RPM_END, DURATION_S, SAMPLE_RATE_HZ, rng=rng, noise_std=0.005, faults=[slip_fault]
    )
    slipped_result = analyze_dc_record(
        slipped.channels["vib_a"], slipped.time_s, slipped.rpm, SAMPLE_RATE_HZ, "R", "RU", GEAR_R, masters
    )
    reports.append(_report_dict("slippage-unit", slipped_result))

    return reports


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the NVH Phase 1 analysis pipeline demo")
    parser.add_argument("--trials", type=int, default=30, help="number of known-good trials for the master signature")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--out", type=str, default=None, help="optional path to write the report as JSON")
    args = parser.parse_args()

    reports = run_demo(n_trials=args.trials, seed=args.seed)

    for report in reports:
        print(f"[{report['unit']}] gear={report['gear']} dir={report['direction']} -> {report['result']}"
              + (f" ({', '.join(report['fail_reason_codes'])})" if report["fail_reason_codes"] else ""))

    if args.out:
        with open(args.out, "w") as f:
            json.dump(reports, f, indent=2)
        print(f"\nWrote report to {args.out}")


if __name__ == "__main__":
    main()
