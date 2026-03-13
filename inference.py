"""
inference.py

CLI for running inference — now uses the shared InferenceEngine.

Usage:
    python inference.py --input ./test_img.jpg --checkpoint ./checkpoints/G_epoch50.pth --index_dir ./index
"""

import os
import argparse
from PIL import Image

from eikona.inference_engine import InferenceEngine


def run_inference(args):
    engine = InferenceEngine(
        checkpoint_path=args.checkpoint,
        index_dir=args.index_dir,
    )

    os.makedirs(args.output_dir, exist_ok=True)

    # Collect input images
    if os.path.isdir(args.input):
        paths = [
            os.path.join(args.input, f)
            for f in os.listdir(args.input)
            if f.endswith((".jpg", ".png"))
        ]
    else:
        paths = [args.input]

    print(f"Running inference on {len(paths)} image(s)...")

    for path in paths:
        img = Image.open(path).convert("RGB")
        canvas = engine.run(img)

        base_name = os.path.splitext(os.path.basename(path))[0]
        fname = f"{base_name}_result.png"
        canvas.save(os.path.join(args.output_dir, fname))
        print(f"Saved: {fname}")

    print(f"Done. Results in {args.output_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input",      type=str, required=True,  help="Input image or folder")
    parser.add_argument("--checkpoint", type=str, required=True,  help="Path to G checkpoint (.pth)")
    parser.add_argument("--index_dir",  type=str, default="./index")
    parser.add_argument("--output_dir", type=str, default="./outputs")
    args = parser.parse_args()
    run_inference(args)
