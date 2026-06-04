# -*- coding: utf-8 -*-
# ============================================================
# excavation_unsupported.py
# 小模型 sub_2896：無支撐逐步開挖
#
# 功能：
#   1) 只使用小模型本身，不讀大模型邊界位移。
#   2) 不轉換大模型輸出，不讀大模型應力狀態。
#   3) 監測三個岩體點：頂拱、左側壁、右側壁。
#   4) 只在收斂後輸出最大塑性厚度。
#
# Run in FLAC3D IPython Console:
#   exec(open("D:/FLAC_AI/3D_small/0531/2896/excavation_unsupported.py").read())
# ============================================================

import itasca as it
import os
import csv
from collections import defaultdict

it.command("python-reset-state false")

# ============================================================
# 路徑與模型設定
# ============================================================
BASE_DIR = r"D:\FLAC_AI\3D_small\0531\2896"
PARENT_DIR = r"D:\FLAC_AI\3D_small\0531"
MODEL_ID = "sub_2896"

OUTPUT_DIR = os.path.join(BASE_DIR, "out")
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

# 優先讀子資料夾內的 build save；若尚未搬入，退回讀 0531 根目錄。
INITIAL_STATE_CANDIDATES = [
    os.path.join(BASE_DIR, "sub_2896_build"),
    os.path.join(PARENT_DIR, "sub_2896_build"),
]

def find_save_basename(candidates):
    for name in candidates:
        if os.path.isfile(name + ".f3sav"):
            return name.replace("\\", "/")
    return candidates[0].replace("\\", "/")

INITIAL_STATE_NAME = find_save_basename(INITIAL_STATE_CANDIDATES)

# ============================================================
# 小模型與監測點設定
# ============================================================
MONITOR_X = 2896.0
MODEL_XMIN = 2846.0
MODEL_XMAX = 2946.0

MONITOR_TARGETS = {
    "crown":  (MONITOR_X, 4800.0, 220.0),
    "wall_L": (MONITOR_X, 4797.0, 217.0),
    "wall_R": (MONITOR_X, 4803.0, 217.0),
}

# ============================================================
# 收斂與記錄參數
# ============================================================
RATIO_TARGET = 1e-5
SOLVE_CHUNK = 500
SOLVE_CAP = 20000
# 只在「監測斷面步」記錄這串 cycle 的位移演化
MONITOR_CYCLE_RECORDS = [50, 100, 200, 300, 400, 500, 1000]
CHECKPOINT_INTERVAL = 10

# FLAC3D console smoke test 用。正式運算時不要設定這些環境變數。
SMOKE_MAX_STEP = int(os.environ.get("FLAC_SMOKE_MAX_STEP", "0"))
if SMOKE_MAX_STEP > 0:
    SOLVE_CAP = int(os.environ.get("FLAC_SMOKE_SOLVE_CAP", "500"))
    MONITOR_CYCLE_RECORDS = [50]
    print("[SMOKE] max_step={0}, solve_cap={1}".format(SMOKE_MAX_STEP, SOLVE_CAP))

# ============================================================
# 讀取小模型 build save
# ============================================================
print("restore model: {0}".format(INITIAL_STATE_NAME))
it.command("model restore '{0}'".format(INITIAL_STATE_NAME))
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
if not x_slices:
    raise RuntimeError("No tunnel zones found. Please check group 'tunnel'.")

print("tunnel slices: {0}  x={1:.1f}~{2:.1f}".format(
    len(x_slices), x_slices[0], x_slices[-1]))

# 小模型內逐 slice 開挖；由小 x 往大 x。
excavation_groups = [[x] for x in x_slices]

# 用半個 slice 間距作為塑性厚度查詢的 x 方向容許範圍。
dx_list = [abs(x_slices[i + 1] - x_slices[i]) for i in range(len(x_slices) - 1)]
X_MARGIN = 0.51 * min(dx_list) if dx_list else 0.5
print("plastic thickness X_MARGIN = {0:.3f}".format(X_MARGIN))

# ============================================================
# 建立三個監測 gridpoint
# ============================================================
monitor_gps = {}
monitor_pos = {}

for name in ["crown", "wall_L", "wall_R"]:
    target = MONITOR_TARGETS[name]
    gp = it.gridpoint.near(target)
    pos = gp.pos()
    monitor_gps[name] = gp
    monitor_pos[name] = pos

    print("monitor point: {0}".format(name))
    print("  target=({0:.2f},{1:.2f},{2:.2f})".format(
        target[0], target[1], target[2]))
    print("  gp id={0} pos=({1:.2f},{2:.2f},{3:.2f})".format(
        gp.id(), pos[0], pos[1], pos[2]))

def get_monitor_disp(name):
    d = monitor_gps[name].disp()
    return d[0], d[1], d[2]

