import csv
from pathlib import Path

from tabulate import tabulate


def report_status(
    per_problem: bool, per_model: bool, per_instance: bool, statistics: Path, avg: str, tablefmt: str
>>>>>>> feature/add-support-for-time-stat-in-avg
):
    keys = ["configuration"]
    
    if per_model:
        keys.append("model")
    if per_problem:
        keys.append("problem")
    if per_model:
        keys.append("model")
    if per_instance:
        keys.append("instance")


    seen_status = set()
    table = {}
    with statistics.open() as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            key = [row["configuration"]]
            if per_model:
                key.append(row["model"])
            if per_problem:
                key.append(row["problem"])
            if per_instance:
                key.append(Path(row["data_file"]).name)

            seen_status.add(row["status"])
            key = tuple(key)

            avg_value = row.get(avg, 0)
            time = float(0 if avg_value == "" else avg_value)
            if key not in table:
                table[key] = {row["status"]: [time]}
            elif row["status"] not in table[tuple(key)]:
                table[key][row["status"]] = [time]
            else:
                table[key][row["status"]].append(time)

    seen_status = list(seen_status)
    seen_status.sort(reverse=True)

    return tabulate(
        [
            list(key)
            + [
                f"{len(row[s])} ({sum(row[s]) / len(row[s]) :.2f}s)"
                if avg is not None and s in row
                else str(len(row.get(s, [])))
                for s in seen_status
            ]
            for key, row in table.items()
        ],
        headers=(keys + seen_status),
        tablefmt=tablefmt,
    )
