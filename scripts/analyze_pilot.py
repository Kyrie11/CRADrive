#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from cradrive.metrics import _dynamic_actor, load_checkpoint_summary, read_jsonl, spearman, summarize_trace


def safe_float(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", required=True)
    p.add_argument("--runs", required=True, help="Output directory produced by run_grid.py")
    p.add_argument("--out", required=True)
    args = p.parse_args()

    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    runs_root = Path(args.runs)
    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)

    rows = []
    for cond in manifest["conditions"]:
        run_dir = runs_root / cond["condition_id"]
        trace = summarize_trace(read_jsonl(run_dir / "trace.jsonl"))
        ckpt = load_checkpoint_summary(run_dir / "checkpoint.json")
        row = dict(cond)
        row.pop("weather", None)
        row.update(trace)
        row.update(ckpt)
        rows.append(row)

    fields = []
    for r in rows:
        for k in r:
            if k not in fields and not isinstance(r[k], (dict, list)):
                fields.append(k)
    csv_path = out_root / "summary.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) for k in fields})

    report = []
    groups = defaultdict(list)
    for r in rows:
        groups[r.get("experiment")].append(r)

    report.append("# CRADrive pilot report\n")
    report.append("This is a diagnostic report, not yet a paper-level causal claim.\n")
    report.append("## Causal intervention groups\n")
    for name, group in groups.items():
        causal = [r for r in group if r.get("kind") == "causal" and safe_float(r.get("value")) is not None]
        causal.sort(key=lambda r: float(r["value"]))
        if not causal:
            continue
        report.append(f"### {name}\n")
        report.append("| reaction_time | min speed | max brake | min actor dist | score | collisions | status |\n")
        report.append("|---:|---:|---:|---:|---:|---:|---|\n")
        for r in causal:
            def fmt(v):
                return "NA" if v is None else (f"{float(v):.3f}" if isinstance(v, (float, int)) else str(v))
            report.append(
                f"| {r.get('value')} | {fmt(r.get('min_speed_near_hazard_mps'))} | {fmt(r.get('max_brake_near_hazard'))} | "
                f"{fmt(r.get('min_dynamic_actor_distance_m'))} | {fmt(r.get('driving_score'))} | "
                f"{fmt(r.get('collision_count'))} | {r.get('status', 'NA')} |\n"
            )

        xs = [float(r["value"]) for r in causal]
        # Larger reaction_time = more time available to react; urgency is the negative value.
        urgency = [-x for x in xs]
        for metric, expected in [
            ("max_brake_near_hazard", "higher urgency should generally not reduce braking response"),
            ("min_speed_near_hazard_mps", "higher urgency should generally not increase minimum speed"),
            ("speed_at_10m_mps", "higher urgency should generally not increase near-hazard speed"),
        ]:
            paired = [(u, safe_float(r.get(metric))) for u, r in zip(urgency, causal)]
            paired = [(u, y) for u, y in paired if y is not None]
            rho = spearman([x for x, _ in paired], [y for _, y in paired]) if len(paired) >= 3 else None
            report.append(f"- Spearman(urgency, {metric}) = {rho if rho is not None else 'NA'}; expectation: {expected}.\n")
        report.append("\n")

    report.append("## Negative-control weather checks\n")
    for name, group in groups.items():
        nuisance = [r for r in group if r.get("kind") == "nuisance_weather"]
        if nuisance:
            report.append(f"### {name}\n")
            for r in nuisance:
                report.append(
                    f"- {r.get('value')}: score={r.get('driving_score')}, min_speed={r.get('min_speed_near_hazard_mps')}, "
                    f"max_brake={r.get('max_brake_near_hazard')}, collisions={r.get('collision_count')}\n"
                )
            report.append("\n")

    report.append("## Go / no-go reading guide\n")
    report.append(
        "- **Strong go signal:** standard driving score changes little, but intervention response curves are flat, discontinuous, or non-monotonic; or nuisance weather causes a response comparable to the causal intervention.\n"
        "- **Moderate go signal:** hard conditions expose collisions/near misses and the trajectory/control response is delayed or inconsistent, even though ordinary conditions look strong.\n"
        "- **Weak signal:** response curves are smooth and semantically sensible, nuisance controls are stable, and the proposed CRA metrics add almost no information beyond the standard score. In that case do not over-invest in this exact framing.\n"
        "- Before a paper claim, repeat the same paired interventions on at least two additional policy families (e.g. LEAD/SimLingo) and add an explicit expert/safety-oracle response target.\n"
    )
    report_path = out_root / "report.md"
    report_path.write_text("".join(report), encoding="utf-8")

    # Optional plots. CSV/report are always produced even if matplotlib is unavailable.
    try:
        import matplotlib.pyplot as plt
        for name, group in groups.items():
            causal = [r for r in group if r.get("kind") == "causal" and safe_float(r.get("value")) is not None]
            causal.sort(key=lambda r: float(r["value"]))
            if not causal:
                continue
            x = [float(r["value"]) for r in causal]
            for metric in ["min_speed_near_hazard_mps", "max_brake_near_hazard", "driving_score", "min_dynamic_actor_distance_m"]:
                y = [safe_float(r.get(metric)) for r in causal]
                pairs = [(a, b) for a, b in zip(x, y) if b is not None]
                if len(pairs) < 2:
                    continue
                plt.figure(figsize=(6.4, 4.2))
                plt.plot([a for a, _ in pairs], [b for _, b in pairs], marker="o")
                plt.xlabel("reaction_time (s)")
                plt.ylabel(metric)
                plt.title(f"{name}: {metric}")
                plt.grid(True, alpha=0.25)
                plt.tight_layout()
                plt.savefig(out_root / f"{name}__{metric}.png", dpi=160)
                plt.close()

            # Most useful visual diagnostic: actual speed/brake response versus
            # distance to the target actor, one curve per intervention value.
            for response_metric in ["speed_mps", "brake"]:
                plt.figure(figsize=(7.2, 4.8))
                plotted = 0
                for r in causal:
                    trace_rows = read_jsonl(runs_root / r["condition_id"] / "trace.jsonl")
                    xs, ys = [], []
                    for tr in trace_rows:
                        actor = _dynamic_actor(tr)
                        if actor is None:
                            continue
                        d = safe_float(actor.get("distance_m"))
                        longitudinal = safe_float(actor.get("longitudinal_m"))
                        if d is None or d > 45.0 or (longitudinal is not None and longitudinal < -5.0):
                            continue
                        if response_metric == "speed_mps":
                            y = safe_float(tr.get("speed_mps"))
                        else:
                            y = safe_float((tr.get("control") or {}).get("brake"))
                        if y is not None:
                            xs.append(d); ys.append(y)
                    if len(xs) >= 2:
                        plt.plot(xs, ys, label=f"rt={r['value']}")
                        plotted += 1
                if plotted:
                    plt.xlabel("distance to target actor (m)")
                    plt.ylabel(response_metric)
                    plt.title(f"{name}: {response_metric} response")
                    plt.gca().invert_xaxis()
                    plt.grid(True, alpha=0.25)
                    plt.legend(fontsize=8, ncol=2)
                    plt.tight_layout()
                    plt.savefig(out_root / f"{name}__{response_metric}_vs_actor_distance.png", dpi=160)
                plt.close()
    except Exception as exc:
        (out_root / "plot_warning.txt").write_text(repr(exc) + "\n", encoding="utf-8")

    print(csv_path)
    print(report_path)


if __name__ == "__main__":
    main()
