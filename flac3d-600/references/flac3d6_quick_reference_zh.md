# FLAC3D 6.00 中文速查整理版

這份文件是 `flac3d-600` skill 的中文輔助速查，整理自本機資料夾：

`C:\Users\rocklab\iCloudDrive\碩一下\FLAC\FLAC3D6.0_完整速查手冊.md`

並參考同資料夾內的 FLAC3D 6.0 文件與 NotebookLM 摘要。最高依據仍是：

`C:\Program Files\Itasca\Flac3d600\flac3dhelp.chm`

若本文件與官方 Help、官方 `.f3dat` 範例衝突，以官方資料為準。

## 使用時機

讀這份文件的情境：

- 快速查 FLAC3D 6.00 常用指令。
- 建立或檢查 `.f3dat` 骨架。
- 檢查 tunnel excavation、boundary、history、range、FISH 寫法。

不要用這份文件：

- 推論 FLAC3D 7.x 指令。
- 取代官方 Help。
- 編造材料參數或現地條件。

## FLAC3D 6.00 指令結構

FLAC3D 6.00 常見結構：

```text
NOUN VERB OPTION MODIFIERS RANGE
```

例子：

```flac3d
zone face apply velocity-normal 0 range group 'Bottom'
zone cmodel assign mohr-coulomb range group 'rock'
zone property cohesion 1.0e6 friction 35 range group 'rock'
model solve ratio 1e-5
```

基本原則：

- 指令多以物件開頭，例如 `zone`、`model`、`structure`、`fish`。
- 範圍限制放在 `range` 後面。
- 群組名稱建議用單引號。
- 長指令可用行尾 `...` 延續。
- 註解用分號 `;`。

## `.f3dat` 基本骨架

這是結構範本，`<TODO>` 必須由使用者提供，不可自動填入工程參數。

```flac3d
model new
fish automatic-create off
model title '<TODO: model title>'

; 幾何
zone create brick size <TODO_i> <TODO_j> <TODO_k>
zone face skin

; 材料模型
zone cmodel assign mohr-coulomb range group '<TODO_group>'
zone property bulk <TODO> shear <TODO> ...
              cohesion <TODO> friction <TODO> dilation <TODO> tension <TODO> ...
              density <TODO> range group '<TODO_group>'

; 邊界條件
zone face apply velocity-normal 0 range group 'Bottom'
zone face apply velocity-normal 0 range group 'East' or 'West'
zone face apply velocity-normal 0 range group 'North' or 'South'

; 初始狀態
model gravity 9.81
zone initialize-stresses ratio <TODO_K0>

; 收斂監測
model history mechanical ratio-local

; 求解與儲存
model solve
model save '<TODO_save_name>'
```

## 模型初始化

常用：

```flac3d
model new
fish automatic-create off
model title 'example'
model largestrain off
```

注意：

- `model new` 會清空目前模型。
- 大型 FISH 程式建議 `fish automatic-create off`，避免打錯變數名稱卻自動建立新變數。
- `model largestrain on/off` 要配合問題型態，不能默默假設。

## 網格建立

常用 primitive：

```flac3d
zone create brick size 10 5 6
zone create radial-cylinder ...
zone create radial-brick ...
zone import '<TODO>.f3grid'
zone generate from-extruder
```

常用後處理：

```flac3d
zone face skin
```

`zone face skin` 會建立邊界 face group，常見如 `Top`、`Bottom`、`East`、`West`、`North`、`South`。實際群組名稱仍要以模型輸出檢查。

## 群組

建立群組：

```flac3d
zone group 'rock' range position-z -100 0
zone group 'tunnel' range cylinder end-1 (0,0,0) end-2 (100,0,0) radius 3
```

檢查群組用途：

- 開挖前必須先有 tunnel group。
- 賦予材料前必須確認 rock / fault group 存在。
- 邊界條件若用 group，必須確認 `zone face skin` 或其他流程已建立 face group。

## 本構模型

常用：

```flac3d
zone cmodel assign elastic
zone cmodel assign mohr-coulomb
zone cmodel assign hoek-brown
zone cmodel assign ubiquitous-joint
zone cmodel assign strain-softening
zone cmodel assign null
```

必填 property 不要猜。優先查：

- `SKILL.md` 的 constitutive model required parameters。
- `datafiles\ConstitutiveModels\` 官方 element test。
- `flac3dhelp.chm`。

常見材料性質：

```flac3d
zone property bulk <TODO> shear <TODO>
zone property young <TODO> poisson <TODO>
zone property cohesion <TODO> friction <TODO> dilation <TODO> tension <TODO>
zone property density <TODO>
```

若使用 `young` / `poisson`，需確認該模型與 FLAC3D 6.00 是否接受這組輸入；不確定時改用官方範例中的 `bulk` / `shear`。

## 邊界條件

Face 邊界：

```flac3d
zone face apply velocity-normal 0 range group 'Bottom'
zone face apply velocity-x 0 range group 'East'
zone face apply stress-normal -1.0e6 range group 'Top'
zone face apply pore-pressure 0 range group 'Top'
zone face apply quiet-normal range group 'Bottom'
```

Gridpoint 固定：

```flac3d
zone gridpoint fix velocity-x range position-x 0
zone gridpoint fix velocity-y range position-y 0
zone gridpoint fix velocity-z range position-z 0
zone gridpoint free velocity-x range position-x 0
```

注意：

- `velocity-normal 0` 是常見滾動邊界。
- 固定底部時要確認座標軸方向。
- 應力正負號要先說明。FLAC3D 常見壓縮為負值。

## 初始應力與重力

常用：

```flac3d
model gravity 9.81
zone initialize-stresses ratio <TODO_K0>
```

查核：

- SI 單位下重力通常約 9.81。
- K0 不能無來源亂填。
- 水壓、孔隙壓、有效應力狀態要分清楚。

## 求解與儲存

```flac3d
model history mechanical ratio-local
model solve
model solve ratio 1e-5
model step 1000
model save 'initial'
model restore 'initial'
```

`model save 'initial'` 會自動補 `.f3sav`。明寫 `'initial.f3sav'` 也常見，但同一專案內建議維持一致。

## 開挖

開挖前先定義群組：

```flac3d
zone group 'tunnel' range cylinder end-1 (0,0,0) end-2 (100,0,0) radius 3
```

瞬間開挖：

```flac3d
zone cmodel assign null range group 'tunnel'
model solve
model save 'after_excavation'
```

漸進式釋放：

```flac3d
zone relax excavate range group 'tunnel'
model solve
model save 'after_relax_excavation'
```

檢查：

- `range group 'tunnel'` 是否真的選到 zone。
- 開挖後是否重新 `model solve`。
- 每個主要階段是否 `model save`。

## 結構元素

Cable：

```flac3d
structure cable create by-line (0,0,0) (5,0,0) segments 5
structure cable property young <TODO> cross-sectional-area <TODO> ...
                         yield-tension <TODO> grout-cohesion <TODO> ...
                         grout-stiffness <TODO> grout-perimeter <TODO>
