# FLAC3D 6.00 Python 介面整理版

這份文件是 `flac3d-600` skill 的中文輔助筆記，整理自本機資料夾：

`C:\Users\rocklab\iCloudDrive\碩一下\FLAC\FLAC3D_Python_完整手冊.md`

並交叉參考同資料夾中的 Python 相關文件與 NotebookLM 摘要。最高依據仍然是本機 FLAC3D 6.00 官方安裝資料：

`C:\Program Files\Itasca\Flac3d600\`

## 使用時機

讀這份文件的情境：

- 使用 FLAC3D 6.00 內嵌 Python。
- 撰寫 `flac3d/run_simulation.py` 這類由 FLAC3D 呼叫的 Python 2.7 腳本。
- 使用 `import itasca as it` 控制模型。
- 使用 `zonearray` / `gridpointarray` 批次讀寫資料。
- 用 Python 輸出 CSV、讀取 JSON 參數、設定材料性質或監測點。

不要用這份文件處理：

- 外部 Orchestrator 的 Python 3.13 程式碼。
- FLAC3D 7.x 的 Python API。
- PFC 或 3DEC 專用 API。
- 授權、破解、DLL 覆蓋等非官方流程。

## 權威順序

1. 官方安裝資料：`flac3dhelp.chm`、`HelpExcerpts\`、`datafiles\`。
2. `flac3d-600/SKILL.md` 的硬性規則。
3. `references/v6_idioms.md` 與 `references/rules_digest.md`。
4. 本文件。

如果本文件與官方 Help 或官方範例衝突，以官方資料為準。

## 執行環境

FLAC3D 6.00 內嵌 Python 環境與外部 Orchestrator 不同。

| 位置 | Python | 用途 |
|---|---:|---|
| FLAC3D 內嵌 | Python 2.7.9 | 在 FLAC3D 內控制 zone、gridpoint、structure、FISH、指令 |
| 外部 Orchestrator | Python 3.13.5 | 控制反算流程、寫 `params.json`、讀 CSV、操作 SQLite |

重要限制：

| Python 2.7 限制 | 寫法 |
|---|---|
| 不支援 f-string | 用 `"{}".format(value)` |
| 不支援 type hints | 不寫 `x: float`、`-> None` |
| `5 / 2` 會得到整數 `2` | 需要小數時寫 `5.0 / 2.0` |
| 中文輸出可能觸發編碼問題 | FLAC3D 內嵌 Python 盡量輸出 ASCII 或寫入 UTF-8 檔案 |
| `it.command()` 多行字串對縮排敏感 | 三引號內每行不要多縮排 |

## 最小 Python 腳本骨架

這段是給 FLAC3D 內嵌 Python 2.7 使用，不是外部 Python 3。

```python
# -*- coding: utf-8 -*-
import json
import itasca as it

# 避免 model new / model restore 後清掉 Python 變數與函數
it.command("python-reset-state false")

with open("flac3d/params.json", "r") as fp:
    params = json.load(fp)

scale_factor = float(params["scale_factor"])
support_delay_step = int(params["support_delay_step"])

print("scale_factor = {}".format(scale_factor))
print("support_delay_step = {}".format(support_delay_step))
```

## it.command 用法

`it.command()` 會把字串送進 FLAC3D 指令解析器。它適合用來執行 `.f3dat` 指令，但不是 Python 語法。

單行指令：

```python
# -*- coding: utf-8 -*-
import itasca as it

it.command("python-reset-state false")
it.command("model new")
it.command("model title 'python controlled model'")
```

多行指令：

```python
# -*- coding: utf-8 -*-
import itasca as it

it.command("python-reset-state false")

it.command("""
model new
zone create brick size 2 2 2
zone cmodel assign elastic
zone property density 2200 young 1.0e9 poisson 0.25
model solve
model save 'python_example'
""")
```

注意：

- 三引號中的 FLAC3D 指令行不要多加 Python 縮排。
- 字串內使用 Python 變數時，用 `.format()`。
- 不要把外部 Python 3 的語法放進 FLAC3D 內嵌 Python。

變數嵌入：

```python
# -*- coding: utf-8 -*-
import itasca as it

it.command("python-reset-state false")

young = 2.0e9
poisson = 0.25
density = 2400

