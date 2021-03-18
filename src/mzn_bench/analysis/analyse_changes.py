#!/usr/bin/env python3
import csv
import math
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PerformanceChanges:
    time_delta: float
    obj_delta: float
    # (from_status, to_status) -> (model, datafile)
    status_changes: dict[tuple[str, str], list[tuple[str, str]]] = field(
        default_factory=lambda: defaultdict(list)
    )
    # model, datafile, from_time, to_time
    time_changes: list[tuple[str, str, float, float]] = field(default_factory=list)
    # model, datafile, from_obj, to_obj, maximise?
    obj_changes: list[tuple[str, str, float, float, bool]] = field(default_factory=list)
    # model, datafile
    missing_instances: list[tuple[str, str]] = field(default_factory=list)

    def __str__(self):
        n_status_changes = sum([len(li) for key, li in self.status_changes.items()])
        n_pos_status_changes = 0
        n_bad_status_changes = 0

        pos_status_changes = [
            ("ERROR", "SATISFIED"),
            ("ERROR", "UNSATISFIABLE"),
            ("ERROR", "OPTIMAL_SOLUTION"),
            ("ERROR", "UNKNOWN"),
            ("UNKNOWN", "SATISFIED"),
            ("UNKNOWN", "UNSATISFIABLE"),
            ("UNKNOWN", "OPTIMAL_SOLUTION"),
            ("SATISFIED", "OPTIMAL_SOLUTION"),
        ]

        conflicting_status_changes = [
            ("UNSATISFIABLE", "SATISFIED"),
            ("SATISFIED", "UNSATISFIABLE"),
            ("UNSATISFIABLE", "OPTIMAL_SOLUTION"),
            ("OPTIMAL_SOLUTION", "UNSATISFIABLE"),
        ]

        stat_bad_str = ""
        stat_pos_str = ""
        stat_neg_str = ""

        for change, li in self.status_changes.items():
            s = f"{change[0]} -> {change[1]}:\n"
            for i in li:
                s += f"  - {i[0]} {i[1]}\n"
            if change in conflicting_status_changes:
                n_bad_status_changes += len(li)
                stat_bad_str += s
            elif change in pos_status_changes:
                n_pos_status_changes += len(li)
                stat_pos_str += s
            else:
                stat_neg_str += s

        if stat_bad_str != "":
            stat_bad_str = (
                "Conflicting Status Changes:\n---------------------------\n"
                + stat_bad_str
            )
        if stat_pos_str != "":
            stat_pos_str = (
                "Positive Status Changes:\n------------------------\n" + stat_pos_str
            )
        if stat_neg_str != "":
            stat_neg_str = (
                "Negative Status Changes:\n------------------------\n" + stat_neg_str
            )

        output = (
            f"Summary:\n"
            f"========\n"
            f"- Status Changes: {n_status_changes} ({'conflicts: ' + str(n_bad_status_changes) + ', ' if n_bad_status_changes > 0 else ''}positive: {n_pos_status_changes})\n"
            f"- Runtime Changes: {len(self.time_changes)} (positive: {len([x for x in self.time_changes if (x[3] - x[2]) / x[2] < 0])})\n"
            f"- Objective Changes: {len(self.obj_changes)} (posxive: {len([x for x in self.obj_changes if (1 if x[4] else -1) * (x[3] - x[2]) / x[2] > 0])})\n"
        )
        if len(self.missing_instances) > 0:
            f"- Missing instances: {len(self.missing_instances)}\n"
        output += "\n\n"

        output += (
            f"Status Changes:\n===============\n{stat_bad_str}\n{stat_neg_str}\n{stat_pos_str}\n"
            if n_status_changes > 0
            else ""
        )

        if len(self.time_changes) > 0:
            output += f"Timing Changes (>±{self.time_delta * 100:.1f}%):\n=========================\n"
            time_li = sorted(
                self.time_changes, key=lambda it: (it[3] - it[2]) / it[2], reverse=True
            )
            for it in time_li:
                output += f"- ({(it[3] - it[2]) / it[2] * 100:.1f}%: {it[2]:.1f}s -> {it[3]:.1f}s) {it[0]} {it[1]}\n"
            output += "\n"

        if len(self.obj_changes) > 0:
            output += f"Objective Changes (>±{self.obj_delta * 100:.1f}%):\n=========================\n"
            obj_li = sorted(
                self.obj_changes,
                key=lambda it: (1 if it[4] else -1) * (it[3] - it[2]) / it[2],
            )
            for it in obj_li:
                output += f"- ({(it[3] - it[2]) / it[2] * 100:.1f}%: {'MAX' if it[4] else 'MIN'} {it[2]:.2f} -> {it[3]:.2f}) {it[0]} {it[1]}\n"

        if len(self.missing_instances) > 0:
            output += "Missing Instances:\n==================\n"
            for it in self.missing_instances:
                output += f"- {it[0]} {it[1]}"

        return output


def compare_configurations(
    statistics: Path, from_conf: str, to_conf: str, time_delta: float, obj_delta: float
) -> PerformanceChanges:
    from_stats = {}
    to_stats = {}

    with statistics.open() as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            if row["configuration"] == from_conf:
                from_stats[(row["model"], row["data_file"])] = (
                    row["status"],
                    float(0 if row["time"] == "" else row["time"]),
                    float(math.nan if row["objective"] == "" else row["objective"]),
                    row["method"],
                )
            elif row["configuration"] == to_conf:
                to_stats[(row["model"], row["data_file"])] = (
                    row["status"],
                    float(0 if row["time"] == "" else row["time"]),
                    float(math.nan if row["objective"] == "" else row["objective"]),
                )

    changes = PerformanceChanges(time_delta, obj_delta)

    for key, from_val in from_stats.items():
        to_val = to_stats.get(key, None)
        if to_val is None:
            changes.missing_instances.append(key)
        elif from_val[0] != to_val[0]:
            changes.status_changes[(from_val[0], to_val[0])].append(key)
        elif from_val[0] == "OPTIMAL_SOLUTION" or (
            from_val[0] == "SATISFIED" and from_val[3] == "satisfy"
        ):
            time_change = (to_val[1] - from_val[1]) / from_val[1]
            if abs(time_change) > time_delta:
                changes.time_changes.append((key[0], key[1], from_val[1], to_val[1]))
        elif from_val[0] == "SATISFIED" and from_val[3] != "satisfy":
            obj_change = (to_val[2] - from_val[2]) / from_val[2]
            if abs(obj_change) > obj_delta:
                changes.obj_changes.append(
                    (key[0], key[1], from_val[2], to_val[2], from_val[3] == "maximize")
                )

    return changes