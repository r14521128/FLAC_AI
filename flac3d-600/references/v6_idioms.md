# FLAC3D 6.00 — v6 idiomatic syntax reference

Distilled from the official `datafiles/` examples. Every snippet below has been verified against a real shipped file at `C:\Program Files\Itasca\Flac3d600\datafiles\…`. Use these as the v6 canonical patterns.

---

## 1. Skeleton of a v6 model

```
model new
fish automatic-create off                  ; disable auto-creation of FISH names from typos
model title 'My model'

; --- geometry
zone create brick size 10 3 5              ; or zone create radial-brick / radial-cylinder / etc.
zone face skin                             ; auto-label boundary groups: East/West/North/South/Top/Bottom

; --- constitutive model + properties
zone cmodel assign mohr-coulomb
zone property bulk 1e8  shear 0.3e8  ...
              friction 35  cohesion 1e3  tension 1e3  density 2200

; --- boundary conditions
zone face apply velocity-normal 0 range group 'East' or 'West'
zone face apply velocity-normal 0 range group 'North' or 'South'
zone face apply velocity-normal 0 range group 'Bottom'

; --- initial state
model gravity 9.81                         ; scalar = -z; or vector form: model gravity (0,0,-10)
zone initialize-stresses ratio 0.5         ; K0 = 0.5
; zone initialize-stresses ratio 1.0 0.5   ; two-arg form: K0_xx and K0_yy independently

; --- convergence monitor
model history mechanical ratio-local

; --- solve
model solve
model save 'initial'                       ; .f3sav auto-appended; 'initial.f3sav' also valid
```

Source: `datafiles/UsersGuide/Tutorial/QuickStart/first.f3dat`, `datafiles/ExampleApplications/ExcavationAndSupportOfShallowTunnel/ExcavationAndSupportOfShallowTunnel.f3dat`.

## 2. Geometry generation

| Command | Use |
|---|---|
| `zone create brick size <i> <j> <k>` | Simple hex block |
| `zone create radial-brick point 0 … point 1 … size … ratio …` | Brick with radial bias |
| `zone create radial-cylinder …` | Cylindrical mesh |
| `zone generate from-extruder` | Mesh from the GUI extruder tool |
| `zone generate from-building-blocks` | Mesh from the BuildingBlocks GUI tool |
| `zone import '<file>.f3grid'` | Import a saved grid |
| `building-blocks set create '<name>'` + `building-blocks block import from-file '<file.f3bset>' position …` | Programmatic building-blocks |

Source: `datafiles/UsersGuide/Geometry/example_*.f3dat`, `datafiles/UsersGuide/Tutorial/QuickStart/geometry.f3dat`.

## 3. Range syntax

```
range group 'soil'                                          ; by group name (set by zone group / zone face skin)
range group 'A' or 'B'                                      ; union of groups
range position (0,0,0) (1,0.8,2)                            ; axis-aligned box
range position-z 0.0                                        ; single plane / 1D selector
range position-x 0.0 10.0                                   ; range along one axis
range cylinder end-1 (0,0,0) end-2 (0,1,0) radius 0.5       ; cylinder
range sphere center (0,0,0) radius 0.3                      ; sphere
range id 1 3                                                ; structural-element ids
```

## 4. Boundary conditions

```
; velocity / fixity
zone gridpoint fix velocity-x range position-z 0.0
zone gridpoint fix velocity-y                                ; all directions
zone gridpoint free velocity-x range position-x 0 1          ; release

; face traction / stress
zone face apply velocity-normal 0 range group 'Bottom'
zone face apply stress-normal -1e5 range group 'Top'
zone face apply stress-normal 0 gradient (0,[-10*1000*0.5],0) range group 'East' or 'Top'

; pore pressure (groundwater)
zone gridpoint fix pore-pressure 0 range position-z 0
zone face apply pore-pressure 1e4 range group 'Top'
```

Source: `datafiles/UsersGuide/Tutorial/Illustrative/tutorial.f3dat`.