it.command("""
zone cmodel assign elastic
zone property young {} poisson {} density {}
""".format(young, poisson, density))
```

## 從 FLAC3D 呼叫 Python

專案既有 `.f3dat` 若已使用 `python_run "flac3d/run_simulation.py"`，不要無故改寫。若改用官方 Help 或範例中的其他 Python 載入命令，必須先以本機 FLAC3D 6.00 Help 驗證。

整理自筆記的常見入口：

```flac3d
program python-file "script.py"
```

專案目前常見入口：

```flac3d
python_run "flac3d/run_simulation.py"
```

二者不要混用。若要替換，先做最小 smoke test。

## Zone 物件介面

常用函數：

| API | 用途 |
|---|---|
| `it.zone.count()` | zone 數量 |
| `it.zone.list()` | 遍歷所有 zone |
| `it.zone.find(id)` | 依 ID 取得 zone |
| `it.zone.near((x, y, z))` | 找最接近座標的 zone |

常用 zone 方法：

| API | 用途 |
|---|---|
| `z.id()` | zone ID |
| `z.pos()` | zone 形心座標 |
| `z.vol()` | zone 體積 |
| `z.model()` | zone 本構模型名稱 |
| `z.props()` | 全部材料性質，回傳 dictionary |
| `z.prop("young")` | 讀取單一材料性質 |
| `z.set_prop("young", value)` | 寫入單一材料性質 |
| `z.group()` | 讀取群組 |
| `z.set_group("name")` | 設定群組 |

範例：

```python
# -*- coding: utf-8 -*-
import itasca as it

it.command("python-reset-state false")

z = it.zone.near((0.0, 0.0, 0.0))

if z is not None:
    print("zone id = {}".format(z.id()))
    print("zone position = {}".format(z.pos()))
    print("zone model = {}".format(z.model()))
    print("zone props = {}".format(z.props()))
```

## Gridpoint 物件介面

常用函數：

| API | 用途 |
|---|---|
| `it.gridpoint.count()` | gridpoint 數量 |
| `it.gridpoint.list()` | 遍歷所有 gridpoint |
| `it.gridpoint.find(id)` | 依 ID 取得 gridpoint |
| `it.gridpoint.near((x, y, z))` | 找最接近座標的 gridpoint |

常用 gridpoint 方法：

| API | 用途 |
|---|---|
| `gp.id()` | gridpoint ID |
| `gp.pos()` | 座標 |
| `gp.disp()` | 位移 |
| `gp.vel()` | 速度 |
| `gp.force_unbal()` | 不平衡力 |
| `gp.mass_gravity()` | 重力質量 |

範例：

```python
# -*- coding: utf-8 -*-
import itasca as it

it.command("python-reset-state false")

gp = it.gridpoint.near((0.0, 0.0, 0.0))

if gp is not None:
    print("gridpoint id = {}".format(gp.id()))
    print("position = {}".format(gp.pos()))
    print("displacement = {}".format(gp.disp()))
```

## Structure 物件介面

常見結構元素：

- `cable`
- `liner`
- `beam`
- `pile`
- `shell`
- `geogrid`

Python API 名稱與可用方法需以本機 Help 或 `dir()` 實測確認。不要只憑其他版本文件推定。

最小檢查：

```python
# -*- coding: utf-8 -*-
import itasca as it

it.command("python-reset-state false")

print(dir(it.structure))
```

## Extra 變數

Extra 適合把 Python 計算結果暫存在 FLAC3D 物件上，並跟著 save file 保存。

注意：Extra index 通常從 1 開始，不是 Python 慣用的 0。

```python
# -*- coding: utf-8 -*-
import itasca as it

it.command("python-reset-state false")

z = it.zone.near((0.0, 0.0, 0.0))

if z is not None:
    z.set_extra(1, 123.45)
    print(z.extra(1))
```

## zonearray

`zonearray` 適合大模型批次運算，比逐一 loop zone 快。

基本匯入：

```python
# -*- coding: utf-8 -*-
import numpy as np
import itasca as it
from itasca import zonearray as za

it.command("python-reset-state false")
np.set_printoptions(threshold=20)
```

常用項目：

| API | 用途 |
|---|---|
| `za.pos()` | 全部 zone 形心座標，通常為 `(N, 3)` |
| `za.stress()` | 全部 zone 應力張量 |
| `za.stress_flat()` | 扁平化應力資料 |
| `za.ids()` | zone ID 陣列 |
| `za.in_group("name")` | 判斷 zone 是否屬於某群組 |
| `za.set_group(mask, "name", "slot")` | 依 mask 設定群組與 slot |
| `za.set_prop_scalar("young", values)` | 批次寫入純量性質陣列 |

實測筆記指出：`za.get_prop_scalar()` 在 FLAC3D 6.0 / Python 2.7.9 下不可用；讀取材料性質時優先用物件介面或 FISH 驗證。

批次設定材料性質：

```python
# -*- coding: utf-8 -*-
import numpy as np
import itasca as it
from itasca import zonearray as za

it.command("python-reset-state false")

pos = za.pos()
z_coord = pos[:, 2]

upper_mask = z_coord > 0.0
young_values = np.ones(it.zone.count()) * 1.0e9
young_values[upper_mask] = 2.0e9

za.set_group(upper_mask, "upper_zone", "geometry")
za.set_prop_scalar("young", young_values)

