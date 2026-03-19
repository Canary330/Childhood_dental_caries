import argparse
import json
import os
import sys
from pathlib import Path

import torch
import torch.nn as nn
import torchvision.transforms as T
from PIL import Image
from tqdm import tqdm

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))
from engine.core import YAMLConfig


class COCOResultGenerator:
    def __init__(self, annotation_file):
        with open(annotation_file, "r", encoding="utf-8") as f:
            self.coco_data = json.load(f)
        self.image_id_to_filename = {
            image["id"]: image["file_name"] for image in self.coco_data["images"]
        }
        self.results = []

    def add_detections(self, image_id, labels, boxes, scores, threshold):
        mask = scores > threshold
        labels = labels[mask].detach().cpu().numpy()
        boxes = boxes[mask].detach().cpu().numpy()
        scores = scores[mask].detach().cpu().numpy()

        for label, box, score in zip(labels, boxes, scores):
            x1, y1, x2, y2 = box
            self.results.append(
                {
                    "image_id": int(image_id),
                    "category_id": int(label),
                    "bbox": [float(x1), float(y1), float(x2 - x1), float(y2 - y1)],
                    "score": float(score),
                }
            )

    def save(self, output_path):
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)


def evaluate_coco(annotation_file, result_file):
    from pycocotools.coco import COCO
    from pycocotools.cocoeval import COCOeval

    coco_gt = COCO(annotation_file)
    coco_dt = coco_gt.loadRes(result_file)
    evaluator = COCOeval(coco_gt, coco_dt, "bbox")
    evaluator.evaluate()
    evaluator.accumulate()
    evaluator.summarize()
    stats = evaluator.stats.tolist()
    return {
        "mAP50_95": stats[0],
        "mAP50": stats[1],
        "mAP75": stats[2],
        "mAP_small": stats[3],
        "mAP_medium": stats[4],
        "mAP_large": stats[5],
        "AR@1": stats[6],
        "AR@10": stats[7],
        "AR@100": stats[8],
        "AR_small": stats[9],
        "AR_medium": stats[10],
        "AR_large": stats[11],
    }


def main(args):
    cfg = YAMLConfig(args.config, num_classes=args.num_classes)
    if "HGNetv2" in cfg.yaml_cfg:
        cfg.yaml_cfg["HGNetv2"]["pretrained"] = False

    checkpoint = torch.load(args.resume, map_location="cpu")
    state = checkpoint["ema"]["module"] if "ema" in checkpoint else checkpoint["model"]
    cfg.model.load_state_dict(state)

    class Model(nn.Module):
        def __init__(self):
            super().__init__()
            self.model = cfg.model.deploy()
            self.postprocessor = cfg.postprocessor.deploy()

        def forward(self, images, orig_target_sizes):
            outputs = self.model(images)
            return self.postprocessor(outputs, orig_target_sizes)

    device = torch.device(args.device)
    model = Model().to(device)
    model.eval()

    transform = T.Compose([T.Resize((640, 640)), T.ToTensor()])
    generator = COCOResultGenerator(args.annotation_file)

    with torch.no_grad():
        for image_id, filename in tqdm(sorted(generator.image_id_to_filename.items())):
            image_path = os.path.join(args.image_dir, filename)
            image = Image.open(image_path).convert("RGB")
            width, height = image.size
            orig_size = torch.tensor([[width, height]], device=device)
            image_tensor = transform(image).unsqueeze(0).to(device)
            labels, boxes, scores = model(image_tensor, orig_size)
            generator.add_detections(
                image_id=image_id,
                labels=labels[0],
                boxes=boxes[0],
                scores=scores[0],
                threshold=args.conf_threshold,
            )

    generator.save(args.output)
    metrics = evaluate_coco(args.annotation_file, args.output)
    if args.metrics_output:
        metrics_path = Path(args.metrics_output)
        metrics_path.parent.mkdir(parents=True, exist_ok=True)
        with open(metrics_path, "w", encoding="utf-8") as f:
            json.dump(metrics, f, ensure_ascii=False, indent=2)
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export COCO-format predictions for a tuned checkpoint.")
    parser.add_argument("--config", required=True, type=str)
    parser.add_argument("--resume", required=True, type=str)
    parser.add_argument("--image_dir", required=True, type=str)
    parser.add_argument("--annotation_file", required=True, type=str)
    parser.add_argument("--output", required=True, type=str)
    parser.add_argument("--metrics_output", type=str, default="")
    parser.add_argument("--device", type=str, default="cuda")
    parser.add_argument("--conf_threshold", type=float, default=0.3)
    parser.add_argument("--num_classes", type=int, default=7)
    args = parser.parse_args()
    main(args)
