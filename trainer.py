from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Callable

from model_runtime import DEFAULT_LABELS, IMAGE_SIZE


MetricCallback = Callable[[dict], None]


def train_profile(
    profile_dir: Path,
    epochs: int = 16,
    batch_size: int = 16,
    on_metric: MetricCallback | None = None,
) -> Path:
    import tensorflow as tf

    tf.config.set_visible_devices([], "GPU")
    profile_dir = Path(profile_dir)
    train_dir = profile_dir / "images" / "train"
    valid_dir = profile_dir / "images" / "valid"
    model_dir = profile_dir / "models" / "latest"
    saved_model_dir = model_dir / "saved_model"
    labels = [p.name for p in sorted(train_dir.iterdir()) if p.is_dir()]
    labels = [label for label in labels if any((train_dir / label).glob("*"))]
    if not labels:
        labels = list(DEFAULT_LABELS)
    if len(labels) < 2:
        raise RuntimeError("At least two classes with training images are required")

    train_ds = tf.keras.utils.image_dataset_from_directory(
        train_dir,
        labels="inferred",
        label_mode="categorical",
        class_names=labels,
        image_size=IMAGE_SIZE,
        batch_size=batch_size,
        shuffle=True,
    )
    valid_ds = tf.keras.utils.image_dataset_from_directory(
        valid_dir,
        labels="inferred",
        label_mode="categorical",
        class_names=labels,
        image_size=IMAGE_SIZE,
        batch_size=batch_size,
        shuffle=False,
    )
    augmentation = tf.keras.Sequential(
        [
            tf.keras.layers.RandomFlip("horizontal"),
            tf.keras.layers.RandomRotation(0.03, fill_mode="nearest"),
            tf.keras.layers.RandomZoom(0.08, fill_mode="nearest"),
        ],
        name="training_augmentation",
    )

    train_ds = train_ds.map(
        lambda x, y: (augmentation(tf.cast(x, tf.float32) / 255.0, training=True), y),
        num_parallel_calls=tf.data.AUTOTUNE,
    ).prefetch(tf.data.AUTOTUNE)
    valid_ds = valid_ds.map(
        lambda x, y: (tf.cast(x, tf.float32) / 255.0, y),
        num_parallel_calls=tf.data.AUTOTUNE,
    ).prefetch(tf.data.AUTOTUNE)

    inputs = tf.keras.layers.Input(shape=IMAGE_SIZE + (3,))
    x = tf.keras.layers.Rescaling(2.0, offset=-1.0)(inputs)
    base_model = tf.keras.applications.MobileNetV2(
        input_shape=IMAGE_SIZE + (3,),
        include_top=False,
        weights="imagenet",
    )
    base_model.trainable = False
    x = base_model(x, training=False)
    x = tf.keras.layers.GlobalAveragePooling2D()(x)
    x = tf.keras.layers.Dropout(0.25)(x)
    outputs = tf.keras.layers.Dense(len(labels))(x)
    model = tf.keras.Model(inputs, outputs)
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=0.0003),
        loss=tf.keras.losses.CategoricalCrossentropy(from_logits=True, label_smoothing=0.05),
        metrics=["accuracy"],
    )

    class LiveMetrics(tf.keras.callbacks.Callback):
        def on_epoch_end(self, epoch, logs=None):
            logs = logs or {}
            payload = {
                "type": "metric",
                "epoch": int(epoch + 1),
                "epochs": int(epochs),
                "loss": float(logs.get("loss", 0.0)),
                "accuracy": float(logs.get("accuracy", 0.0)),
                "val_loss": float(logs.get("val_loss", 0.0)),
                "val_accuracy": float(logs.get("val_accuracy", 0.0)),
                "time": time.time(),
            }
            if on_metric:
                on_metric(payload)

    if on_metric:
        on_metric({
            "type": "started",
            "epochs": epochs,
            "labels": labels,
            "architecture": "mobilenet_v2_imagenet",
            "time": time.time(),
        })
    model.fit(
        train_ds,
        validation_data=valid_ds,
        epochs=epochs,
        callbacks=[
            LiveMetrics(),
            tf.keras.callbacks.EarlyStopping(
                monitor="val_loss",
                patience=4,
                restore_best_weights=True,
            ),
        ],
        verbose=0,
    )

    model_dir.mkdir(parents=True, exist_ok=True)
    if hasattr(model, "export"):
        model.export(saved_model_dir)
    else:
        model.save(saved_model_dir, include_optimizer=False)
    converter = tf.lite.TFLiteConverter.from_saved_model(str(saved_model_dir))
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    tflite_model = converter.convert()
    (model_dir / "model.tflite").write_bytes(tflite_model)
    (model_dir / "labels.json").write_text(json.dumps(labels, indent=2), encoding="utf-8")
    if on_metric:
        on_metric({"type": "finished", "model_dir": str(model_dir), "labels": labels, "time": time.time()})
    return model_dir