```

Liner：

```flac3d
structure liner create by-face range group 'tunnel'
structure liner property isotropic <TODO_E> <TODO_nu> thickness <TODO>
```

Beam / pile / shell / geogrid 必須查 `datafiles\Structure\<Element>\` 官方範例，不要只照名稱猜 property。

## Interface

常用於接觸面、節理面或材料交界面。建立方式與 property 名稱需查官方範例：

```text
datafiles\Interface\
```

不要在沒有來源時編造 normal stiffness、shear stiffness、friction、cohesion 等參數。

## History 監測

收斂：

```flac3d
model history mechanical ratio-local
model history mechanical unbalanced-maximum
```

位移：

```flac3d
zone history displacement-z position (<TODO_x>, <TODO_y>, <TODO_z>)
zone gridpoint history displacement-z position (<TODO_x>, <TODO_y>, <TODO_z>)
```

孔隙壓：

```flac3d
zone gridpoint history pore-pressure position (<TODO_x>, <TODO_y>, <TODO_z>)
```

支撐：

```flac3d
structure node history displacement-z position (<TODO_x>, <TODO_y>, <TODO_z>)
```

## Range 語法

```flac3d
range group 'rock'
range group 'rock' or 'fault'
range position (0,0,0) (10,10,10)
range position-x 0 100
range position-y 0 50
range position-z -100 0
range cylinder end-1 (0,0,0) end-2 (100,0,0) radius 3
range sphere center (0,0,0) radius 5
range id 1 10
```

查核：

- `range group` 選的是 zone group 還是 face group。
- position 座標是否與模型座標系一致。
- cylinder 軸線方向是否與隧道方向一致。

## FISH 基本語法

建議先關閉自動建立：

```flac3d
fish automatic-create off
```

函數：

```flac3d
fish define calc_value
    local a = 1.0
    local b = 2.0
    calc_value = a + b
end

[calc_value]
```

遍歷 zone：

```flac3d
fish define count_zones
    local n = 0
    loop foreach local z zone.list
        n = n + 1
    end_loop
    count_zones = n
end

[count_zones]
```

在 FISH 中執行 FLAC3D 指令：

```flac3d
fish define save_stage(name)
    command
        model save [name]
    end_command
end
```

注意：

- `[]` 是 inline FISH 表達式。
- `@func` 可呼叫已定義的 FISH 函數。
- `command ... end_command` 中的指令通常要等函數執行時才會報錯。

## 典型隧道分析流程

1. `model new`
2. 建立或匯入網格。
3. 建立岩性、斷層、隧道開挖區、邊界群組。
4. 指定本構模型與材料性質。
5. 設定邊界條件、重力、初始應力。
6. 求初始平衡。
7. 儲存初始狀態。
8. 依 step 開挖。
9. 每步開挖後安裝支撐或更新材料。
10. 每步求解並輸出 history / CSV。
11. 儲存每個主要階段。

範本：

```flac3d
model new
fish automatic-create off

call 'geometry.f3dat'
call 'material_setup.f3dat'

model gravity 9.81
zone initialize-stresses ratio <TODO_K0>
model solve
model save 'initial'

call 'excavation.f3dat'
model save 'final'
```

## 單位與換算

FLAC3D 本身不強制單位，但同一模型內必須一致。常見 SI：

| 量 | 常用單位 |
|---|---|
| 長度 | m |
| 力 | N |
| 應力 | Pa |
| 密度 | kg/m3 |
| 位移 | m |

專案監測資料若為 mm，而 FLAC3D 輸出為 m，loss function 比較前必須轉換：

```text
1 m = 1000 mm
```

## 常見錯誤檢查

- 使用非 FLAC3D 6.00 語法或舊式簡寫。
- 忘記 `zone face skin`，導致邊界 group 不存在。
- 開挖前沒有建立 `tunnel` group。
- `zone cmodel assign null range group 'tunnel'` 沒選到任何 zone。
- 密度把 `kg/m3` 寫成 `kN/m3`。
- 位移輸出 m，監測資料卻用 mm。
- `model save` 路徑受 working directory 影響。
- FISH `@func` 沒有對應 `fish define func`。
- 用 7.x 文件查到的指令直接放進 6.00。

## 查核順序

遇到不確定指令時：

1. 先查 `datafiles\` 官方範例。
2. 再查 `flac3dhelp.chm` 或 `HelpExcerpts\flac3dmodeling.pdf`。
3. 再查本文件。
4. 找不到就不要猜。