## 5. Excavation

```
; method A — instant null
zone group 'tunnel' range cylinder end-1 (0,-50,0) end-2 (0,50,0) radius 3
zone cmodel assign null range group 'tunnel'
model solve

; method B — graceful relaxation (v6 idiom)
zone relax excavate range group 'Space'
model solve
```

Source: `datafiles/UsersGuide/Tutorial/QuickStart/first.f3dat` (method B), every excavation example under `datafiles/ExampleApplications/`.

## 6. FISH idioms (v6)

```
; --- function definition
fish define area_avg(name)
    local sum_a = 0.0
    loop foreach local z zone.list
        sum_a = sum_a + zone.vol(z)
    end_loop
    return sum_a
end

; --- inline expression
[global crown_gp = gp.near(0,30,5.5)]

; --- call
@area_avg('soil')                          ; call FISH function
fish list @sum_a                           ; print value of FISH variable

; --- embedded command block inside FISH
fish define place_cables(num,segs)
    loop local n (1,num)
        local z_d = 5.5 - float(n)
        command
            structure cable create by-line 0 0.5 [z_d] 7 0.5 [z_d] segments [segs]
            structure cable property young 2e10 yield-tension 1e8 ...
        end_command
    end_loop
end
@place_cables(5,7)
```

Source: `datafiles/UsersGuide/Fish/ug-defining.f3dat`, `datafiles/UsersGuide/Fish/ug-excavation-sequence.f3dat`.

## 7. Histories

```
model history mechanical ratio-local                  ; convergence
zone history displacement-z position (0,0,5.)
zone history stress-zz position (0,0,5)
zone gridpoint history pore-pressure position (0,0,0)
structure node history displacement-x position (0,0,5)
```

## 8. Structural elements

```
structure cable create by-line 0 0 0 10 0 0 segments 10
structure cable create by-ray (1.0,0.4,1.5) (1,0,0) 4 segments 4
structure cable import from-geometry 'cables' segments 15 id 1 range group '1'
structure cable property young 2e9 yield-tension 1e8 ...
                       cross-sectional-area 1.0 ...
                       grout-cohesion 1e10 grout-stiffness 2e9 grout-perimeter 1.0

structure shell create by-face internal id 10 range group 'shell'
structure shell property isotropic 10.5e9 0.25 thickness 0.3 density 2500 range id 10

structure liner create by-face range group 'tunnel'
structure beam create by-line …
structure pile create …
structure geogrid create …
```

Source: `datafiles/Structure/<Element>/`, `datafiles/ExampleApplications/ExcavationAndSupportOfShallowTunnel/`.

## 9. Coupled flow

```
model configure fluid
zone fluid cmodel assign isotropic
zone fluid property permeability 1e-10 porosity 0.3
zone gridpoint fix pore-pressure 0 range position-z [water_table_z]
zone face apply pore-pressure 0 range group 'Top'
```

Source: `datafiles/Fluid/1DConsolidation/1DConsolidation-Coupled.f3dat`.

## 10. Solving / stepping / saving

```
model history mechanical ratio              ; or ratio-local, unbalanced-maximum
model solve                                  ; solve to ratio-tolerance default
model solve ratio 1e-5                       ; tighter tolerance
model step 1000                              ; fixed step count
model largestrain on                         ; or:  model largestrain true
model save 'initial'                         ; .f3sav appended
model save 'initial.f3sav'                   ; also fine — both forms in official examples
model restore 'initial'
```

## 11. File chaining

```
call 'geometry.f3dat'                        ; echoes commands
call 'check.f3dat' suppress                  ; runs silently
```

Source: every `master.f3dat` in `datafiles/`.

## 12. Non-v6 syntax policy

Do not use this file as a legacy-command conversion table. If a requested command looks like FLAC3D 3/5, FLAC3D 7, 3DEC, PFC, or another Itasca product, stop and ask the user to confirm the target product/version before writing code.
