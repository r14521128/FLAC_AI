# -*- coding: utf-8 -*-
# ============================================================
# 06_unsupported_submodel_boundary_monitor.py
# 大模型：無支撐開挖 + 小模型六面邊界位移輸出 + 收斂後塑性厚度
#
# 輸出：
#   1) no_shotcrete_cycle_displacement_v4.csv
#      監測斷面 crown / wall_L / wall_R 位移。
#      只有收斂列會輸出最大塑性厚度；cycle 過程列不計算塑性厚度。
#
#   2) submodel_boundary_displacement_v4.csv
#      2608 / 2896 兩個小模型 box 的六面邊界 gridpoint 位移。
#      此檔案維持原本欄位，方便接續小模型邊界使用。
#
#   3) submodel_boundary_gridpoints_v4.csv
#      小模型六面邊界 gridpoint 清單。
#
# Run in FLAC3D IPython Console:
#   exec(open("D:/FLAC_AI/3D_far/0601/06_unsupported_submodel_boundary_monitor.py").read())
# ============================================================

import itasca as it
import os
import csv
from collections import defaultdict

it.command("python-reset-state false")

# ============================================================
# 路徑設定
# ============================================================
base_dir = r"D:\FLAC_AI\3D_far\0530"
output_dir = os.path.join(base_dir, "out")
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

far_output_dir = os.path.join(base_dir, "far_out")
if not os.path.exists(far_output_dir):
    os.makedirs(far_output_dir)

initial_state_name = os.path.join(base_dir, "initial_state_0530").replace("\\", "/")

# ============================================================
# 監測斷面 x 座標
# ============================================================
MONITOR_X = [2608, 2896]

FINE_HALF   = 36
FINE_STEP   = 1
COARSE_STEP = 5

def is_fine(x):
    # 判斷單一 slice 是否落在監測斷面附近。
    return any(abs(x - mx) <= FINE_HALF for mx in MONITOR_X)

# ============================================================
# 小模型 box 定義
# ============================================================
SUBMODEL_BOXES = [
    {
        "box_id": "sub_2608",
        "monitor_x": 2608.0,
        "xmin": 2558.0,
        "xmax": 2658.0,
        "ymin": 4775.0,
        "ymax": 4825.0,
        "zmin": 192.0,
        "zmax": 242.0,
    },
    {
        "box_id": "sub_2896",
        "monitor_x": 2896.0,
        "xmin": 2846.0,
        "xmax": 2946.0,
        "ymin": 4775.0,
        "ymax": 4825.0,
        "zmin": 192.0,
        "zmax": 242.0,
    },
]

# 若設定的 box 邊界座標沒有剛好落在 gridpoint 層上，
# 會在 FACE_SEARCH_PAD 範圍內找最近的實際 gridpoint 層。
FACE_SEARCH_PAD = 2.0
INPLANE_PAD = 0.001
LAYER_TOL = 0.001

# ============================================================
# 開挖停止線
# ============================================================
R_STOP_X = 2780.0
L_STOP_X = 2780.0

# ============================================================
# 分區收斂與記錄參數
# ============================================================
RATIO_FINE   = 1e-5
RATIO_COARSE = 1e-4
SOLVE_CHUNK  = 500
SOLVE_CAP    = 20000

FINE_CYCLE_RECORDS = [50, 100, 300, 500, 1000]

# FLAC3D console smoke test 用。
# 一般正式運算時不要設定這些環境變數。
SMOKE_MAX_STEP_PAIR = int(os.environ.get("FLAC_SMOKE_MAX_STEP_PAIR", "0"))
if SMOKE_MAX_STEP_PAIR > 0:
    SOLVE_CAP = int(os.environ.get("FLAC_SMOKE_SOLVE_CAP", "500"))
    FINE_CYCLE_RECORDS = [50]
    print("[SMOKE] max_step_pair={0}, solve_cap={1}".format(
        SMOKE_MAX_STEP_PAIR, SOLVE_CAP))

# ============================================================
# 讀取 initial_state
# ============================================================
it.command("model restore '{0}'".format(initial_state_name))
it.command("zone gridpoint initialize displacement (0,0,0)")
it.command("zone gridpoint initialize velocity    (0,0,0)")

# ============================================================
# 建立 tunnel slice
# ============================================================
slice_dict = defaultdict(list)
for z in it.zone.list():
    if z.group("default") == "tunnel":
        xc = round(z.pos()[0], 4)
        slice_dict[xc].append(z)