# ============================================================
# 建立 FISH 讀取 ratio_avg
# ============================================================
# zone.mech.ratio 是 FISH 內的全域平均力比 (average)。
# Python 不能直接讀這個 FISH 量，所以用一個穩定存在的 ref_zone
# 當暫存容器：FISH 寫入 zone.extra(ref_zone,10)，Python 再讀回來。
ref_zone = it.zone.near((MODEL_XMIN + 1.0, 4776.0, 193.0))
ref_id = ref_zone.id()
print("ref zone for ratio and extras: id={0}".format(ref_id))

it.command("""
fish define write_ratio_info
    local rz = zone.find({0})
    zone.extra(rz, 10) = zone.mech.ratio
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
    ; max_ring: 只計入距開挖輪廓 <= 此值(m) 的塑性 zone，排除遠場 in-situ 降伏
    local max_ring = 15.0

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
    loop foreach local gc gp.list
        if gp.extra(gc,21) = marker
            if gp.extra(gc,22) = marker
                n_contour = n_contour + 1
            endif
        endif
    endloop

    ; ---- 收集開挖輪廓點座標到陣列（只掃一次 gp.list）----
    ; 之後每個塑性 zone 只比對這 ~n_contour 個點，不再每次掃全部 gridpoint，大幅加速
    local cy = array.create(n_contour + 1)
    local cz = array.create(n_contour + 1)
    local ic = 0
    loop foreach local gc2 gp.list
        if gp.extra(gc2,21) = marker
            if gp.extra(gc2,22) = marker
                ic = ic + 1
                cy(ic) = gp.pos.y(gc2)
                cz(ic) = gp.pos.z(gc2)
            endif
        endif
    endloop

    local max_thick = 0.0
    local n_plastic = 0

    loop foreach local z2 zone.list
        local xz2 = zone.pos.x(z2)
        if xz2 >= qmin
            if xz2 <= qmax
                if zone.model(z2) # 'null'
                    if zone.group(z2,'default') # 'tunnel'
                        if zone.group(z2,'default') # 'excavation'
                            local st = zone.state(z2,1)
                            if math.and(st, plastic_bits) # 0
                                local zy = zone.pos.y(z2)
                                local zz = zone.pos.z(z2)
                                local min_dist = 1.0e30
                                if n_contour > 0
                                    local ip
                                    loop ip (1, n_contour)
                                        local dy = zy - cy(ip)
                                        local dz = zz - cz(ip)
                                        local d = math.sqrt(dy*dy + dz*dz)
                                        if d < min_dist
                                            min_dist = d
                                        endif
                                    end_loop
                                endif

                                if min_dist <= max_ring
                                    n_plastic = n_plastic + 1
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
    # 回傳：最大塑性厚度、塑性 zone 數量、輪廓 gridpoint 數量。
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
    # 強制每個開挖步先 cycle 至少 MIN_CYCLES，確保開挖真的力學鬆弛。
    # （ratio-average 在大模型會「太容易」達標 -> 0 cycle -> 開挖不變形 -> 位移=0）
    # MIN_CYCLES 是關鍵調校參數：若 fine 步的 cycle 記錄顯示位移到 1000 還在變，就調大。
    MIN_CYCLES = 2000
    total = 0
    while total < SOLVE_CAP:
        it.command("model cycle {0}".format(SOLVE_CHUNK))
        total += SOLVE_CHUNK
        if total >= MIN_CYCLES and get_ratio() <= target:
            return total, True

    return total, (get_ratio() <= target)

def convergence_status(ok, ratio_avg):
    if ok:
        return 1
    return "cap_ratio={0:.6e}".format(ratio_avg)

# ============================================================
# FLAC3D 原生 history
# ============================================================
it.command("history interval 50")
it.command("model history mechanical ratio-average")
it.command("model history mechanical unbalanced-maximum")

it.command("zone history displacement-z position ({0} {1} {2})".format(
    monitor_pos["crown"][0], monitor_pos["crown"][1], monitor_pos["crown"][2]))
it.command("zone history displacement-y position ({0} {1} {2})".format(
    monitor_pos["wall_L"][0], monitor_pos["wall_L"][1], monitor_pos["wall_L"][2]))
it.command("zone history displacement-y position ({0} {1} {2})".format(
    monitor_pos["wall_R"][0], monitor_pos["wall_R"][1], monitor_pos["wall_R"][2]))

# ============================================================
# CSV 輸出
# ============================================================
csv_path = os.path.join(OUTPUT_DIR, "unsupported_excavation_monitor_{0}.csv".format(MODEL_ID))

header = [
    "step", "phase", "cycle",
    "excav_xmin", "excav_xmax",
    "ratio_target", "ratio_avg", "converged",
    "plastic_thick_max_m", "plastic_nzone", "contour_ngp",
    "crown_gp_id", "crown_x", "crown_y", "crown_z", "crown_ux", "crown_uy", "crown_uz",
    "wallL_gp_id", "wallL_x", "wallL_y", "wallL_z", "wallL_ux", "wallL_uy", "wallL_uz",
    "wallR_gp_id", "wallR_x", "wallR_y", "wallR_z", "wallR_ux", "wallR_uy", "wallR_uz"
]

with open(csv_path, "wb") as f:
    csv.writer(f).writerow(header)

def write_row(step, phase, cycle, x_group, ratio_target, converged, calc_plastic=False):
    ratio_avg = get_ratio()
    xmin = min(x_group) if x_group else -1
    xmax = max(x_group) if x_group else -1

    if calc_plastic:
        plastic_thick, plastic_nzone, contour_ngp = get_plastic_thickness(x_group)
    else:
        plastic_thick, plastic_nzone, contour_ngp = "", "", ""

    crown_ux, crown_uy, crown_uz = get_monitor_disp("crown")
    wallL_ux, wallL_uy, wallL_uz = get_monitor_disp("wall_L")
    wallR_ux, wallR_uy, wallR_uz = get_monitor_disp("wall_R")

    row = [
        step, phase, cycle,
        xmin, xmax,
        ratio_target, ratio_avg, converged,
        plastic_thick, plastic_nzone, contour_ngp,
        monitor_gps["crown"].id(),
        monitor_pos["crown"][0], monitor_pos["crown"][1], monitor_pos["crown"][2],
        crown_ux, crown_uy, crown_uz,
        monitor_gps["wall_L"].id(),
        monitor_pos["wall_L"][0], monitor_pos["wall_L"][1], monitor_pos["wall_L"][2],
        wallL_ux, wallL_uy, wallL_uz,
        monitor_gps["wall_R"].id(),
        monitor_pos["wall_R"][0], monitor_pos["wall_R"][1], monitor_pos["wall_R"][2],
        wallR_ux, wallR_uy, wallR_uz
    ]

    with open(csv_path, "ab") as f:
        csv.writer(f).writerow(row)

# ============================================================
# 只開挖，不建立噴凝土
# ============================================================
def excavate_only(x_group):
    for xc in x_group:
        for z in slice_dict[xc]:
            z.set_group("excavation", "default")
    it.command("zone cmodel assign null range group 'excavation'")

# ============================================================
# 主迴圈：小模型逐 slice 開挖
# ============================================================
step = 0
monitor_crossed = False   # 開挖面是否已越過監測斷面 MONITOR_X

for x_group in excavation_groups:
    step += 1

    excavate_only(x_group)

    # 監測斷面步：開挖面首次越過 MONITOR_X 的那一步（只觸發一次詳細記錄）
    is_monitor_step = False
    if not monitor_crossed and x_group and max(x_group) >= MONITOR_X:
        monitor_crossed = True
        is_monitor_step = True

    if is_monitor_step:
        # 只有監測斷面這步：依序記錄 cycle 演化，再收斂 1e-5
        last_cycle = 0
        for c in MONITOR_CYCLE_RECORDS:
            inc = c - last_cycle
            if inc > 0:
                it.command("model cycle {0}".format(inc))
            write_row(step, "cycle", c, x_group, RATIO_TARGET, "", calc_plastic=False)
            last_cycle = c
        used, ok = solve_to_ratio(RATIO_TARGET)
        ratio_now = get_ratio()
        conv_status = convergence_status(ok, ratio_now)
        write_row(step, "conv_1e-5", last_cycle + used, x_group,
                  RATIO_TARGET, conv_status, calc_plastic=True)
    else:
        # 其他步：直接收斂 1e-5，只記最終那一筆（含花費 cycle）
        used, ok = solve_to_ratio(RATIO_TARGET)
        ratio_now = get_ratio()
        conv_status = convergence_status(ok, ratio_now)
        write_row(step, "conv_1e-5", used, x_group,
                  RATIO_TARGET, conv_status, calc_plastic=True)

    if not ok:
        print("  [WARN] step={0} NOT converged to 1e-5 (cap {1}, ratio={2:.6e})".format(
            step, SOLVE_CAP, ratio_now))

    if step % CHECKPOINT_INTERVAL == 0:
        it.command("model save '{0}/{1}_chk_{2:04d}'".format(
            OUTPUT_DIR.replace("\\", "/"), MODEL_ID, step))
        print("  checkpoint saved: step={0}".format(step))

    print("step={0:3d}  x={1}".format(
        step, [round(x, 1) for x in x_group]))

    if SMOKE_MAX_STEP > 0 and step >= SMOKE_MAX_STEP:
        print("[SMOKE] stopped after step={0}".format(step))
        break

# ============================================================
# 最終存檔
# ============================================================
it.command("model save '{0}/{1}_unsupported_final'".format(
    OUTPUT_DIR.replace("\\", "/"), MODEL_ID))
print("Done.")
print("CSV saved to: {0}".format(csv_path))