print("zone count = {}".format(len(z_coord)))
print("upper zone count = {}".format(int(upper_mask.sum())))
```

## gridpointarray

`gridpointarray` 適合批次讀寫節點座標、位移、固定狀態與外力。

基本匯入：

```python
# -*- coding: utf-8 -*-
import numpy as np
import itasca as it
from itasca import gridpointarray as gpa

it.command("python-reset-state false")
np.set_printoptions(threshold=20)
```

常用項目：

| API | 用途 |
|---|---|
| `gpa.pos()` | 全部 gridpoint 座標 |
| `gpa.disp()` | 全部 gridpoint 位移 |
| `gpa.ids()` | gridpoint ID 陣列 |
| `gpa.fixity()` | 固定狀態 |
| `gpa.set_fixity(fixity)` | 寫回固定狀態 |
| `gpa.force_app()` | 外加力 |
| `gpa.set_force_app(force)` | 寫回外加力 |

找最大位移點：

```python
# -*- coding: utf-8 -*-
import numpy as np
import itasca as it
from itasca import gridpointarray as gpa

it.command("python-reset-state false")

disp = gpa.disp()
disp_mag = np.sqrt((disp * disp).sum(axis=1))
idx = int(disp_mag.argmax())

print("max displacement = {}".format(disp_mag[idx]))
print("gridpoint position = {}".format(gpa.pos()[idx]))
```

## Mask Array

Mask 是 NumPy 的布林陣列，用來選取一批 zone 或 gridpoint。

建立 mask：

```python
# -*- coding: utf-8 -*-
import numpy as np
import itasca as it
from itasca import zonearray as za

it.command("python-reset-state false")

pos = za.pos()
x = pos[:, 0]
y = pos[:, 1]
z = pos[:, 2]

tunnel_mask = (x > 2580.0) & (x < 2600.0) & (z < 0.0)

print("selected zones = {}".format(int(tunnel_mask.sum())))
```

常用邏輯：

| 寫法 | 意義 |
|---|---|
| `(x > 0.0) & (x < 10.0)` | 同時滿足 |
| `(group_a) \| (group_b)` | 任一滿足 |
| `~mask` | 反向選取 |

## Callback

Callback 會在求解過程中被 FLAC3D 重複呼叫，適合做監控或逐步輸出。使用前先確認觸發頻率，避免拖慢計算。

```python
# -*- coding: utf-8 -*-
import itasca as it

it.command("python-reset-state false")

def my_callback(*args):
    print("callback called")

it.set_callback("my_callback", -1)
it.command("model step 5")
it.remove_callback("my_callback", -1)
```

常用檢查：

```flac3d
list fish callback
```

## JSON 參數整合範本

外部 Python 可以先把當次模擬參數寫成 JSON，再由 FLAC3D 內嵌 Python 讀取。參數名稱應由專案自己定義，通用 skill 不預設任何工程參數。

```json
{
  "scale_factor": 1.2,
  "support_delay_step": 3
}
```

FLAC3D 內嵌 Python 2.7 讀取：

```python
# -*- coding: utf-8 -*-
import json
import itasca as it

it.command("python-reset-state false")

with open("flac3d/params.json", "r") as fp:
    params = json.load(fp)

scale_factor = float(params["scale_factor"])
support_delay_step = int(params["support_delay_step"])

print("scale_factor = {}".format(scale_factor))
print("support_delay_step = {}".format(support_delay_step))
```

真正寫入材料群組、支撐元素或施工階段時，必須確認群組名稱、slot、施工步序與 `.f3dat` / FISH 建模邏輯一致。不要默默假設群組或施工階段存在。

## 常見錯誤

- 在 FLAC3D 內嵌 Python 2.7 使用 f-string。
- 在 `it.command("""...""")` 裡讓 FLAC3D 指令多了 Python 縮排。
- `model new` 或 `model restore` 前沒有設定 `python-reset-state false`。
- 把外部 Python 3 套件直接拿到 FLAC3D 內嵌 Python 2.7 用。
- 誤以為 `za.get_prop_scalar()` 可用。
- 用 `zonearray` 批次寫入前沒有先確認 mask 數量。
- 改材料性質時沒有確認 `zone group` 名稱是否存在。

## 查核清單

在修改 FLAC3D 內嵌 Python 腳本前，先確認：

- 腳本是否真的在 FLAC3D 內執行，而不是外部 Python 3。
- 是否需要 `import itasca as it`。
- 是否需要 `python-reset-state false`。
- 是否有 Python 2.7 不支援的語法。
- JSON、CSV 路徑是否相對於 FLAC3D working directory。
- 寫入材料群組前是否有檢查 group。
- 批次 array 寫入前是否印出 mask 數量。
- 正式執行前是否有 save model state。