x_slices = sorted(slice_dict.keys())
N = len(x_slices)
print("tunnel slices: {0}  x={1:.1f}~{2:.1f}".format(N, x_slices[0], x_slices[-1]))

# 用半個 slice 間距作為塑性厚度查詢的 x 方向容許範圍。
dx_list = [abs(x_slices[i + 1] - x_slices[i]) for i in range(len(x_slices) - 1)]
X_MARGIN = 0.51 * min(dx_list) if dx_list else 0.5
print("plastic thickness X_MARGIN = {0:.3f}".format(X_MARGIN))

# ============================================================
# 建立左右開挖群組
# ============================================================
def build_groups_left(x_list, stop_x):
    groups = []
    i = 0
    while i < len(x_list):
        step = FINE_STEP if is_fine(x_list[i]) else COARSE_STEP
        grp = x_list[i:i + step]
        groups.append(grp)
        if max(grp) >= stop_x:
            break
        i += step
    return groups

def build_groups_right(x_list, stop_x):
    groups = []
    i = len(x_list) - 1
    while i >= 0:
        step = FINE_STEP if is_fine(x_list[i]) else COARSE_STEP
        start = max(0, i - step + 1)
        grp = list(reversed(x_list[start:i + 1]))
        groups.append(grp)
        if min(grp) <= stop_x:
            break
        i -= step
    return groups

left_groups  = build_groups_left(x_slices, L_STOP_X)
right_groups = build_groups_right(x_slices, R_STOP_X)
print("L groups: {0} (stop x~{1})  R groups: {2} (stop x~{3})".format(
    len(left_groups), L_STOP_X, len(right_groups), R_STOP_X))

def group_is_fine(group):
    if not group:
        return False
    return is_fine(group[0])

# ============================================================
# 建立岩體監測 gridpoint
# ============================================================
mon_gps = {}

MON_TARGETS = {
    "crown":  (4800.0, 220.0),
    "wall_L": (4797.0, 217.0),
    "wall_R": (4803.0, 217.0),
}

for mx in MONITOR_X:
    crown  = it.gridpoint.near((float(mx), MON_TARGETS["crown"][0],  MON_TARGETS["crown"][1]))
    wall_L = it.gridpoint.near((float(mx), MON_TARGETS["wall_L"][0], MON_TARGETS["wall_L"][1]))
    wall_R = it.gridpoint.near((float(mx), MON_TARGETS["wall_R"][0], MON_TARGETS["wall_R"][1]))
    mon_gps[mx] = {"crown": crown, "wall_L": wall_L, "wall_R": wall_R}

    pc = crown.pos()
    pL = wall_L.pos()
    pR = wall_R.pos()
    print("rock gp x={0}".format(mx))
    print("  crown  id={0} pos=({1:.2f},{2:.2f},{3:.2f})".format(
        crown.id(), pc[0], pc[1], pc[2]))
    print("  wall_L id={0} pos=({1:.2f},{2:.2f},{3:.2f})".format(
        wall_L.id(), pL[0], pL[1], pL[2]))
    print("  wall_R id={0} pos=({1:.2f},{2:.2f},{3:.2f})".format(
        wall_R.id(), pR[0], pR[1], pR[2]))

def get_rock_disp(mx):
    n = mon_gps[mx]
    dz  = n["crown"].disp()[2]
    dyL = n["wall_L"].disp()[1]
    dyR = n["wall_R"].disp()[1]
    return dz, dyL, dyR

# ============================================================
# 建立小模型 box 六面邊界 gridpoint 清單
# ============================================================
def in_range(value, vmin, vmax, pad):
    return value >= vmin - pad and value <= vmax + pad

def point_in_box_plane(p, box, axis, pad):
    if axis != 0 and not in_range(p[0], box["xmin"], box["xmax"], pad):
        return False
    if axis != 1 and not in_range(p[1], box["ymin"], box["ymax"], pad):
        return False
    if axis != 2 and not in_range(p[2], box["zmin"], box["zmax"], pad):
        return False
    return True

