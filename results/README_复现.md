# README_复现

## 1. 项目结论

这次最终最优模型不是大模型，而是小模型 `deim_hgnetv2_s_coco` 的两阶段训练版本：

- 阶段一：小模型主线训练
- 阶段二：基于阶段一最佳权重继续微调

当前最佳模型：

- 模型文件：`dental_phone_best_small_tune_epoch17_map5095_0.7549.pth`
- 最佳轮次：`epoch 17`
- 训练链路：`small_main -> small_tune`

训练日志中的最佳指标：

- `mAP50-95 = 0.7548555068`
- `mAP50 = 0.9613500896`
- `mAP75 = 0.8810853275`
- `mAP_small = 0.6848293471`
- `mAP_medium = 0.7443382322`
- `mAP_large = 0.8412292129`
- `AR@1 = 0.2565638378`
- `AR@10 = 0.8053807377`
- `AR@100 = 0.8161844089`


## 2. 模型与数据

模型路线：

- `DEIM`
- `backbone = HGNetv2-B0`
- `decoder = DFINETransformer`

类别数：

- `7`

类别名：

- `1st Molar`
- `1st Premolar`
- `2nd Molar`
- `2nd Premolar`
- `Canine`
- `Central Incisor`
- `Lateral Incisor`

数据格式：

- 训练使用 `COCO JSON`
- 图像来自手机拍摄口内照片数据
- 没有把 `DENTEX X-ray` 混进这条最优主线


## 3. 环境准备

建议环境：

- `Ubuntu 20.04/22.04`
- `Python 3.10/3.11`
- `PyTorch + CUDA`

安装依赖：

```bash
pip install -r requirements.txt
```

如果仓库里 `engine/deim/__init__.py` 仍然因为可选模块导入报错，保留当前仓库里的兼容写法即可，不要回退。


## 4. 数据准备

当前训练使用的目录结构：

```text
DentalDataset/
  train/
    images/
    annotations.json
  valid/
    images/
    annotations.json
  test/
    images/
    annotations.json
```

如果你手上是 Roboflow 导出的 YOLO 数据，需要先转成 COCO JSON。

这次训练实际使用的 4 个关键路径是：

```text
train images: /root/autodl-tmp/Dent-FINE-DD3C/DentalDataset/train/images
train ann:    /root/autodl-tmp/Dent-FINE-DD3C/DentalDataset/train/annotations.json
valid images: /root/autodl-tmp/Dent-FINE-DD3C/DentalDataset/valid/images
valid ann:    /root/autodl-tmp/Dent-FINE-DD3C/DentalDataset/valid/annotations.json
```


## 5. 第一阶段训练

第一阶段目标：

- 用小模型先把主线训稳
- 得到一个高质量 `best_stg1.pth`

这次实际使用的第一阶段命令如下：

```bash
torchrun --standalone --nproc_per_node=1 train.py \
  -c configs/deim_dfine/deim_hgnetv2_s_coco.yml \
  -r /root/autodl-tmp/runs/dental_phone_best50/best_stg1.pth \
  --use-amp --seed 0 \
  --output-dir /root/autodl-tmp/runs/dental_phone_s80_parallel \
  -u num_classes=7 epoches=80 print_freq=40 checkpoint_freq=5 sync_bn=False \
     train_dataloader.total_batch_size=8 \
     val_dataloader.total_batch_size=8 \
     train_dataloader.num_workers=4 \
     val_dataloader.num_workers=4 \
     train_dataloader.dataset.img_folder=/root/autodl-tmp/Dent-FINE-DD3C/DentalDataset/train/images \
     train_dataloader.dataset.ann_file=/root/autodl-tmp/Dent-FINE-DD3C/DentalDataset/train/annotations.json \
     val_dataloader.dataset.img_folder=/root/autodl-tmp/Dent-FINE-DD3C/DentalDataset/valid/images \
     val_dataloader.dataset.ann_file=/root/autodl-tmp/Dent-FINE-DD3C/DentalDataset/valid/annotations.json \
     HGNetv2.pretrained=False
```

这一阶段的最好结果：

- `best epoch = 78`
- `mAP50-95 = 0.7540000544`


## 6. 第二阶段微调

第二阶段目标：

- 不从头再训
- 直接从第一阶段最佳权重继续搜索更好的局部最优

这次实际使用的第二阶段命令如下：

