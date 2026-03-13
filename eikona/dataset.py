"""
eikona/dataset.py

Dataset class for edges2shoes (or any side-by-side Pix2Pix dataset).
Also contains the RAGRetriever that fetches similar images from FAISS.
"""

import os
import numpy as np
from PIL import Image

import torch
from torch.utils.data import Dataset
import torchvision.transforms as T

import clip
import faiss


# ---------------------------------------------------------------------------
# Transforms
# ---------------------------------------------------------------------------

def get_transform(size=256):
    return T.Compose([
        T.Resize((size, size)),
        T.ToTensor(),
        T.Normalize([0.5] * 3, [0.5] * 3),  # [-1, 1]
    ])


def denorm(tensor):
    """Convert [-1,1] tensor back to [0,1] for visualization."""
    return (tensor * 0.5 + 0.5).clamp(0, 1)


# ---------------------------------------------------------------------------
# RAG Retriever
# ---------------------------------------------------------------------------

class RAGRetriever:
    """
    Given a query image, returns the most similar image from the training set
    using CLIP embeddings + FAISS.
    """
    def __init__(self, index_dir, device="cpu"):
        self.device = device
        self.clip_model, self.clip_preprocess = clip.load("ViT-B/32", device=device)
        self.clip_model.eval()

        self.index = faiss.read_index(os.path.join(index_dir, "faiss.index"))
        self.paths = np.load(os.path.join(index_dir, "paths.npy"), allow_pickle=True)
        self.transform = get_transform()

    @torch.no_grad()
    def retrieve(self, pil_image, k=1, exclude_path=None):
        """
        Args:
            pil_image: PIL Image (input/edge image)
            k: number of neighbors to retrieve
            exclude_path: path to exclude (avoid retrieving itself during training)
        Returns:
            retrieved_tensor: (3, H, W) normalized tensor of retrieved image's INPUT side
        """
        clip_input = self.clip_preprocess(pil_image).unsqueeze(0).to(self.device)
        emb = self.clip_model.encode_image(clip_input)
        emb = emb / emb.norm(dim=-1, keepdim=True)
        emb_np = emb.cpu().numpy().astype(np.float32)

        # Search top k+1 to allow exclusion
        D, I = self.index.search(emb_np, k + 1)

        for idx in I[0]:
            path = self.paths[idx]
            if exclude_path and os.path.abspath(path) == os.path.abspath(exclude_path):
                continue
            # Load the retrieved image's target side (the shoe, for style/appearance hint)
            img = Image.open(path).convert("RGB")
            w, h = img.size
            target_half = img.crop((w // 2, 0, w, h))
            return self.transform(target_half)

        # Fallback: return first result (target side)
        img = Image.open(self.paths[I[0][0]]).convert("RGB")
        w, h = img.size
        return self.transform(img.crop((w // 2, 0, w, h)))


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------

class Pix2PixDataset(Dataset):
    """
    Loads side-by-side Pix2Pix images (input | target).
    Optionally fetches a retrieved reference via RAGRetriever.
    """
    def __init__(self, data_dir, index_dir=None, size=256, use_rag=True):
        self.data_dir = data_dir
        self.size = size
        self.use_rag = use_rag
        self.transform = get_transform(size)

        self.image_paths = sorted([
            os.path.join(data_dir, f)
            for f in os.listdir(data_dir)
            if f.endswith(('.jpg', '.png'))
        ])

        self.retriever = None
        if use_rag and index_dir:
            if torch.cuda.is_available():
                device = "cuda"
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                device = "mps"
            else:
                device = "cpu"
            self.retriever = RAGRetriever(index_dir, device=device)

        print(f"Dataset: {len(self.image_paths)} images | RAG: {use_rag and self.retriever is not None}")

    def __len__(self):
        return len(self.image_paths)

    def __getitem__(self, idx):
        path = self.image_paths[idx]
        img = Image.open(path).convert("RGB")
        w, h = img.size

        input_pil  = img.crop((0, 0, w // 2, h))   # edge / sketch
        target_pil = img.crop((w // 2, 0, w, h))   # real image

        input_tensor  = self.transform(input_pil)
        target_tensor = self.transform(target_pil)

        if self.retriever is not None:
            retrieved_tensor = self.retriever.retrieve(input_pil, exclude_path=path)
        else:
            # No RAG: use zeros as placeholder (baseline mode)
            retrieved_tensor = torch.zeros_like(input_tensor)

        return {
            "input":     input_tensor,      # (3, H, W)
            "target":    target_tensor,     # (3, H, W)
            "retrieved": retrieved_tensor,  # (3, H, W)
            "path":      path,
        }