def build_one_face(all_gps, box, boundary, axis, target_coord):
    candidates = []

    for gp in all_gps:
        p = gp.pos()
        if not point_in_box_plane(p, box, axis, INPLANE_PAD):
            continue
        if abs(p[axis] - target_coord) <= FACE_SEARCH_PAD:
            candidates.append(gp)

    # 如果 2 m 內找不到 gridpoint 層，退回同一 box 投影範圍內最接近的層。
    if not candidates:
        for gp in all_gps:
            p = gp.pos()
            if point_in_box_plane(p, box, axis, INPLANE_PAD):
                candidates.append(gp)

    if not candidates:
        print("[WARN] no candidate gp for {0} {1}".format(box["box_id"], boundary))
        return {
            "boundary": boundary,
            "axis": axis,
            "target_coord": target_coord,
            "actual_coord": None,
            "gps": [],
        }

    nearest = min(candidates, key=lambda gp: abs(gp.pos()[axis] - target_coord))
    actual_coord = nearest.pos()[axis]

    selected = []
    for gp in candidates:
        p = gp.pos()
        if abs(p[axis] - actual_coord) <= LAYER_TOL:
            selected.append(gp)

    selected.sort(key=lambda gp: (gp.pos()[0], gp.pos()[1], gp.pos()[2], gp.id()))

    if abs(actual_coord - target_coord) > FACE_SEARCH_PAD:
        print("[WARN] {0} {1}: target={2:.3f}, nearest layer={3:.3f}".format(
            box["box_id"], boundary, target_coord, actual_coord))

    print("boundary gp: {0} {1} target={2:.3f} actual={3:.3f} count={4}".format(
        box["box_id"], boundary, target_coord, actual_coord, len(selected)))

    return {
        "boundary": boundary,
        "axis": axis,
        "target_coord": target_coord,
        "actual_coord": actual_coord,
        "gps": selected,
    }

def build_submodel_boundary_gps():
    all_gps = list(it.gridpoint.list())
    data = {}

    for box in SUBMODEL_BOXES:
        box_id = box["box_id"]
        data[box_id] = {
            "box": box,
            "faces": [],
        }

        face_defs = [
            ("xmin", 0, box["xmin"]),
            ("xmax", 0, box["xmax"]),
            ("ymin", 1, box["ymin"]),
            ("ymax", 1, box["ymax"]),
            ("zmin", 2, box["zmin"]),
            ("zmax", 2, box["zmax"]),
        ]

        for boundary, axis, target_coord in face_defs:
            face = build_one_face(all_gps, box, boundary, axis, target_coord)
            data[box_id]["faces"].append(face)

    return data

submodel_boundary_gps = build_submodel_boundary_gps()

# ============================================================
# 建立 FISH 讀取 ratio_local
# ============================================================
# 用途：
#   FLAC3D 的 zone.mech.ratio.local 是 FISH 內的全域局部力比。
#   這個腳本需要在 Python 迴圈中讀取它，判斷是否已收斂。
#   做法是找一個穩定存在的參考 zone，把 ratio_local 暫存到 zone.extra(10)，
#   Python 再用 ref_zone.extra(10) 讀回來。
#   這個 ref_zone 不代表該位置的力比，只是 Python 與 FISH 之間的暫存容器。
# ============================================================
ref_zone = it.zone.near((2400.5, 4700.5, 170.5))
ref_id = ref_zone.id()
print("ref zone for ratio and extras: id={0}".format(ref_id))

it.command("""
fish define write_ratio_info
    local rz = zone.find({0})
    zone.extra(rz, 10) = zone.mech.ratio.local
end
""".format(ref_id))

def get_ratio():
    it.command("@write_ratio_info")
    return ref_zone.extra(10)

