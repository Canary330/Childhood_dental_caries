import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.optimize import linear_sum_assignment


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def to_jsonable(value):
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [to_jsonable(v) for v in value]
    if isinstance(value, tuple):
        return [to_jsonable(v) for v in value]
    if isinstance(value, np.generic):
        return value.item()
    return value


def compute_iou(box1, box2):
    x1_min, y1_min, w1, h1 = box1
    x2_min, y2_min, w2, h2 = box2
    x1_max, y1_max = x1_min + w1, y1_min + h1
    x2_max, y2_max = x2_min + w2, y2_min + h2

    inter_xmin = max(x1_min, x2_min)
    inter_ymin = max(y1_min, y2_min)
    inter_xmax = min(x1_max, x2_max)
    inter_ymax = min(y1_max, y2_max)
    inter_w = max(0.0, inter_xmax - inter_xmin)
    inter_h = max(0.0, inter_ymax - inter_ymin)
    inter_area = inter_w * inter_h

    area1 = max(0.0, w1) * max(0.0, h1)
    area2 = max(0.0, w2) * max(0.0, h2)
    union = area1 + area2 - inter_area
    return inter_area / union if union > 0 else 0.0


def match_boxes(preds, gts, iou_threshold=0.5):
    if not preds or not gts:
        return [], list(range(len(preds))), list(range(len(gts)))

    cost = np.zeros((len(preds), len(gts)), dtype=np.float32)
    for i, pred in enumerate(preds):
        for j, gt in enumerate(gts):
            cost[i, j] = -compute_iou(pred["bbox"], gt["bbox"])

    pred_indices, gt_indices = linear_sum_assignment(cost)
    matches = []
    unmatched_preds = set(range(len(preds)))
    unmatched_gts = set(range(len(gts)))

    for pred_idx, gt_idx in zip(pred_indices, gt_indices):
        iou = -float(cost[pred_idx, gt_idx])
        if iou >= iou_threshold:
            matches.append((pred_idx, gt_idx, iou))
            unmatched_preds.discard(pred_idx)
            unmatched_gts.discard(gt_idx)

    return matches, sorted(unmatched_preds), sorted(unmatched_gts)


def evaluate_coco(annotation_file, prediction_file):
    try:
        from pycocotools.coco import COCO
        from pycocotools.cocoeval import COCOeval
    except ImportError:
        return None

    coco_gt = COCO(annotation_file)
    coco_dt = coco_gt.loadRes(prediction_file)
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


def build_image_stats(coco_data, predictions, iou_threshold):
    gt_by_image = defaultdict(list)
    pred_by_image = defaultdict(list)
    for ann in coco_data["annotations"]:
        gt_by_image[ann["image_id"]].append(ann)
    for pred in predictions:
        pred_by_image[pred["image_id"]].append(pred)

    image_stats = {}
    matched_ious = []
    for image in coco_data["images"]:
        image_id = image["id"]
        gts = gt_by_image.get(image_id, [])
        preds = pred_by_image.get(image_id, [])
        matches, unmatched_preds, unmatched_gts = match_boxes(preds, gts, iou_threshold=iou_threshold)
        per_image_ious = [item[2] for item in matches]
        matched_ious.extend(per_image_ious)
        cls_correct = sum(
            1 for pred_idx, gt_idx, _ in matches
            if preds[pred_idx]["category_id"] == gts[gt_idx]["category_id"]
        )
        image_stats[image_id] = {
            "file_name": image["file_name"],
            "gt_count": len(gts),
            "pred_count": len(preds),
            "match_count": len(matches),
            "class_correct": cls_correct,
            "mean_iou": float(np.mean(per_image_ious)) if per_image_ious else 0.0,
            "matches": matches,
            "unmatched_preds": unmatched_preds,
            "unmatched_gts": unmatched_gts,
        }

    overall_mean_iou = float(np.mean(matched_ious)) if matched_ious else 0.0
    return gt_by_image, pred_by_image, image_stats, overall_mean_iou


def choose_image(coco_data, image_stats, image_id=None):
    if image_id is not None:
        return image_id

    ranked = sorted(
        coco_data["images"],
        key=lambda item: (
            image_stats[item["id"]]["gt_count"],
            image_stats[item["id"]]["match_count"],
            image_stats[item["id"]]["mean_iou"],
        ),
        reverse=True,
    )
    return ranked[0]["id"]


