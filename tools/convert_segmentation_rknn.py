#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert an ONNX segmentation model to RKNN for RK3588/RK3588S.")
    parser.add_argument("--onnx", type=Path, default=Path("data/segmentation/model.onnx"))
    parser.add_argument("--out", type=Path, default=Path("data/segmentation/model.rknn"))
    parser.add_argument("--labels", type=Path, default=Path("data/segmentation/labels.json"))
    parser.add_argument("--target", default="rk3588")
    parser.add_argument("--dataset", type=Path, help="Optional RKNN quantization dataset text file.")
    parser.add_argument("--quantized", action="store_true", help="Enable int8 quantization. Requires --dataset.")
    parser.add_argument("--mean", default="123.675,116.28,103.53", help="RGB mean values used during preprocessing.")
    parser.add_argument("--std", default="58.395,57.12,57.375", help="RGB std values used during preprocessing.")
    return parser.parse_args()


def parse_floats(value: str) -> list[float]:
    return [float(part.strip()) for part in value.split(",") if part.strip()]


def main() -> None:
    args = parse_args()
    if not args.onnx.exists():
        raise SystemExit(f"Missing ONNX model: {args.onnx}")
    if args.quantized and not args.dataset:
        raise SystemExit("--quantized requires --dataset")
    if args.dataset and not args.dataset.exists():
        raise SystemExit(f"Missing quantization dataset: {args.dataset}")

    try:
        from rknn.api import RKNN
    except Exception as exc:
        raise SystemExit(f"rknn-toolkit2 is required for conversion: {exc}") from exc

    args.out.parent.mkdir(parents=True, exist_ok=True)
    rknn = RKNN(verbose=True)
    try:
        ret = rknn.config(
            target_platform=args.target,
            mean_values=[parse_floats(args.mean)],
            std_values=[parse_floats(args.std)],
        )
        if ret != 0:
            raise SystemExit("RKNN config failed")
        ret = rknn.load_onnx(model=str(args.onnx))
        if ret != 0:
            raise SystemExit("RKNN load_onnx failed")
        ret = rknn.build(do_quantization=bool(args.quantized), dataset=str(args.dataset) if args.dataset else None)
        if ret != 0:
            raise SystemExit("RKNN build failed")
        ret = rknn.export_rknn(str(args.out))
        if ret != 0:
            raise SystemExit("RKNN export failed")
    finally:
        rknn.release()

    if args.labels.exists():
        labels = json.loads(args.labels.read_text(encoding="utf-8"))
        args.labels.write_text(json.dumps(labels, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
