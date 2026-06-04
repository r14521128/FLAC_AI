# -*- coding: utf-8 -*-
import itasca as it
it.command("python-reset-state false")
it.command('model restore "D:/FLAC_AI/3D_far/0601/step5_tunnel_marked"')

# ============================================================
# Mohr-Coulomb    
# ============================================================
# tension dilation 銝甇斗摰雿輻 FLAC3D Mohr-Coulomb 身潦
# strength order: SS_NK > SS_NC >  Interbedded_ST > SH_ST > Fault
# (density[kg/m3], young[GPa], poisson[-], cohesion[KPa], friction[deg],)
materials_mc = {
    'SS_NK':          (2565.0, 1.2e9, 0.29, 300e3, 38),
    'Interbedded_ST': (2520.0, 0.6e9, 0.32, 75e3, 35),
    'SH_ST':          (2538.0, 0.8e9, 0.38, 100e3, 32),
    'SS_NC':          (2485.0, 1.0e9, 0.25, 200e3, 42),
    'Fault':          (2490.0, 0.3e9, 0.30, 30e3, 20),
}

# ============================================================
# 靘lithology slot 痔抒黎蝯Mohr-Coulomb 璅∪
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
# tunnel 蝢斤靘x 挾鋆撠撗拇扳
#   x=2500~2600嚗S_NC
#   x=2600~2850嚗ault
#   x=2850~3000嚗H_ST
# 瘜冽嚗ㄐ芣 tunnel 蝢斤芋銝 tunnel null
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
# 瑼Ｘ嚗null zone嚗絞閮璅∪摨衣 0 zone
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
# 璇辣
# 璅∪蝭蝝 X:2500~3000, Y:4700~4900, Z:170~265
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
# 憪
# K0 身嚗 y 孵瘞游像瘥1.2
# ============================================================
it.command("""
model gravity 0 0 -9.81
zone initialize-stresses ratio 1.2 1.2
""")
 
print("initial stress done")
 
# ============================================================
# 撟唾﹛
#
# 雿輻 model solve elastic 撟唾﹛
# 閫敺飛園漲蝘鳴霈蝥蝘餃甇斤憪敞閮
# 亙蝥閬瘝嚗賢ㄐ甇賊 displacement
# 祆格臬遣蝡excavation  initial_state
#
# ============================================================
it.command("model solve elastic")
it.command("zone gridpoint initialize velocity (0,0,0)")
it.command("zone gridpoint initialize displacement (0,0,0)")
 
print("solve done")

# ============================================================
# Save initial state for excavation_unsupported.py
# ============================================================
it.command('model save "D:/FLAC_AI/3D_far/0601/initial_state_0601"')

print("saved: D:/FLAC_AI/3D_far/0601/initial_state_0601")
 
