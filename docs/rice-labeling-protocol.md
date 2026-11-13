# 水稻标注规范 v1

## 标注目标

首轮标注用于验证水稻候选区提取和业务闭环，不追求一次覆盖全部江夏区。四个5 km样区使用2025年7月7日RGB影像作为统一标注底图，其他四个时相的RGB、假彩色和NDVI仅作为判读参考。

由于各时相具有完全一致的范围、坐标和500×500像元网格，主图上的像素多边形能够映射回GeoTIFF，并复用于其他时相。

## LabelMe类别

只使用以下两个标签：

- `rice`：能够结合多时相特征较有把握地确认的水稻地块；
- `ignore`：云影、边界不清、作物类型无法判断或其他不应参与训练与评价的区域。

非水稻地物不需要逐一画`non_rice`，未标注区域默认作为背景。若整幅影像确认没有水稻，可以保持`shapes`为空，并将JSON中的`verified_empty`改为`true`、`annotation_status_unreviewed`改为`false`。

## 标注顺序

1. 优先标注`JX5K_R05C04`，该区规则农田较集中，用于建立正样本；
2. 标注`JX5K_R03C06`，补充混合农田和塘库周边地块；
3. 检查`JX5K_R07C05`，该区水体占比较高，主要用于确认困难负样本；
4. 标注`JX5K_R10C10`，补充城郊、道路和破碎地块背景。

## 判读原则

- 必须同时参考五个时相，不凭单张绿色程度判断水稻；
- 结合移栽前后的水分或裸地背景、7—8月植被增长以及10月成熟衰退进行判断；
- 优先沿真实田块边界绘制，尽量排除道路、水渠、塘库、建筑和林地；
- 10 m影像无法支持过细边界，避免在单像元尺度频繁折线；
- 相邻且具有相同物候表现的连续田块可以合并，存在明显道路或水渠时应分开；
- 无法确认的地块不要强行标为水稻，可暂不标注或使用`ignore`。

## 质量要求

- 多边形不得自相交；
- 不得超出图像边界；
- `rice`与`ignore`不应重叠；
- 标注完成后将`annotation_status_unreviewed`改为`false`；
- 每个样区至少由另一名成员快速复核一次；
- 训练集、验证集和测试集后续按空间样区划分，不能把同一地块的不同日期随机分散到不同集合。

## 文件位置

LabelMe任务目录：

`/Users/j/Documents/科研/oge/oge-rice/data/raw/labeling/labelme_rice_v1/tasks`

多时相参考目录：

`/Users/j/Documents/科研/oge/oge-rice/data/raw/labeling/labelme_rice_v1/references`

打开方式：

```bash
labelme /Users/j/Documents/科研/oge/oge-rice/data/raw/labeling/labelme_rice_v1/tasks
```