# ============================================================
# FISH：計算收斂後最大塑性厚度
# ============================================================
it.command("""
fish define calc_plastic_thickness
    local rz = zone.find({0})
    local xmin = zone.extra(rz, 21)
    local xmax = zone.extra(rz, 22)
    local xmargin = zone.extra(rz, 23)

    if xmax < xmin
        zone.extra(rz, 11) = -1.0
        zone.extra(rz, 12) = 0
        zone.extra(rz, 13) = 0
        exit
    endif

    local qmin = xmin - xmargin
    local qmax = xmax + xmargin
    local marker = zone.extra(rz, 24) + 1
    zone.extra(rz, 24) = marker

    local plastic_bits = 1023

    loop foreach local z zone.list
        local xz = zone.pos.x(z)
        if xz >= qmin
            if xz <= qmax
                local igp
                loop igp (1,8)
                    local g = zone.gp(z, igp)

                    if zone.model(z) = 'null'
                        if zone.group(z,'default') = 'excavation'
                            gp.extra(g,21) = marker
                        endif
                    else
                        if zone.group(z,'default') # 'tunnel'
                            if zone.group(z,'default') # 'excavation'
                                gp.extra(g,22) = marker
                            endif
                        endif
                    endif
                end_loop
            endif
        endif
    endloop

    local n_contour = 0
    loop foreach local g gp.list
        if gp.extra(g,21) = marker
            if gp.extra(g,22) = marker
                n_contour = n_contour + 1
            endif
        endif
    endloop

    local max_thick = 0.0
    local n_plastic = 0

    loop foreach local z zone.list
        local xz = zone.pos.x(z)
        if xz >= qmin
            if xz <= qmax
                if zone.model(z) # 'null'
                    if zone.group(z,'default') # 'tunnel'
                        if zone.group(z,'default') # 'excavation'
                            local st = zone.state(z,1)
                            if math.and(st, plastic_bits) # 0
                                n_plastic = n_plastic + 1
                                local min_dist = 1.0e30

                                loop foreach local g gp.list
                                    if gp.extra(g,21) = marker
                                        if gp.extra(g,22) = marker
                                            local dy = zone.pos.y(z) - gp.pos.y(g)
                                            local dz = zone.pos.z(z) - gp.pos.z(g)
                                            local d = math.sqrt(dy*dy + dz*dz)

                                            if d < min_dist
                                                min_dist = d
                                            endif
                                        endif
                                    endif
                                endloop

                                if min_dist < 1.0e20
                                    if min_dist > max_thick
                                        max_thick = min_dist
                                    endif
                                endif
                            endif
                        endif
                    endif
                endif
            endif
        endif
    endloop

    if n_contour = 0
        zone.extra(rz, 11) = -1.0
    else
        zone.extra(rz, 11) = max_thick
    endif

    zone.extra(rz, 12) = n_plastic
    zone.extra(rz, 13) = n_contour
end
""".format(ref_id))

def get_plastic_thickness(x_group):
    # 回傳：
    #   max_thickness_m：該側開挖範圍收斂後最大塑性厚度
    #   n_plastic：參與計算的塑性 rock zone 數量
    #   n_contour：辨識出的開挖輪廓 gridpoint 數量
    if not x_group:
        return -1.0, 0, 0

    xmin = min(x_group)
    xmax = max(x_group)

    it.command("""
fish define set_plastic_query
    local rz = zone.find({0})
    zone.extra(rz, 21) = {1}
    zone.extra(rz, 22) = {2}
    zone.extra(rz, 23) = {3}
end
@set_plastic_query
@calc_plastic_thickness
""".format(ref_id, xmin, xmax, X_MARGIN))

    return ref_zone.extra(11), int(ref_zone.extra(12)), int(ref_zone.extra(13))

# ============================================================
# 分段收斂
# ============================================================
def solve_to_ratio(target):
    total = 0
    if get_ratio() <= target:
        return 0, True

    while total < SOLVE_CAP:
        it.command("model cycle {0}".format(SOLVE_CHUNK))
        total += SOLVE_CHUNK
        if get_ratio() <= target:
            return total, True

    return total, False

def convergence_status(ok, ratio_local):
    if ok:
        return 1
    return "cap_ratio={0:.6e}".format(ratio_local)

# ============================================================
# 建立 FLAC3D 原生 history
# ============================================================
it.command("history interval 50")
it.command("model history mechanical ratio-local")
it.command("model history mechanical unbalanced-maximum")

for mx in MONITOR_X:
    pc = mon_gps[mx]["crown"].pos()
    pL = mon_gps[mx]["wall_L"].pos()
    pR = mon_gps[mx]["wall_R"].pos()
    it.command("zone history displacement-z position ({0} {1} {2})".format(pc[0], pc[1], pc[2]))
    it.command("zone history displacement-y position ({0} {1} {2})".format(pL[0], pL[1], pL[2]))
    it.command("zone history displacement-y position ({0} {1} {2})".format(pR[0], pR[1], pR[2]))

print("rock history created: {0} items".format(2 + len(MONITOR_X) * 3))

# ============================================================
# CSV 輸出
# ============================================================
monitor_csv_path = os.path.join(output_dir, "no_shotcrete_cycle_displacement_v4.csv")
boundary_csv_path = os.path.join(far_output_dir, "submodel_boundary_displacement_v4.csv")
boundary_gp_list_path = os.path.join(far_output_dir, "submodel_boundary_gridpoints_v4.csv")

