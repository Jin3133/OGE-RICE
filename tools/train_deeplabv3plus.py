"""Train a DeepLabV3+ baseline adapted from the official SMP PyTorch examples."""

from __future__ import annotations

import argparse
import csv
import json
import random
import time
from pathlib import Path
from typing import Any

import numpy as np
import segmentation_models_pytorch as smp
import torch
import yaml
from PIL import Image, ImageDraw
from torch.utils.data import DataLoader
from tqdm import tqdm

from oge_main.data.dataset import FarmSegmentationDataset
from oge_main.data.transforms import TrainingTransform
from oge_main.losses import masked_bce_dice_loss
from oge_main.metrics import BinarySegmentationMetrics
from oge_main.utils.device import select_device


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("configs/deeplabv3plus.yaml"))
    parser.add_argument("--epochs", type=int)
    parser.add_argument("--batch-size", type=int)
    parser.add_argument("--num-workers", type=int)
    parser.add_argument("--encoder")
    parser.add_argument("--encoder-weights")
    parser.add_argument("--resume", type=Path)
    parser.add_argument("--output-directory", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--max-train-batches", type=int)
    parser.add_argument("--max-valid-batches", type=int)
    return parser.parse_args()


def load_configuration(args: argparse.Namespace) -> dict[str, Any]:
    configuration = yaml.safe_load(args.config.read_text())
    overrides = {
        ("training", "epochs"): args.epochs,
        ("training", "batch_size"): args.batch_size,
        ("training", "num_workers"): args.num_workers,
        ("model", "encoder"): args.encoder,
        ("model", "encoder_weights"): args.encoder_weights,
    }
    for (section, key), value in overrides.items():
        if value is not None:
            configuration[section][key] = (
                None if isinstance(value, str) and value.lower() == "none" else value
            )
    return configuration


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def make_loaders(configuration: dict[str, Any]) -> tuple[DataLoader, DataLoader]:
    data = configuration["data"]
    training = configuration["training"]
    common = {
        "split_file": data["split_file"],
        "statistics_file": data["statistics_file"],
        "root": data.get("dataset_root"),
    }
    train_dataset = FarmSegmentationDataset(
        "train", transform=TrainingTransform(), **common
    )
    validation_dataset = FarmSegmentationDataset("validation", **common)
    loader_common = {
        "batch_size": training["batch_size"],
        "num_workers": training["num_workers"],
        "pin_memory": torch.cuda.is_available(),
    }
    return (
        DataLoader(train_dataset, shuffle=True, drop_last=True, **loader_common),
        DataLoader(validation_dataset, shuffle=False, drop_last=False, **loader_common),
    )


def run_epoch(
    model: torch.nn.Module,
    loader: DataLoader,
    device: torch.device,
    optimizer: torch.optim.Optimizer | None,
    threshold: float,
    bce_weight: float,
    gradient_clip_norm: float,
    max_batches: int | None,
) -> dict[str, float]:
    training = optimizer is not None
    model.train(training)
    metrics = BinarySegmentationMetrics(threshold=threshold)
    loss_sum = 0.0
    batch_count = 0
    context = torch.enable_grad() if training else torch.inference_mode()
    with context:
        for batch_index, batch in enumerate(
            tqdm(loader, desc="train" if training else "valid", leave=False)
        ):
            if max_batches is not None and batch_index >= max_batches:
                break
            images = batch["image"].to(device)
            masks = batch["mask"].to(device)
            valid_masks = batch["valid_mask"].to(device)
            if training:
                optimizer.zero_grad(set_to_none=True)
            logits = model(images)
            loss = masked_bce_dice_loss(logits, masks, valid_masks, bce_weight=bce_weight)
            if training:
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), gradient_clip_norm)
                optimizer.step()
            loss_sum += float(loss.detach().cpu())
            batch_count += 1
            metrics.update(logits.detach(), masks, valid_masks)
    if not batch_count:
        raise RuntimeError("No batches were processed")
    return {"loss": loss_sum / batch_count, **metrics.compute()}


def stretch(image: np.ndarray) -> np.ndarray:
    output = np.zeros_like(image, dtype=np.uint8)
    for channel in range(3):
        low, high = np.percentile(image[channel], (2, 98))
        output[channel] = (
            np.clip((image[channel] - low) / max(high - low, 1e-6), 0, 1) * 255
        ).astype(np.uint8)
    return np.moveaxis(output, 0, -1)


