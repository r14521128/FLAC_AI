# -*- coding: utf-8 -*-
import itasca as it
it.command("python-reset-state false")
it.command("model restore 'step5_tunnel_marked'")

# ============================================================
# Mohr-Coulomb 材料參數   
# ============================================================
# tension 與 dilation 不在此指定，使用 FLAC3D Mohr-Coulomb 預設值。
# strength order: SS_NC > SS_NK > Interbedded_ST > SH_ST > Fault
# (density[kg/m3], young[Pa], poisson[-], cohesion[Pa], friction[deg],)
materials_mc = {
    'SS_NK':          (2565.0, 1.0e9, 0.29, 0.20e6, 38),
    'Interbedded_ST': (2520.0, 0.8e9, 0.32, 0.15e6, 35),
    'SH_ST':          (2538.0, 0.6e9, 0.38, 0.10e6, 32),
    'SS_NC':          (2485.0, 1.2e9, 0.25, 0.25e6, 42),
    'Fault':          (2490.0, 0.3e9, 0.30, 0.02e6, 20),
}

# ============================================================
# 依 lithology slot 的岩性群組套用 Mohr-Coulomb 模型與材料參數
# ============================================================
for grp, (den, E, nu, c, phi) in materials_mc.items():
    it.command(
        "zone cmodel assign mohr-coulomb range group '{}' slot 'lithology'".format(grp)
    )
    it.command((
        "zone property density {} young {} poisson {} "
        "cohesion {} friction {} "
        "range group '{}' slot 'lithology'"
    ).format(den, E, nu, c, phi, grp))

# ============================================================
# tunnel 群組依 x 里程分段補上對應岩性材料
#   x=2500~2600：SS_NC
#   x=2600~2850：Fault
#   x=2850~3000：SH_ST
# 注意：這裡只改 tunnel 群組的材料模型，不把 tunnel 挖除成 null。
# ============================================================

tunnel_segments = [
    (2500, 2600, 'SS_NC'),
    (2600, 2850, 'Fault'),
    (2850, 3000, 'SH_ST'),
]

for x_start, x_end, lyr_name in tunnel_segments:
    den, E, nu, c, phi = materials_mc[lyr_name]
    it.command(
        "zone cmodel assign mohr-coulomb "
        "range group 'tunnel' position-x {} {}".format(x_start, x_end)
    )
    it.command((
        "zone property density {} young {} poisson {} "
        "cohesion {} friction {} "
        "range group 'tunnel' position-x {} {}"
    ).format(den, E, nu, c, phi, x_start, x_end))

print("tunnel material done")
 
# ============================================================
# 材料檢核：略過 null zone，統計未指定模型或密度為 0 的 zone
# ============================================================
it.command("""
fish define check_material
    local n_no_model = 0
    local n_no_den   = 0
    loop foreach local z zone.list
        if zone.model(z) = 'null' then
            continue
        endif
        if zone.model(z) = 'none' then
            n_no_model = n_no_model + 1
            continue
        endif
        if zone.density(z) = 0.0 then
            n_no_den = n_no_den + 1
        endif
    endloop
    io.out('zones with no model : ' + string(n_no_model))
    io.out('zones with density=0: ' + string(n_no_den))
end
@check_material
""")
 
print("check done")
 
# ============================================================
# 邊界條件
# 模型範圍約為 X:2500~3000, Y:4700~4900, Z:170~265
# ============================================================
it.command("""
zone gridpoint fix velocity-x range position-x 2499 2501
zone gridpoint fix velocity-x range position-x 2999 3001
zone gridpoint fix velocity-y range position-y 4699 4701
zone gridpoint fix velocity-y range position-y 4899 4901
zone gridpoint fix velocity-z range position-z 169  171
""")
 
print("boundary done")
 
# ============================================================
# 重力與初始應力
# K0 假設：x 與 y 方向水平應力比皆為 1.2。
# ============================================================
it.command("""
model gravity 0 0 -9.81
zone initialize-stresses ratio 1.2 1.2
""")
 
print("initial stress done")
 
# ============================================================
# 初始平衡
#
# 使用 model solve elastic 先求初始重力平衡。
# 解完後歸零速度與位移，讓後續開挖位移從此狀態開始累計。
# 若後續需要看初始重力沉陷，不能在這裡歸零 displacement。
# 本檔目標是建立 excavation 前的 initial_state。
#
#
# ============================================================
it.command("model solve elastic")
it.command("zone gridpoint initialize velocity (0,0,0)")
it.command("zone gridpoint initialize displacement (0,0,0)")
 
print("solve done")
 
# ============================================================
# 儲存初始狀態
# ============================================================
it.command('model save "initial_state"')
 
print("saved: initial_state")
