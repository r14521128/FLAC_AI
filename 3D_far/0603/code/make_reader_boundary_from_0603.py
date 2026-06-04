import csv
from pathlib import Path


BASE = Path(r"D:\FLAC_AI\3D_far\0603\far_out")
DISP_IN = BASE / "submodel_boundary_displacement.csv"
GRID_IN = BASE / "submodel_boundary_gridpoints.csv"
OUT = BASE / "submodel_boundary_displacement_v4_from_0603.csv"


def main():
    grid_by_gp = {}
    with GRID_IN.open("r", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            grid_by_gp[row["gp_id"]] = row

    max_step = -1
    rows_at_max = []
    with DISP_IN.open("r", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            step = int(row["step"])
            if step > max_step:
                max_step = step
                rows_at_max = [row]
            elif step == max_step:
                rows_at_max.append(row)

    header = [
        "step_pair",
        "phase",
        "cycle",
        "L_xmin",
        "L_xmax",
        "R_xmin",
        "R_xmax",
        "ratio_target",
        "ratio_local",
        "converged",
        "box_id",
        "monitor_x",
        "boundary",
        "target_coord",
        "actual_coord",
        "gp_id",
        "x",
        "y",
        "z",
        "ux",
        "uy",
        "uz",
    ]

    written = 0
    missing = 0
    with OUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for disp in rows_at_max:
            grid = grid_by_gp.get(disp["gp_id"])
            if grid is None:
                missing += 1
                continue
            writer.writerow(
                [
                    disp["step"],
                    disp["phase"],
                    disp["cycle"],
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    1,
                    grid["box_id"],
                    grid["monitor_x"],
                    grid["boundary"],
                    grid["target_coord"],
                    grid["actual_coord"],
                    disp["gp_id"],
                    grid["x"],
                    grid["y"],
                    grid["z"],
                    disp["ux"],
                    disp["uy"],
                    disp["uz"],
                ]
            )
            written += 1

    print(f"input max step: {max_step}")
    print(f"rows at max step: {len(rows_at_max)}")
    print(f"written: {written}")
    print(f"missing gp_id: {missing}")
    print(f"output: {OUT}")


if __name__ == "__main__":
    main()