# converged：
#   1 = 達到目標力比
#   cap_ratio=<ratio_local> = 撞到 SOLVE_CAP 時的實際 ratio_local
#   空白 = cycle 過程點
monitor_header = [
    "step_pair", "phase", "cycle",
    "L_xmin", "L_xmax", "R_xmin", "R_xmax",
    "ratio_target", "ratio_local", "converged",
    "L_plastic_thick_max_m", "L_plastic_nzone", "L_contour_ngp",
    "R_plastic_thick_max_m", "R_plastic_nzone", "R_contour_ngp"
]

for mx in MONITOR_X:
    monitor_header += [
        "rock_crown_{0}_z".format(mx),
        "rock_wallL_{0}_y".format(mx),
        "rock_wallR_{0}_y".format(mx),
    ]

boundary_header = [
    "step_pair", "phase", "cycle",
    "L_xmin", "L_xmax", "R_xmin", "R_xmax",
    "ratio_target", "ratio_local", "converged",
    "box_id", "monitor_x", "boundary",
    "target_coord", "actual_coord",
    "gp_id", "x", "y", "z",
    "ux", "uy", "uz"
]

with open(monitor_csv_path, "wb") as f:
    csv.writer(f).writerow(monitor_header)

with open(boundary_csv_path, "wb") as f:
    csv.writer(f).writerow(boundary_header)

boundary_gp_header = [
    "box_id", "monitor_x", "boundary",
    "target_coord", "actual_coord",
    "gp_id", "x", "y", "z"
]

with open(boundary_gp_list_path, "wb") as f:
    writer = csv.writer(f)
    writer.writerow(boundary_gp_header)
    for box_id in sorted(submodel_boundary_gps.keys()):
        item = submodel_boundary_gps[box_id]
        box = item["box"]
        for face in item["faces"]:
            for gp in face["gps"]:
                p = gp.pos()
                writer.writerow([
                    box_id, box["monitor_x"], face["boundary"],
                    face["target_coord"], face["actual_coord"],
                    gp.id(), p[0], p[1], p[2]
                ])

def group_range(group):
    if not group:
        return -1, -1
    return min(group), max(group)

def write_monitor_row(step_pair, phase, cyc, L_group, R_group,
                      ratio_target, ratio_local, converged,
                      calc_plastic=False):
    L_xmin, L_xmax = group_range(L_group)
    R_xmin, R_xmax = group_range(R_group)

    if calc_plastic:
        L_thick, L_nplastic, L_ncontour = get_plastic_thickness(L_group)
        R_thick, R_nplastic, R_ncontour = get_plastic_thickness(R_group)
    else:
        L_thick, L_nplastic, L_ncontour = "", "", ""
        R_thick, R_nplastic, R_ncontour = "", "", ""

    row = [
        step_pair, phase, cyc,
        L_xmin, L_xmax, R_xmin, R_xmax,
        ratio_target, ratio_local, converged,
        L_thick, L_nplastic, L_ncontour,
        R_thick, R_nplastic, R_ncontour
    ]

    for mx in MONITOR_X:
        dz, dyL, dyR = get_rock_disp(mx)
        row += [dz, dyL, dyR]

    with open(monitor_csv_path, "ab") as f:
        csv.writer(f).writerow(row)

def write_boundary_rows(step_pair, phase, cyc, L_group, R_group,
                        ratio_target, ratio_local, converged):
    L_xmin, L_xmax = group_range(L_group)
    R_xmin, R_xmax = group_range(R_group)

    with open(boundary_csv_path, "ab") as f:
        writer = csv.writer(f)

        for box_id in sorted(submodel_boundary_gps.keys()):
            item = submodel_boundary_gps[box_id]
            box = item["box"]

            for face in item["faces"]:
                boundary = face["boundary"]
                target_coord = face["target_coord"]
                actual_coord = face["actual_coord"]

                for gp in face["gps"]:
                    p = gp.pos()
                    d = gp.disp()
                    writer.writerow([
                        step_pair, phase, cyc,
                        L_xmin, L_xmax, R_xmin, R_xmax,
                        ratio_target, ratio_local, converged,
                        box_id, box["monitor_x"], boundary,
                        target_coord, actual_coord,
                        gp.id(), p[0], p[1], p[2],
                        d[0], d[1], d[2]
                    ])

