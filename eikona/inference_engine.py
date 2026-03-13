"""
eikona/inference_engine.py

Reusable inference engine — no CLI, no argparse.
Used by both the CLI script and the API worker.

Produces the exact same labeled canvas output as the original inference.py.
"""

import os
import io
import torch
from PIL import Image, ImageDraw, ImageFont
import torchvision.transforms as T

from eikona.model import Generator
from eikona.dataset import RAGRetriever, get_transform, denorm


class InferenceEngine:
    """
    Holds a loaded Generator + RAGRetriever and runs inference.

    Thread-safety: NOT thread-safe. Use one engine per worker process.
    """

    def __init__(self, checkpoint_path: str, index_dir: str):
        """
        Args:
            checkpoint_path: Path to a Generator .pth checkpoint.
            index_dir: Directory containing faiss.index and paths.npy.
        """
        if torch.cuda.is_available():
            self.device = torch.device("cuda")
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            self.device = torch.device("mps")
        else:
            self.device = torch.device("cpu")

        # Load generator
        self.G = Generator(in_channels=6, out_channels=3).to(self.device)
        self.G.load_state_dict(torch.load(checkpoint_path, map_location=self.device))
        self.G.eval()

        # Load retriever
        self.retriever = RAGRetriever(index_dir, device=self.device)
        self.transform = get_transform(256)

        self._checkpoint_path = checkpoint_path
        self._index_dir = index_dir

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, input_image: Image.Image) -> Image.Image:
        """
        Run inference on a single PIL Image.

        Args:
            input_image: PIL RGB image (sketch / edge map).

        Returns:
            PIL Image — the labeled canvas with [Input | Reference | Output].
        """
        w, h = input_image.size

        # Handle both side-by-side and standalone input images
        if w > h * 1.5:
            input_pil = input_image.crop((0, 0, w // 2, h))
        else:
            input_pil = input_image

        input_tensor = self.transform(input_pil).unsqueeze(0).to(self.device)

        # Retrieve reference
        retrieved_tensor = self.retriever.retrieve(input_pil).unsqueeze(0).to(self.device)

        # Generate
        with torch.no_grad():
            g_input = torch.cat([input_tensor, retrieved_tensor], dim=1)
            output = self.G(g_input)

        # Build labeled canvas (same as original inference.py)
        to_pil = T.ToPILImage()
        in_p  = to_pil(denorm(input_tensor.squeeze(0).cpu()))
        ref_p = to_pil(denorm(retrieved_tensor.squeeze(0).cpu()))
        out_p = to_pil(denorm(output.squeeze(0).cpu()))

        cw, ch = in_p.size
        label_h = 40
        canvas = Image.new("RGB", (cw * 3, ch + label_h), (255, 255, 255))
        canvas.paste(in_p, (0, 0))
        canvas.paste(ref_p, (cw, 0))
        canvas.paste(out_p, (cw * 2, 0))

        draw = ImageDraw.Draw(canvas)
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 18)
        except Exception:
            font = ImageFont.load_default()

        labels = ["User Input", "Reference (RAG)", "Model Output"]
        for i, text in enumerate(labels):
            if hasattr(draw, "textbbox"):
                bbox = draw.textbbox((0, 0), text, font=font)
                tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            else:
                tw, th = draw.textsize(text, font=font)
            draw.text(
                (i * cw + (cw - tw) // 2, ch + (label_h - th) // 2),
                text,
                fill=(0, 0, 0),
                font=font,
            )

        return canvas

    def run_to_bytes(self, input_image: Image.Image, fmt: str = "PNG") -> bytes:
        """Run inference and return the result as PNG/JPEG bytes."""
        canvas = self.run(input_image)
        buf = io.BytesIO()
        canvas.save(buf, format=fmt)
        buf.seek(0)
        return buf.getvalue()

    def reload_checkpoint(self, checkpoint_path: str):
        """Hot-reload a different checkpoint without restarting."""
        self.G.load_state_dict(torch.load(checkpoint_path, map_location=self.device))
        self.G.eval()
        self._checkpoint_path = checkpoint_path
