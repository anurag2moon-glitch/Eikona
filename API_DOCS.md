# Eikona API Documentation

> **Base URL:** `http://localhost:8000`
> **Interactive Docs:** [Swagger UI](http://localhost:8000/docs) · [ReDoc](http://localhost:8000/redoc)

---

## Overview

The Eikona API provides a RESTful interface for RAG-guided image-to-image translation.
Upload a sketch or edge map, and the system returns a photorealistic translation
using retrieval-augmented generation (CLIP + FAISS + U-Net Generator).

### Architecture

```
Frontend → POST /api/v1/generate (upload image)
        ← 202 { job_id }

Frontend → GET /api/v1/jobs/{job_id} (poll)
        ← 200 { status: "processing" }

Frontend → GET /api/v1/jobs/{job_id} (poll again)
        ← 200 { status: "completed", result_url: "/api/v1/jobs/{job_id}/result" }

Frontend → GET /api/v1/jobs/{job_id}/result
        ← 200 (PNG image)
```

Jobs are processed **one at a time** (FIFO queue). This ensures GPU safety
and predictable resource usage.

---

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Start API + Worker with a single command
python start.py

# Or customize:
python start.py --port 9000
python start.py --api-only      # Just the API
python start.py --workers-only  # Just the worker
```

---

## Endpoints

### 🟢 `GET /health`

Health check — verify the server is running.

**Response** `200 OK`
```json
{
  "status": "ok",
  "version": "0.1.0",
  "checkpoint": "./checkpoints/G_epoch1.pth",
  "device": "auto",
  "queue_depth": 0
}
```

---

### 🟣 `POST /api/v1/generate`

Submit an inference job. The image is queued and processed by the background worker.

**Request**
- Content-Type: `multipart/form-data`
- Body:
  | Field | Type | Required | Description |
  |-------|------|----------|-------------|
  | `image` | file | ✅ | Input sketch/edge image (JPEG, PNG, or WebP) |
  | `checkpoint` | string | ❌ | Optional checkpoint path override |

**cURL Example**
```bash
curl -X POST http://localhost:8000/api/v1/generate \
  -F "image=@./my_sketch.png"
```

**JavaScript (fetch)**
```javascript
const formData = new FormData();
formData.append('image', fileInput.files[0]);

const response = await fetch('http://localhost:8000/api/v1/generate', {
  method: 'POST',
  body: formData,
});
const { job_id } = await response.json();
```

**Response** `202 Accepted`
```json
{
  "job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "queued",
  "message": "Job submitted successfully."
}
```

---

### 🔵 `GET /api/v1/jobs/{job_id}`

Poll the status of a submitted job.

**Path Parameters**
| Parameter | Type | Description |
|-----------|------|-------------|
| `job_id` | string | The UUID returned by `/generate` |

**Response** `200 OK`
```json
{
  "job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "completed",
  "created_at": "2026-03-14T00:15:00Z",
  "started_at": "2026-03-14T00:15:01Z",
  "completed_at": "2026-03-14T00:15:05Z",
  "error": null,
  "result_url": "/api/v1/jobs/a1b2c3d4-e5f6-7890-abcd-ef1234567890/result"
}
```

**Status Flow:**
```
queued → processing → completed
                    → failed (with error message)
```

---

### 🟡 `GET /api/v1/jobs/{job_id}/result`

Download the generated result image (PNG).

**Response** `200 OK` — `image/png` binary data

**Error Responses**
| Code | Meaning |
|------|---------|
| 404 | Job not found |
| 409 | Job not yet completed |

**JavaScript Example**
```javascript
// Poll until complete, then show result
async function waitForResult(jobId) {
  while (true) {
    const res = await fetch(`http://localhost:8000/api/v1/jobs/${jobId}`);
    const data = await res.json();

    if (data.status === 'completed') {
      // Display the result image
      const img = document.createElement('img');
      img.src = `http://localhost:8000/api/v1/jobs/${jobId}/result`;
      document.body.appendChild(img);
      return;
    }

    if (data.status === 'failed') {
      throw new Error(data.error);
    }

    // Wait 1 second before polling again
    await new Promise(r => setTimeout(r, 1000));
  }
}
```

---

### 🟠 `GET /api/v1/queue`

Get queue statistics.

**Response** `200 OK`
```json
{
  "pending": 2,
  "processing": 1,
  "completed": 15,
  "failed": 0
}
```

---

### 🔴 `GET /api/v1/checkpoints`

List all available `.pth` checkpoint files.

**Response** `200 OK`
```json
{
  "checkpoints": [
    {
      "name": "G_epoch1.pth",
      "path": "/path/to/checkpoints/G_epoch1.pth",
      "size_mb": 207.7
    },
    {
      "name": "G_demo.pth",
      "path": "/path/to/checkpoints/G_demo.pth",
      "size_mb": 207.7
    }
  ]
}
```

---

### ⚪ `POST /api/v1/reload`

Hot-reload a different checkpoint. Takes effect on the next processed job.

**Query Parameters**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `checkpoint` | string | ✅ | Path to the `.pth` file |

**cURL Example**
```bash
curl -X POST "http://localhost:8000/api/v1/reload?checkpoint=./checkpoints/G_epoch50.pth"
```

**Response** `200 OK`
```json
{
  "message": "Checkpoint reload scheduled.",
  "checkpoint": "./checkpoints/G_epoch50.pth"
}
```

---

## Frontend Integration Guide

### Complete React Example

```jsx
import { useState } from 'react';

const API = 'http://localhost:8000';

function EikonaGenerator() {
  const [file, setFile] = useState(null);
  const [status, setStatus] = useState('idle');
  const [resultUrl, setResultUrl] = useState(null);

  const handleSubmit = async () => {
    if (!file) return;

    // 1. Submit the job
    setStatus('uploading');
    const formData = new FormData();
    formData.append('image', file);

    const submitRes = await fetch(`${API}/api/v1/generate`, {
      method: 'POST',
      body: formData,
    });
    const { job_id } = await submitRes.json();

    // 2. Poll for completion
    setStatus('processing');
    while (true) {
      const pollRes = await fetch(`${API}/api/v1/jobs/${job_id}`);
      const job = await pollRes.json();

      if (job.status === 'completed') {
        setResultUrl(`${API}/api/v1/jobs/${job_id}/result`);
        setStatus('done');
        return;
      }
      if (job.status === 'failed') {
        setStatus('error');
        alert(`Error: ${job.error}`);
        return;
      }

      await new Promise(r => setTimeout(r, 1000));
    }
  };

  return (
    <div>
      <input type="file" onChange={e => setFile(e.target.files[0])} />
      <button onClick={handleSubmit} disabled={!file || status === 'processing'}>
        {status === 'processing' ? 'Processing...' : 'Generate'}
      </button>
      {resultUrl && <img src={resultUrl} alt="Result" />}
    </div>
  );
}
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `EIKONA_CHECKPOINT` | `./checkpoints/G_epoch1.pth` | Default checkpoint path |
| `EIKONA_INDEX_DIR` | `./index` | FAISS index directory |
| `EIKONA_OUTPUT_DIR` | `./outputs` | Output directory |
| `EIKONA_JOBS_DIR` | `./jobs` | Job storage directory |
| `EIKONA_HOST` | `0.0.0.0` | API bind host |
| `EIKONA_PORT` | `8000` | API port |
| `EIKONA_WORKER_POLL` | `0.5` | Worker poll interval (seconds) |

---

## Error Handling

All errors follow a consistent format:
```json
{
  "detail": "Human-readable error message"
}
```

| HTTP Code | Meaning |
|-----------|---------|
| 202 | Job accepted (async) |
| 400 | Bad request (invalid image format) |
| 404 | Resource not found |
| 409 | Conflict (e.g., job not yet completed) |
| 422 | Validation error |
| 500 | Internal server error |