def save_prediction_preview(
    model: torch.nn.Module,
    loader: DataLoader,
    device: torch.device,
    output: Path,
    mean: np.ndarray,
    std: np.ndarray,
) -> None:
    batch = next(iter(loader))
    images = batch["image"].to(device)
    with torch.inference_mode():
        predictions = torch.sigmoid(model(images))[:, 0].cpu().numpy() >= 0.5
    image = images[0].cpu().numpy() * std[:, None, None] + mean[:, None, None]
    rgb = stretch(image)
    target = batch["mask"][0].numpy().astype(bool)
    prediction = predictions[0]
    target_overlay = rgb.copy()
    prediction_overlay = rgb.copy()
    target_overlay[target] = (
        0.55 * target_overlay[target] + 0.45 * np.array([255, 32, 32])
    ).astype(np.uint8)
    prediction_overlay[prediction] = (
        0.55 * prediction_overlay[prediction] + 0.45 * np.array([32, 255, 32])
    ).astype(np.uint8)
    canvas = Image.new("RGB", (512 * 3, 536), "white")
    draw = ImageDraw.Draw(canvas)
    for index, (title, array) in enumerate(
        (("input", rgb), ("label", target_overlay), ("prediction", prediction_overlay))
    ):
        canvas.paste(Image.fromarray(array), (512 * index, 24))
        draw.text((512 * index + 4, 4), title, fill="black")
    canvas.save(output)


def append_history(path: Path, row: dict[str, object]) -> None:
    exists = path.exists()
    with path.open("a", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(row))
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def main() -> None:
    args = parse_arguments()
    configuration = load_configuration(args)
    if args.output_directory is not None:
        configuration["output"]["directory"] = str(args.output_directory)
    seed_everything(int(configuration["experiment"]["seed"]))
    device = select_device()
    print(f"device={device}")
    if int(configuration["training"]["batch_size"]) < 2:
        raise ValueError("DeepLabV3+ training requires batch_size >= 2 because of ASPP BatchNorm")
    train_loader, validation_loader = make_loaders(configuration)

    model_config = configuration["model"]
    model = smp.DeepLabV3Plus(
        encoder_name=model_config["encoder"],
        encoder_weights=model_config.get("encoder_weights"),
        in_channels=3,
        classes=1,
    ).to(device)
    training = configuration["training"]
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=float(training["learning_rate"]),
        weight_decay=float(training["weight_decay"]),
    )
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer,
        T_max=int(training["epochs"]),
        eta_min=float(training.get("eta_min", 1e-6)),
    )
    output = Path(configuration["output"]["directory"])
    history_path = output / "history.csv"
    if history_path.exists() and args.resume is None and not args.overwrite:
        raise FileExistsError(
            f"{history_path} already exists. Use --resume, --overwrite, or another output directory."
        )
    output.mkdir(parents=True, exist_ok=True)
    if args.overwrite and history_path.exists():
        history_path.unlink()
    (output / "configuration.json").write_text(
        json.dumps(configuration, ensure_ascii=False, indent=2) + "\n"
    )
    start_epoch = 1
    best_iou = -1.0
    patience = 0
    if args.resume:
        checkpoint = torch.load(args.resume, map_location=device, weights_only=False)
        model.load_state_dict(checkpoint["model"])
        optimizer.load_state_dict(checkpoint["optimizer"])
        scheduler.load_state_dict(checkpoint["scheduler"])
        start_epoch = int(checkpoint["epoch"]) + 1
        best_iou = float(checkpoint["best_iou"])

    statistics = json.loads(Path(configuration["data"]["statistics_file"]).read_text())
    mean = np.asarray(statistics["mean"], dtype=np.float32)
    std = np.asarray(statistics["std"], dtype=np.float32)
    for epoch in range(start_epoch, int(training["epochs"]) + 1):
        started = time.time()
        train_metrics = run_epoch(
            model,
            train_loader,
            device,
            optimizer,
            float(training.get("threshold", 0.5)),
            float(training.get("bce_weight", 0.5)),
            float(training.get("gradient_clip_norm", 1.0)),
            args.max_train_batches,
        )
        validation_metrics = run_epoch(
            model,
            validation_loader,
            device,
            None,
            float(training.get("threshold", 0.5)),
            float(training.get("bce_weight", 0.5)),
            float(training.get("gradient_clip_norm", 1.0)),
            args.max_valid_batches,
        )
        scheduler.step()
        row: dict[str, object] = {
            "epoch": epoch,
            "learning_rate": optimizer.param_groups[0]["lr"],
            "seconds": round(time.time() - started, 2),
            **{f"train_{key}": value for key, value in train_metrics.items()},
            **{f"valid_{key}": value for key, value in validation_metrics.items()},
        }
        append_history(history_path, row)
        print(json.dumps(row, ensure_ascii=False))
        checkpoint = {
            "epoch": epoch,
            "model": model.state_dict(),
            "optimizer": optimizer.state_dict(),
            "scheduler": scheduler.state_dict(),
            "best_iou": max(best_iou, validation_metrics["iou"]),
            "configuration": configuration,
        }
        torch.save(checkpoint, output / "latest.pt")
        if validation_metrics["iou"] > best_iou:
            best_iou = validation_metrics["iou"]
            patience = 0
            torch.save(checkpoint, output / "best.pt")
        else:
            patience += 1
        if epoch == 1 or epoch % int(training.get("visualization_interval", 5)) == 0:
            save_prediction_preview(
                model,
                validation_loader,
                device,
                output / f"preview_epoch_{epoch:03d}.jpg",
                mean,
                std,
            )
        if patience >= int(training["early_stopping_patience"]):
            print(f"early stopping after {patience} epochs without IoU improvement")
            break


if __name__ == "__main__":
    main()
