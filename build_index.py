"""
build_index.py

Encodes all input images in the dataset using CLIP and stores them in a FAISS index.
Run this ONCE before training or inference.

Usage:
    python build_index.py --data_dir ./data/edges2shoes/train --output_dir ./index
"""

import os
import argparse
import numpy as np
from PIL import Image
from tqdm import tqdm

import torch
import clip
import faiss


def build_index(data_dir, output_dir, batch_size=64):
    os.makedirs(output_dir, exist_ok=True)

    if torch.cuda.is_available():
        device = "cuda"
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        device = "mps"
    else:
        device = "cpu"
    model, preprocess = clip.load("ViT-B/32", device=device)

    # Collect all image paths
    # edges2shoes format: each image is side-by-side (input | target), 256x512
    image_paths = sorted([
        os.path.join(data_dir, f)
        for f in os.listdir(data_dir)
        if f.endswith(('.jpg', '.png'))
    ])

    print(f"Found {len(image_paths)} images.")

    all_embeddings = []
    all_paths = []

    for i in tqdm(range(0, len(image_paths), batch_size), desc="Encoding"):
        batch_paths = image_paths[i:i + batch_size]
        images = []
        valid_paths = []

        for p in batch_paths:
            try:
                img = Image.open(p).convert("RGB")
                w, h = img.size
                # Left half is the input (edge map), right half is target (shoe)
                input_img = img.crop((0, 0, w // 2, h))
                images.append(preprocess(input_img))
                valid_paths.append(p)
            except Exception as e:
                print(f"Skipping {p}: {e}")

        if not images:
            continue

        batch_tensor = torch.stack(images).to(device)
        with torch.no_grad():
            embeddings = model.encode_image(batch_tensor)
            embeddings = embeddings / embeddings.norm(dim=-1, keepdim=True)  # normalize

        all_embeddings.append(embeddings.cpu().numpy().astype(np.float32))
        all_paths.extend(valid_paths)

    all_embeddings = np.vstack(all_embeddings)
    print(f"Embedding matrix: {all_embeddings.shape}")

    # Build FAISS index (cosine similarity via normalized L2)
    dim = all_embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)  # Inner product = cosine sim for normalized vectors
    index.add(all_embeddings)

    # Save index and paths
    faiss.write_index(index, os.path.join(output_dir, "faiss.index"))
    np.save(os.path.join(output_dir, "paths.npy"), np.array(all_paths))
    print(f"Saved index and paths to {output_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_dir",   type=str, default="./data/edges2shoes/train")
    parser.add_argument("--output_dir", type=str, default="./index")
    args = parser.parse_args()
    build_index(args.data_dir, args.output_dir)