```bash
torchrun --standalone --nproc_per_node=1 train.py \
  -c configs/deim_dfine/deim_hgnetv2_s_coco.yml \
  -t /root/autodl-tmp/runs/dental_phone_s80_parallel/best_stg1.pth \
  --use-amp --seed 42 \
  --output-dir /root/autodl-tmp/runs/dental_phone_s_tune24 \
  -u num_classes=7 epoches=24 print_freq=40 checkpoint_freq=4 sync_bn=False \
     train_dataloader.total_batch_size=12 \
     val_dataloader.total_batch_size=12 \
     train_dataloader.num_workers=4 \
     val_dataloader.num_workers=4 \
     train_dataloader.dataset.img_folder=/root/autodl-tmp/Dent-FINE-DD3C/DentalDataset/train/images \
     train_dataloader.dataset.ann_file=/root/autodl-tmp/Dent-FINE-DD3C/DentalDataset/train/annotations.json \
     val_dataloader.dataset.img_folder=/root/autodl-tmp/Dent-FINE-DD3C/DentalDataset/valid/images \
     val_dataloader.dataset.ann_file=/root/autodl-tmp/Dent-FINE-DD3C/DentalDataset/valid/annotations.json \
     HGNetv2.pretrained=False optimizer.lr=0.00015
```

这一阶段的最好结果：

- `best epoch = 17`
- `mAP50-95 = 0.7548555068`


## 7. 什么是这次的微调方法

这次用的不是 LoRA，也不是只训最后一层。

这次“微调”的本质是：

- 先拿第一阶段已经训练好的最佳检测权重
- 再用 `-t` 继续训练整网
- 但把训练长度缩短到 `24 epoch`
- 把 batch 从 `8` 提到 `12`
- 把随机种子改成 `42`
- 把学习率显式设成 `optimizer.lr=0.00015`

也就是说，这次方法更准确的名字是：

- `checkpoint-based fine-tuning`
- 或者说：`best checkpoint continuation tuning`

它为什么有效：

- 第一阶段已经把模型带到较好的区域
- 第二阶段不需要再花大量时间做粗搜索
- 直接围绕当前最优点做更细的参数更新
- 对这份中小规模手机口腔数据，往往比“重开一个更大模型”更划算

这次微调里真正起作用的几个点：

- `-t best_stg1.pth`
- 较短训练周期
- 更大的 batch
- 更小、更稳的继续训练学习率


## 8. 我建议你以后继续怎么微调

如果以后继续追更高分，优先级建议如下。

### 8.1 最优先

继续围绕当前冠军权重做短程微调：

- 固定 `small_tune` 作为起点
- 试 `optimizer.lr` 在 `0.00008 ~ 0.0002`
- 试 `epoches` 在 `12 / 18 / 24 / 36`
- 试 `batch_size` 在显存允许范围内再增大

### 8.2 次优先

只改训练策略，不换模型：

- 改 seed
- 改验证阈值
- 改增强停止轮次
- 改 `mixup_epochs` 或 `stop_epoch`

### 8.3 不优先

直接换更大模型。

因为这次实验已经证明：

- 更大模型不自动更强
- 在你的手机照片数据上，小模型更适配


## 9. 推理与预览图生成

为了复现可视化结果，这次额外加了两个脚本：

- `tools/inference/export_coco_predictions.py`
- `tools/inference/export_preview_overlay.py`

### 9.1 导出验证集预测

```bash
python tools/inference/export_coco_predictions.py \
  --config configs/deim_dfine/deim_hgnetv2_s_coco.yml \
  --resume /path/to/best_stg1.pth \
  --image_dir /path/to/valid/images \
  --annotation_file /path/to/valid/annotations.json \
  --output /path/to/predictions.json \
  --metrics_output /path/to/metrics.json \
  --device cuda \
  --conf_threshold 0.3 \
  --num_classes 7
```

### 9.2 生成叠框预览图

```bash
python tools/inference/export_preview_overlay.py \
  --annotation_file /path/to/valid/annotations.json \
  --prediction_file /path/to/predictions.json \
  --image_dir /path/to/valid/images \
  --output_image /path/to/preview.png \
  --summary_json /path/to/preview_summary.json \
  --metrics_json /path/to/metrics.json
```

生成的预览图格式：

- 单张图
- 绿色框是 `GT`
- 红色框是 `Prediction`
- 右上角显示：
  - `mAP50-95`
  - `mAP50`
  - `平均 IoU`


## 10. 当前已保存的重要文件

本地 `Downloads` 里当前已经有：

- 最佳权重：`/Users/mico/Downloads/dental_phone_best_small_tune_epoch17_map5095_0.7549.pth`
- 预览图：`/Users/mico/Downloads/best_tune_validation_preview.png`
- 指标：`/Users/mico/Downloads/metrics.json`
- 预览摘要：`/Users/mico/Downloads/preview_summary.json`
- 预测导出脚本：`/Users/mico/Downloads/export_coco_predictions.py`
- 预览导出脚本：`/Users/mico/Downloads/export_preview_overlay.py`


## 11. 一句话复现建议

如果目标是最快复现现在的最佳效果：

- 直接使用已经导出的冠军权重推理

如果目标是完整复现实验：

- 先跑第一阶段 `small_main`
- 再从它的 `best_stg1.pth` 跑第二阶段 `small_tune`

