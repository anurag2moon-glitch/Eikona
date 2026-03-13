# Eikona — RAG-Guided Pix2Pix Image-to-Image Translation

## How it works

```
Input Image (edge/sketch)
        ↓
CLIP Encoder → query embedding
        ↓
FAISS index → retrieve most similar training image
        ↓
Concatenate [input (3ch) + retrieved (3ch)] → 6-channel input
        ↓
U-Net Generator → translated output image
```

The RAG component: instead of translating from input alone, the generator
is conditioned on a retrieved reference image, giving it a style/appearance
hint from the training database.

---

## Project Structure

```
eikona/
├── eikona/                    # Core ML package
│   ├── model.py               #   U-Net Generator + PatchGAN Discriminator
│   ├── dataset.py             #   Dataset class + RAGRetriever (CLIP + FAISS)
│   └── inference_engine.py    #   Reusable inference engine
│
├── api/                       # FastAPI REST API
│   ├── main.py                #   Routes & CORS
│   ├── schemas.py             #   Pydantic request/response models
│   └── config.py              #   Settings (env vars)
│
├── worker/                    # Background inference worker
│   ├── queue.py               #   File-based job queue (FIFO)
│   └── consumer.py            #   Worker loop (1 job at a time)
│
├── scripts/
│   ├── build_index.py         # Build FAISS index (run once)
│   └── download_dataset.sh    # Download edges2shoes dataset
│
├── train.py                   # Training loop
├── inference.py               # CLI inference
├── start.py                   # 🚀 Single command: API + Worker
├── requirements.txt
├── API_DOCS.md                # Full API documentation
└── README.md
```

---

## Setup

```bash
pip install -r requirements.txt
```

> If on GPU: install faiss-gpu instead of faiss-cpu

---

## Dataset

Download edges2shoes:
```bash
bash ./scripts/download_dataset.sh edges2shoes
```

Or manually from: http://efrosgans.eecs.berkeley.edu/pix2pix/datasets/edges2shoes.tar.gz

Extract to: `./data/edges2shoes/`

---

## Step 1: Build FAISS Index

```bash
python scripts/build_index.py --data_dir ./data/edges2shoes/train --output_dir ./index
```

This encodes all training images with CLIP and builds a searchable index.
Run once, takes ~5 minutes on CPU.

---

## Step 2: Train

```bash
python train.py \
  --data_dir ./data/edges2shoes/train \
  --index_dir ./index \
  --epochs 50 \
  --batch_size 4
```

Samples saved to `./samples/` every epoch (rows: input | retrieved | fake | real).
Checkpoints saved to `./checkpoints/` every epoch.

**Quick smoke test (1 epoch):**
```bash
python train.py --epochs 1 --batch_size 2
```

---

## Step 3: Run the API

### Single command — starts both API server and inference worker:

```bash
python start.py
```

This gives you:
- **API** at `http://localhost:8000`
- **Swagger UI** at `http://localhost:8000/docs`
- **ReDoc** at `http://localhost:8000/redoc`
- **Worker** processing inference jobs in the background

### Options

```bash
python start.py --port 9000         # Custom port
python start.py --api-only          # Only API server
python start.py --workers-only      # Only worker
python start.py --reload            # Dev mode with auto-reload
```

### API Usage (Quick)

```bash
# Submit an image for inference
curl -X POST http://localhost:8000/api/v1/generate \
  -F "image=@./my_sketch.png"
# → { "job_id": "abc-123", "status": "queued" }

# Check job status
curl http://localhost:8000/api/v1/jobs/abc-123
# → { "status": "completed", "result_url": "/api/v1/jobs/abc-123/result" }

# Download result
curl http://localhost:8000/api/v1/jobs/abc-123/result -o result.png
```

📖 **Full API documentation:** [API_DOCS.md](./API_DOCS.md)

---

## CLI Inference (still works)

```bash
python inference.py \
  --input ./data/edges2shoes/val \
  --checkpoint ./checkpoints/G_epoch50.pth \
  --index_dir ./index \
  --output_dir ./outputs
```

Output images show: `[input | retrieved reference | generated output]` side by side.

---

## Key Design Choices

| Component | Choice | Why |
|-----------|--------|-----|
| Retrieval | CLIP ViT-B/32 + FAISS | Fast, pretrained, no fine-tuning needed |
| Generator | U-Net with skip connections | Preserves spatial structure |
| Discriminator | 70x70 PatchGAN | Sharper local textures |
| RAG fusion | Early (channel concat) | Simple, effective, easy to implement |
| Loss | BCE + L1 (λ=100) | Standard Pix2Pix formulation |
| API | FastAPI | Auto-docs, async, type-safe |
| Queue | File-based FIFO | Zero dependencies, crash-resilient |
| Worker | Single-process | GPU safety, predictable resource usage |
