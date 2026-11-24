"""Fine-tune a YOLO model on your own objects (for example a Monster Energy can).

1. Take 150+ photos of each object: different angles, lighting, backgrounds, hands holding it.
2. Label them with any YOLO-format tool (Roboflow, CVAT, Label Studio, labelImg).
3. Copy data/custom_dataset.example.yaml, point it at your images and list your class names.
4. Run:   python scripts/train_custom.py --data data/my_dataset.yaml --epochs 50
5. Copy runs/detect/train/weights/best.pt next to config.toml and set  model = "best.pt".
6. Add an entry for each new label to data/knowledge_base.json.

Start from the COCO weights so the model keeps knowing laptops, cups and so on.
Note: a model trained only on your classes forgets the COCO ones; mix both datasets if you need both.
"""
from __future__ import annotations

import argparse


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="dataset YAML file")
    ap.add_argument("--base", default="yolo11n.pt", help="starting weights")
    ap.add_argument("--epochs", type=int, default=50)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--device", default=None, help="e.g. 0 for the first GPU, or cpu")
    a = ap.parse_args()
    from ultralytics import YOLO
    model = YOLO(a.base)
    model.train(data=a.data, epochs=a.epochs, imgsz=a.imgsz, device=a.device)
    metrics = model.val()
    print("mAP50-95:", metrics.box.map)


if __name__ == "__main__":
    main()
