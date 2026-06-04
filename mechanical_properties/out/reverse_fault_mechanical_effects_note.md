# 逆斷層地層反轉對岩體力學性質的影響

## 重點結論

逆斷層或逆衝斷層會使上盤沿斷層面向上移動，常見結果是老地層覆於年輕地層上。這種「地層年代反轉」本身不會自動讓年輕地層變強或老地層變弱；真正影響隧道材料參數的是斷層造成的破碎、剪裂、泥化、裂隙密度、膠結與流體改質。

因此本案不應只用：

```text
NK > ST > NC
```

就直接決定所有斷層附近參數。更合理的是：

```text
Fault_core < Fault_up/down damage zone < 未受斷層強烈影響的母岩
```

## 對本案參數的意義

1. `Fault_core`
   - 代表主要剪切帶、斷層泥、角礫化或高度破碎核心。
   - 應保留最低 `GSI`、最低 `E`、最低 `c`。

2. `Fault_up` / `Fault_down`
   - 代表斷層損傷帶，不一定像 core 一樣弱。
   - 若以砂岩塊、角礫、裂隙化母岩為主，參數可高於 core。
   - 若泥化、剪裂面密集或含水，仍應偏低。

3. 年輕地層受逆斷層衝擊
   - 年輕地層本身可能較弱，但若被老地層覆壓與構造壓密，局部膠結或壓密可能增加。
   - 反過來，強烈剪裂與張裂損傷會降低岩體模數與強度。
   - 所以對 `SS_NC` 不能只看「南莊層年輕」就一律極低；要看是否位於 fault core、damage zone，或遠離斷層。

## 本次試算處理

本次已將：

```text
Fault_up
Fault_core
Fault_down
```

分開計算 Hoek-Brown 與等效 Mohr-Coulomb 參數，最後再依分層厚度加權整合成一組 `Fault` 材料參數。

這比把三者直接合併成單一 `Fault` 更合理，因為文獻中的 fault-zone architecture 通常會區分 fault core 與 damage zone，兩者力學與水力性質不同。

## 使用來源

- USGS, fault and reverse/thrust fault definition: https://www.usgs.gov/index.php/faqs/what-a-fault-and-what-are-different-types
- Britannica, thrust fault and older-over-younger relation: https://www.britannica.com/science/thrust-fault
- Caine, Evans and Forster (1996), fault core and damage zone architecture: https://digitalcommons.usu.edu/geology_facpub/35/
- Faulkner et al. (2010), review of fault-zone structure, mechanics and fluid flow: https://www.researchwithrutgers.org/en/publications/a-review-of-recent-developments-concerning-the-structure-mechanic/
- Wassing et al. (2020), elastic and frictional fault-zone properties: https://www.mdpi.com/1996-1073/13/18/4606