def write_all_rows(step_pair, phase, cyc, L_group, R_group,
                   ratio_target, converged, calc_plastic=False):
    ratio_local = get_ratio()
    write_monitor_row(step_pair, phase, cyc, L_group, R_group,
                      ratio_target, ratio_local, converged,
                      calc_plastic=calc_plastic)
    write_boundary_rows(step_pair, phase, cyc, L_group, R_group,
                        ratio_target, ratio_local, converged)
    return ratio_local

# ============================================================
# 只開挖，不建立噴凝土
# ============================================================
def excavate_only(x_group):
    for xc in x_group:
        for z in slice_dict[xc]:
            z.set_group("excavation", "default")
    it.command("zone cmodel assign null range group 'excavation'")

# ============================================================
# 主迴圈：左右交替開挖
# ============================================================
L_idx  = 0
R_idx  = 0
L_done = False
R_done = False
step_pair = 0

while (L_idx < len(left_groups) and not L_done) or \
      (R_idx < len(right_groups) and not R_done):

    step_pair += 1
    L_group = None
    R_group = None

    if not L_done and L_idx < len(left_groups):
        L_group = left_groups[L_idx]
        L_idx += 1
        excavate_only(L_group)
        if max(L_group) >= L_STOP_X:
            L_done = True
            print("  Left stopped at x~{0:.1f}".format(max(L_group)))

    if not R_done and R_idx < len(right_groups):
        R_group = right_groups[R_idx]
        R_idx += 1
        excavate_only(R_group)
        if min(R_group) <= R_STOP_X:
            R_done = True
            print("  Right stopped at x~{0:.1f}".format(min(R_group)))

    step_fine = group_is_fine(L_group) or group_is_fine(R_group)

    if step_fine:
        last_cycle = 0
        for c in FINE_CYCLE_RECORDS:
            inc = c - last_cycle
            if inc > 0:
                it.command("model cycle {0}".format(inc))
            write_all_rows(step_pair, "cycle", c,
                           L_group, R_group, RATIO_FINE, "",
                           calc_plastic=False)
            last_cycle = c

        used, ok = solve_to_ratio(RATIO_FINE)
        ratio_now = get_ratio()
        conv_status = convergence_status(ok, ratio_now)

        write_all_rows(step_pair, "conv_1e-5", last_cycle + used,
                       L_group, R_group, RATIO_FINE, conv_status,
                       calc_plastic=True)

        if not ok:
            print("  [WARN] step_pair={0} fine NOT converged to 1e-5 "
                  "(cap {1}, ratio={2:.6e})".format(
                      step_pair, SOLVE_CAP, ratio_now))
    else:
        used, ok = solve_to_ratio(RATIO_COARSE)
        ratio_now = get_ratio()
        conv_status = convergence_status(ok, ratio_now)

        write_all_rows(step_pair, "conv_1e-4", used,
                       L_group, R_group, RATIO_COARSE, conv_status,
                       calc_plastic=True)

        if not ok:
            print("  [WARN] step_pair={0} coarse NOT converged to 1e-4 "
                  "(cap {1}, ratio={2:.6e})".format(
                      step_pair, SOLVE_CAP, ratio_now))

    if step_pair % 10 == 0:
        it.command("model save '{0}/no_shotcrete_v4_chk_{1:04d}'".format(
            output_dir.replace("\\", "/"), step_pair))
        print("  checkpoint saved: step_pair={0}".format(step_pair))

    print("step_pair={0:3d}  fine={1}  L={2} R={3}".format(
        step_pair, step_fine,
        [round(x, 1) for x in L_group] if L_group else [],
        [round(x, 1) for x in R_group] if R_group else []))

    if SMOKE_MAX_STEP_PAIR > 0 and step_pair >= SMOKE_MAX_STEP_PAIR:
        print("[SMOKE] stopped after step_pair={0}".format(step_pair))
        break

# ============================================================
# 最終存檔
# ============================================================
it.command("model save '{0}/no_shotcrete_v4_final'".format(output_dir.replace("\\", "/")))
print("Done.")
print("Monitor CSV saved to:  {0}".format(monitor_csv_path))
print("Boundary CSV saved to: {0}".format(boundary_csv_path))
print("Boundary GP list saved to: {0}".format(boundary_gp_list_path))
