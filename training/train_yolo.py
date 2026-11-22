"""
EcoSort AI - YOLO Training Script
====================================
Trains a YOLOv8 model for waste object detection.

Supports the experiments from the project plan:
  - Experiment 1: Train YOLO for waste detection
  - Experiment 3: Compare optimizers (Adam vs SGD)
  - Experiment 4: Tune learning rate and batch size
  - Experiment 6: Evaluate on test set

Metrics reported: Precision, Recall, mAP@50, mAP@50-95

Usage:
    python training/train_yolo.py --data data/yolo_dataset/data.yaml
    python training/train_yolo.py --data data/yolo_dataset/data.yaml --optimizer SGD
    python training/train_yolo.py --data data/yolo_dataset/data.yaml --lr 0.01 --batch 32
"""

import os
import sys
import argparse
import json
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import WEIGHTS_DIR


def train_yolo(data_yaml, epochs=100, imgsz=640, batch=16, optimizer='auto',
               lr0=0.001, patience=20, dropout=0.0, name='yolo_waste'):
    """
    Train YOLOv8 on the waste dataset.

    Args:
        data_yaml:   Path to data.yaml config file.
        epochs:      Number of training epochs.
        imgsz:       Input image size.
        batch:       Batch size.
        optimizer:   'auto', 'Adam', 'SGD', 'AdamW', 'RMSProp'.
        lr0:         Initial learning rate.
        patience:    Early stopping patience (epochs without improvement).
        dropout:     Dropout rate (0.0 to disable).
        name:        Experiment name (used in output directory).
    """
    from ultralytics import YOLO

    # Load a pre-trained YOLOv8n as starting point (transfer learning)
    model = YOLO('yolov8n.pt')

    # Training arguments
    train_args = {
        'data': data_yaml,
        'epochs': epochs,
        'imgsz': imgsz,
        'batch': batch,
        'optimizer': optimizer,
        'lr0': lr0,
        'patience': patience,
        'dropout': dropout,
        'name': f'{name}_{optimizer}_lr{lr0}_bs{batch}',
        'project': str(PROJECT_ROOT / 'training' / 'runs'),
        'exist_ok': True,
        'verbose': True,
    }

    print("=" * 60)
    print("EcoSort AI - YOLO Training")
    print("=" * 60)
    print(f"  Dataset:     {data_yaml}")
    print(f"  Epochs:      {epochs}")
    print(f"  Image size:  {imgsz}")
    print(f"  Batch size:  {batch}")
    print(f"  Optimizer:   {optimizer}")
    print(f"  Learning rate: {lr0}")
    print(f"  Patience:    {patience}")
    print(f"  Dropout:     {dropout}")
    print("=" * 60)

    # Train
    results = model.train(**train_args)

    # Evaluate on validation set
    print("\n" + "=" * 60)
    print("Validation Results")
    print("=" * 60)
    metrics = model.val()
    print(f"  Precision:   {metrics.box.mp:.4f}")
    print(f"  Recall:      {metrics.box.mr:.4f}")
    print(f"  mAP@50:      {metrics.box.map50:.4f}")
    print(f"  mAP@50-95:   {metrics.box.map:.4f}")

    # Save metrics
    metrics_dict = {
        'experiment': name,
        'optimizer': optimizer,
        'learning_rate': lr0,
        'batch_size': batch,
        'epochs': epochs,
        'precision': float(metrics.box.mp),
        'recall': float(metrics.box.mr),
        'mAP50': float(metrics.box.map50),
        'mAP50_95': float(metrics.box.map),
        'timestamp': datetime.now().isoformat(),
    }

    results_path = PROJECT_ROOT / 'training' / f'{name}_results.json'
    with open(results_path, 'w') as f:
        json.dump(metrics_dict, f, indent=2)
    print(f"\nResults saved to: {results_path}")

    # Copy best weights to models/weights/
    weights_src = PROJECT_ROOT / 'training' / 'runs' / \
                  f'{name}_{optimizer}_lr{lr0}_bs{batch}' / 'weights' / 'best.pt'
    weights_dst = Path(WEIGHTS_DIR) / 'yolo_waste.pt'
    if weights_src.exists():
        import shutil
        os.makedirs(WEIGHTS_DIR, exist_ok=True)
        shutil.copy2(weights_src, weights_dst)
        print(f"Best weights copied to: {weights_dst}")

    return metrics_dict


def compare_optimizers(data_yaml, epochs=50, **kwargs):
    """
    Experiment 3: Compare Adam vs SGD optimizers.

    Runs training with each optimizer and saves results for comparison.
    """
    results = {}
    for opt in ['Adam', 'SGD']:
        print(f"\n{'#' * 60}")
        print(f"# Training with {opt}")
        print(f"{'#' * 60}")
        metrics = train_yolo(
            data_yaml, epochs=epochs, optimizer=opt,
            name=f'compare_{opt}', **kwargs
        )
        results[opt] = metrics

    print("\n" + "=" * 60)
    print("Optimizer Comparison Summary")
    print("=" * 60)
    print(f"{'Metric':<20} {'Adam':>12} {'SGD':>12}")
    print("-" * 44)
    for metric_key, label in [('precision', 'Precision'), ('recall', 'Recall'),
                              ('mAP50', 'mAP@50'), ('mAP50_95', 'mAP@50-95')]:
        adam_val = results['Adam'].get(metric_key, 0)
        sgd_val = results['SGD'].get(metric_key, 0)
        print(f"{label:<20} {adam_val:>12.4f} {sgd_val:>12.4f}")

    # Save comparison
    comparison_path = PROJECT_ROOT / 'training' / 'optimizer_comparison.json'
    with open(comparison_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nComparison saved to: {comparison_path}")

    return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Train YOLO model for EcoSort AI waste detection')
    parser.add_argument('--data', required=True,
                        help='Path to data.yaml')
    parser.add_argument('--epochs', type=int, default=100,
                        help='Number of training epochs (default: 100)')
    parser.add_argument('--batch', type=int, default=16,
                        help='Batch size (default: 16)')
    parser.add_argument('--imgsz', type=int, default=640,
                        help='Image size (default: 640)')
    parser.add_argument('--optimizer', default='auto',
                        choices=['auto', 'Adam', 'SGD', 'AdamW', 'RMSProp'],
                        help='Optimizer (default: auto)')
    parser.add_argument('--lr', type=float, default=0.001,
                        help='Initial learning rate (default: 0.001)')
    parser.add_argument('--patience', type=int, default=20,
                        help='Early stopping patience (default: 20)')
    parser.add_argument('--dropout', type=float, default=0.0,
                        help='Dropout rate (default: 0.0)')
    parser.add_argument('--name', default='yolo_waste',
                        help='Experiment name')
    parser.add_argument('--compare-optimizers', action='store_true',
                        help='Run Experiment 3: compare Adam vs SGD')
    args = parser.parse_args()

    if args.compare_optimizers:
        compare_optimizers(args.data, epochs=args.epochs, batch=args.batch,
                          imgsz=args.imgsz, lr0=args.lr, patience=args.patience,
                          dropout=args.dropout)
    else:
        train_yolo(
            args.data, epochs=args.epochs, imgsz=args.imgsz,
            batch=args.batch, optimizer=args.optimizer, lr0=args.lr,
            patience=args.patience, dropout=args.dropout, name=args.name,
        )
