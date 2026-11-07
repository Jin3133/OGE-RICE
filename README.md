# OGE Main

禾灌智析项目的模型训练、推理、导出与部署适配工程。

## 当前目标

1. 使用 OGE 官方武汉一号耕地分割数据建立可复现基线。
2. 训练 SegFormer-B0 主模型和 DeepLabV3+ 对照模型。
3. 将模型导出为 ONNX，并验证 PyTorch 与 ONNX 推理一致性。
4. 保留 OGE 平台模型调用和第三方推理服务两种部署适配方式。
5. 后续加入水稻精标数据，将耕地模型迁移到水稻分割。

## 目录结构

```text
oge-main/
├── configs/                 # 实验配置
├── src/oge_main/            # 正式源码
│   ├── data/                # 数据集读取、划分与预处理
│   ├── models/              # SegFormer、DeepLabV3+ 模型封装
│   └── utils/               # 指标、随机种子与配置工具
├── tools/                   # 数据检查、训练、评估、导出入口
├── tests/                   # 单元测试
├── deployment/              # OGE 与 Web 后台部署适配
└── references/              # 开源参考仓库，不纳入 Git
```

## 数据位置

原始数据不复制到本仓库。默认读取：

```text
../oge-rice/data/raw/oge_wuhan1_farm/extracted/
89d279976ef74625a1ea00d6cad512c1_farm
```

可通过环境变量覆盖：

```bash
export OGE_FARM_DATASET=/absolute/path/to/dataset
```

## 开源实现选择

- 主模型基于 Hugging Face Transformers 的 SegFormer 实现。
- 对照模型基于 Segmentation Models PyTorch 的 DeepLabV3+ 实现。
- MMSegmentation仅作为配置、部署和模型转换参考，不作为第一版硬依赖。

这样可以避免工程被 OpenMMLab 全套依赖绑定，同时保留后续接入其部署工具的可能。

## 快速开始

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
python tools/check_dataset.py
python tools/make_split.py
```

正式训练前生成质量约束后的数据划分和训练集归一化参数：

```bash
python tools/prepare_training_data.py
```

`FarmSegmentationDataset` 会同时返回 `valid_mask`。训练损失和评价指标必须忽略三个
波段同时为零的像元；`oge_main.losses.masked_bce_dice_loss` 已实现这一规则。

模型训练和ONNX导出将在基线训练入口完成后启用。