def measure_text(draw, text, font):
    bbox = draw.multiline_textbbox((0, 0), text, font=font, spacing=4)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def render_overlay(
    image_path,
    output_path,
    gt_anns,
    pred_anns,
    category_names,
    metrics,
    mean_iou,
):
    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()

    gt_color = (34, 197, 94)
    pred_color = (239, 68, 68)
    panel_bg = (255, 255, 255)
    panel_border = (30, 41, 59)
    text_color = (15, 23, 42)

    for ann in gt_anns:
        x, y, w, h = ann["bbox"]
        draw.rectangle([x, y, x + w, y + h], outline=gt_color, width=3)
        label = f"GT {category_names.get(ann['category_id'], ann['category_id'])}"
        draw.text((x + 2, max(0, y - 12)), label, fill=gt_color, font=font)

    for ann in pred_anns:
        x, y, w, h = ann["bbox"]
        draw.rectangle([x, y, x + w, y + h], outline=pred_color, width=2)
        label = f"P {category_names.get(ann['category_id'], ann['category_id'])} {ann.get('score', 0):.2f}"
        draw.text((x + 2, y + 2), label, fill=pred_color, font=font)

    metrics_text = "\n".join(
        [
            f"mAP50-95 = {metrics['mAP50_95']:.4f}",
            f"mAP50 = {metrics['mAP50']:.4f}",
            f"平均 IoU = {mean_iou:.4f}",
        ]
    )
    legend_text = "绿色: GT\n红色: Prediction"
    metrics_w, metrics_h = measure_text(draw, metrics_text, font)
    legend_w, legend_h = measure_text(draw, legend_text, font)
    panel_w = max(metrics_w, legend_w) + 20
    panel_h = metrics_h + legend_h + 28
    x0 = max(8, image.width - panel_w - 12)
    y0 = 12
    x1 = x0 + panel_w
    y1 = y0 + panel_h
    draw.rounded_rectangle([x0, y0, x1, y1], radius=10, fill=panel_bg, outline=panel_border, width=2)
    draw.multiline_text((x0 + 10, y0 + 8), metrics_text, fill=text_color, font=font, spacing=4)
    draw.multiline_text((x0 + 10, y0 + 16 + metrics_h), legend_text, fill=text_color, font=font, spacing=4)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)


def main():
    parser = argparse.ArgumentParser(description="Render a single-image GT/prediction overlay from COCO JSON predictions.")
    parser.add_argument("--annotation_file", required=True, type=str)
    parser.add_argument("--prediction_file", required=True, type=str)
    parser.add_argument("--image_dir", required=True, type=str)
    parser.add_argument("--output_image", required=True, type=str)
    parser.add_argument("--summary_json", required=True, type=str)
    parser.add_argument("--image_id", type=int, default=None)
    parser.add_argument("--metrics_json", type=str, default="")
    parser.add_argument("--iou_threshold", type=float, default=0.5)
    args = parser.parse_args()

    coco_data = load_json(args.annotation_file)
    predictions = load_json(args.prediction_file)
    category_names = {cat["id"]: cat["name"] for cat in coco_data.get("categories", [])}

    gt_by_image, pred_by_image, image_stats, mean_iou = build_image_stats(
        coco_data, predictions, iou_threshold=args.iou_threshold
    )
    if args.metrics_json:
        metrics = load_json(args.metrics_json)
    else:
        metrics = evaluate_coco(args.annotation_file, args.prediction_file)
        if metrics is None:
            raise RuntimeError("Provide --metrics_json or install pycocotools to compute COCO metrics.")

    selected_image_id = choose_image(coco_data, image_stats, image_id=args.image_id)
    selected = next(img for img in coco_data["images"] if img["id"] == selected_image_id)
    image_path = Path(args.image_dir) / selected["file_name"]
    render_overlay(
        image_path=image_path,
        output_path=Path(args.output_image),
        gt_anns=gt_by_image.get(selected_image_id, []),
        pred_anns=pred_by_image.get(selected_image_id, []),
        category_names=category_names,
        metrics=metrics,
        mean_iou=mean_iou,
    )

    summary = {
        "selected_image_id": selected_image_id,
        "selected_file_name": selected["file_name"],
        "metrics": metrics,
        "mean_iou": mean_iou,
        "image_stats": image_stats[selected_image_id],
        "prediction_count_total": len(predictions),
        "category_names": category_names,
    }
    summary_path = Path(args.summary_json)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(to_jsonable(summary), f, ensure_ascii=False, indent=2)

    print(json.dumps(to_jsonable(summary), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
