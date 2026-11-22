"""
EcoSort AI - CNN Quality Classifier Training Script
=====================================================
Trains a ResNet18-based CNN to classify waste images as
'clean' or 'contaminated' using transfer learning.

Supports the experiments from the project plan:
  - Experiment 2: Train CNN for clean/contaminated classification
  - Experiment 3: Compare optimizers (Adam vs SGD)
  - Experiment 4: Tune learning rate and batch size
  - Experiment 5: Dropout and Early Stopping
  - Experiment 6: Evaluate on test set

Metrics reported: Accuracy, Precision, Recall, F1-score, Confusion Matrix

Usage:
    python training/train_cnn.py --data data/cnn_dataset
    python training/train_cnn.py --data data/cnn_dataset --optimizer SGD --lr 0.001
    python training/train_cnn.py --data data/cnn_dataset --compare-optimizers
"""

import os
import sys
import json
import argparse
import numpy as np
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import WEIGHTS_DIR, CNN_MODEL_PATH


def train_cnn(data_dir, epochs=50, batch_size=32, optimizer='Adam',
              lr=0.001, patience=15, dropout=0.5, name='cnn_quality'):
    """
    Train a ResNet18 CNN for clean/contaminated classification.

    Args:
        data_dir:    Root directory with train/val/test subdirectories.
        epochs:      Max training epochs.
        batch_size:  Batch size.
        optimizer:   'Adam' or 'SGD'.
        lr:          Learning rate.
        patience:    Early stopping patience.
        dropout:     Dropout rate.
        name:        Experiment name.
    """
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader
    from torchvision import transforms, models
    from torchvision.datasets import ImageFolder

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Device: {device}")

    # --- Data transforms with augmentation for training ---
    train_transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.RandomHorizontalFlip(),
        transforms.RandomRotation(15),
        transforms.ColorJitter(brightness=0.2, contrast=0.2,
                               saturation=0.2, hue=0.1),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406],
                             std=[0.229, 0.224, 0.225]),
    ])

    eval_transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406],
                             std=[0.229, 0.224, 0.225]),
    ])

    # --- Load datasets ---
    train_path = os.path.join(data_dir, 'train')
    val_path = os.path.join(data_dir, 'val')
    test_path = os.path.join(data_dir, 'test')

    train_dataset = ImageFolder(train_path, transform=train_transform)
    val_dataset = ImageFolder(val_path, transform=eval_transform)
    test_dataset = ImageFolder(test_path, transform=eval_transform) \
        if os.path.exists(test_path) else None

    train_loader = DataLoader(train_dataset, batch_size=batch_size,
                              shuffle=True, num_workers=2)
    val_loader = DataLoader(val_dataset, batch_size=batch_size,
                            shuffle=False, num_workers=2)
    test_loader = DataLoader(test_dataset, batch_size=batch_size,
                             shuffle=False, num_workers=2) if test_dataset else None

    print(f"Train samples: {len(train_dataset)}")
    print(f"Val samples:   {len(val_dataset)}")
    if test_dataset:
        print(f"Test samples:  {len(test_dataset)}")
    print(f"Classes:       {train_dataset.classes}")

    # --- Build model (ResNet18 with transfer learning) ---
    model = models.resnet18(weights=models.ResNet18_Weights.IMAGENET1K_V1)

    # Freeze early layers (transfer learning)
    for param in model.parameters():
        param.requires_grad = False

    # Replace the final FC layer
    num_features = model.fc.in_features
    model.fc = nn.Sequential(
        nn.Dropout(p=dropout),
        nn.Linear(num_features, 2),  # 2 classes: clean, contaminated
    )
    model = model.to(device)

    # --- Loss and optimizer ---
    criterion = nn.CrossEntropyLoss()

    if optimizer.lower() == 'adam':
        opt = torch.optim.Adam(model.fc.parameters(), lr=lr, weight_decay=1e-4)
    elif optimizer.lower() == 'sgd':
        opt = torch.optim.SGD(model.fc.parameters(), lr=lr, momentum=0.9,
                              weight_decay=1e-4)
    else:
        raise ValueError(f"Unknown optimizer: {optimizer}")

    # Learning rate scheduler
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        opt, mode='min', factor=0.5, patience=5
    )

    # --- Training loop ---
    best_val_loss = float('inf')
    patience_counter = 0
    history = {'train_loss': [], 'val_loss': [],
               'train_acc': [], 'val_acc': []}

    print("\n" + "=" * 60)
    print(f"Training: {name}")
    print(f"  Optimizer:   {optimizer}")
    print(f"  LR:          {lr}")
    print(f"  Batch size:  {batch_size}")
    print(f"  Dropout:     {dropout}")
    print(f"  Patience:    {patience}")
    print("=" * 60)

    for epoch in range(epochs):
        # --- Train ---
        model.train()
        running_loss = 0.0
        correct = 0
        total = 0

        for images, labels in train_loader:
            images, labels = images.to(device), labels.to(device)
            opt.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, labels)
            loss.backward()
            opt.step()

            running_loss += loss.item() * images.size(0)
            _, predicted = outputs.max(1)
            total += labels.size(0)
            correct += predicted.eq(labels).sum().item()

        train_loss = running_loss / len(train_dataset)
        train_acc = correct / total

        # --- Validate ---
        model.eval()
        val_loss = 0.0
        correct = 0
        total = 0

        with torch.no_grad():
            for images, labels in val_loader:
                images, labels = images.to(device), labels.to(device)
                outputs = model(images)
                loss = criterion(outputs, labels)
                val_loss += loss.item() * images.size(0)
                _, predicted = outputs.max(1)
                total += labels.size(0)
                correct += predicted.eq(labels).sum().item()

        val_loss /= len(val_dataset)
        val_acc = correct / total

        history['train_loss'].append(train_loss)
        history['val_loss'].append(val_loss)
        history['train_acc'].append(train_acc)
        history['val_acc'].append(val_acc)

        scheduler.step(val_loss)

        print(f"Epoch {epoch+1}/{epochs} | "
              f"Train Loss: {train_loss:.4f} Acc: {train_acc:.4f} | "
              f"Val Loss: {val_loss:.4f} Acc: {val_acc:.4f}")

        # --- Early stopping ---
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            patience_counter = 0
            # Save best model
            os.makedirs(WEIGHTS_DIR, exist_ok=True)
            torch.save(model.state_dict(), CNN_MODEL_PATH)
        else:
            patience_counter += 1
            if patience_counter >= patience:
                print(f"\nEarly stopping at epoch {epoch+1} "
                      f"(no improvement for {patience} epochs)")
                break

    # --- Evaluate on test set ---
    if test_loader:
        model.load_state_dict(torch.load(CNN_MODEL_PATH,
                                         map_location=device))
        model.eval()

        all_preds = []
        all_labels = []
        with torch.no_grad():
            for images, labels in test_loader:
                images = images.to(device)
                outputs = model(images)
                _, predicted = outputs.max(1)
                all_preds.extend(predicted.cpu().numpy())
                all_labels.extend(labels.numpy())

        all_preds = np.array(all_preds)
        all_labels = np.array(all_labels)

        # Compute metrics
        accuracy = (all_preds == all_labels).mean()
        tp = ((all_preds == 1) & (all_labels == 1)).sum()
        fp = ((all_preds == 1) & (all_labels == 0)).sum()
        fn = ((all_preds == 0) & (all_labels == 1)).sum()
        tn = ((all_preds == 0) & (all_labels == 0)).sum()

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) \
            if (precision + recall) > 0 else 0

        # Confusion matrix
        cm = [[int(tn), int(fp)], [int(fn), int(tp)]]

        print("\n" + "=" * 60)
        print("Test Results")
        print("=" * 60)
        print(f"  Accuracy:  {accuracy:.4f}")
        print(f"  Precision: {precision:.4f}")
        print(f"  Recall:    {recall:.4f}")
        print(f"  F1-score:  {f1:.4f}")
        print(f"  Confusion Matrix:")
        print(f"    TN: {tn}  FP: {fp}")
        print(f"    FN: {fn}  TP: {tp}")

        results = {
            'experiment': name,
            'optimizer': optimizer,
            'learning_rate': lr,
            'batch_size': batch_size,
            'dropout': dropout,
            'epochs_trained': epoch + 1,
            'test_accuracy': float(accuracy),
            'test_precision': float(precision),
            'test_recall': float(recall),
            'test_f1': float(f1),
            'confusion_matrix': cm,
            'history': history,
            'timestamp': datetime.now().isoformat(),
        }
    else:
        results = {
            'experiment': name,
            'optimizer': optimizer,
            'learning_rate': lr,
            'batch_size': batch_size,
            'epochs_trained': epoch + 1,
            'history': history,
            'timestamp': datetime.now().isoformat(),
        }

    # Save results
    results_path = PROJECT_ROOT / 'training' / f'{name}_results.json'
    with open(results_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to: {results_path}")

    return results


def compare_optimizers(data_dir, epochs=30, **kwargs):
    """Experiment 3: Compare Adam vs SGD."""
    results = {}
    for opt in ['Adam', 'SGD']:
        print(f"\n{'#' * 60}")
        print(f"# Training with {opt}")
        print(f"{'#' * 60}")
        metrics = train_cnn(
            data_dir, epochs=epochs, optimizer=opt,
            name=f'compare_{opt}', **kwargs
        )
        results[opt] = metrics

    print("\n" + "=" * 60)
    print("Optimizer Comparison Summary")
    print("=" * 60)
    for metric_key, label in [('test_accuracy', 'Accuracy'),
                             ('test_precision', 'Precision'),
                             ('test_recall', 'Recall'),
                             ('test_f1', 'F1-score')]:
        adam_val = results['Adam'].get(metric_key, 0)
        sgd_val = results['SGD'].get(metric_key, 0)
        print(f"{label:<15} Adam: {adam_val:.4f}  SGD: {sgd_val:.4f}")

    comparison_path = PROJECT_ROOT / 'training' / 'cnn_optimizer_comparison.json'
    with open(comparison_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nComparison saved to: {comparison_path}")

    return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Train CNN for EcoSort AI quality classification')
    parser.add_argument('--data', required=True,
                        help='Dataset directory (with train/val/test subdirs)')
    parser.add_argument('--epochs', type=int, default=50)
    parser.add_argument('--batch', type=int, default=32)
    parser.add_argument('--optimizer', default='Adam',
                        choices=['Adam', 'SGD'])
    parser.add_argument('--lr', type=float, default=0.001)
    parser.add_argument('--patience', type=int, default=15)
    parser.add_argument('--dropout', type=float, default=0.5)
    parser.add_argument('--name', default='cnn_quality')
    parser.add_argument('--compare-optimizers', action='store_true')
    args = parser.parse_args()

    if args.compare_optimizers:
        compare_optimizers(args.data, epochs=args.epochs,
                          batch_size=args.batch, lr=args.lr,
                          patience=args.patience, dropout=args.dropout)
    else:
        train_cnn(
            args.data, epochs=args.epochs, batch_size=args.batch,
            optimizer=args.optimizer, lr=args.lr, patience=args.patience,
            dropout=args.dropout, name=args.name,
        )
