"""MessyDesk API for UVDoc (https://github.com/tanguymagne/UVDoc): dewarps photographed document
pages, removing perspective and page curl.

POST /process takes a `message` (task `dewarp`) and, in HTTP mode, the image as `content`; in disk
mode the image is read from message.file.path (see md_storage.py). /config, /help and /health come
from md_service.py.
"""
import json
import os
import threading
import uuid
from typing import Optional

import cv2
import numpy as np
import torch
from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse

import md_service
import md_storage
from utils import IMG_SIZE, bilinear_unwarping, load_model

app = FastAPI(title="MD-UVDoc", description="UVDoc document unwarping for MessyDesk")

UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "output"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

CKPT_PATH = os.getenv("UVDOC_MODEL", "./model/best_model.pkl")
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
_model = None
_model_lock = threading.Lock()


def get_model():
    """The model, loaded on first use so that /health and /config answer at once."""
    global _model
    with _model_lock:
        if _model is None:
            print(f"loading model {CKPT_PATH} on {device}")
            model = load_model(CKPT_PATH, device)
            model.to(device)
            model.eval()
            _model = model
    return _model


def unwarp_img(img_path: str) -> np.ndarray:
    """The dewarped image (BGR) of a document photo."""
    img = cv2.imread(img_path)
    if img is None:
        raise HTTPException(status_code=400, detail="The input is not an image OpenCV can read")
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32) / 255
    inp = torch.from_numpy(cv2.resize(img, IMG_SIZE).transpose(2, 0, 1)).unsqueeze(0).to(device)
    with torch.no_grad():
        point_positions2D, _ = get_model()(inp)
        size = img.shape[:2][::-1]
        unwarped = bilinear_unwarping(
            warped_img=torch.from_numpy(img.transpose(2, 0, 1)).unsqueeze(0).to(device),
            point_positions=torch.unsqueeze(point_positions2D[0], dim=0),
            img_size=tuple(size),
        )
    unwarped = (unwarped[0].cpu().numpy().transpose(1, 2, 0) * 255).astype(np.uint8)
    return cv2.cvtColor(unwarped, cv2.COLOR_RGB2BGR)


def output_extension(name: str) -> str:
    """PNG stays PNG (lossless); other images become JPEG."""
    return "png" if str(name or "").lower().endswith(".png") else "jpg"


def dewarp(image_path: str, output_path: str) -> None:
    if not cv2.imwrite(output_path, unwarp_img(image_path)):
        raise RuntimeError(f"could not write {output_path}")


@app.get("/")
async def root():
    return {"message": "UVDoc API for MessyDesk"}


@app.post("/process")
async def process_files(
    message: Optional[UploadFile] = File(None),
    # MessyDesk sends the task as "message"; "request" is the old name, still accepted
    request: Optional[UploadFile] = File(None),
    content: Optional[UploadFile] = File(None),
):
    message = message or request
    if message is None:
        raise HTTPException(status_code=400, detail="message is required")
    try:
        msg = json.loads((await message.read()).decode("utf-8"))
        if isinstance(msg, str):
            msg = json.loads(msg)
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid message: {e}")
    task_id = (msg.get("task") or {}).get("id")
    if task_id != "dewarp":
        raise HTTPException(status_code=400, detail=f"Unsupported task: {task_id}")

    output_id = uuid.uuid4().hex
    upload_path = None
    try:
        if content is not None:
            extension = output_extension(content.filename)
            upload_path = os.path.join(UPLOAD_FOLDER, output_id + os.path.splitext(content.filename or "")[1])
            with open(upload_path, "wb") as f:
                f.write(await content.read())
            image_path = upload_path
        else:
            image_path = str(md_storage.message_input_path(msg))
            extension = output_extension(image_path)
        output_path = os.path.join(OUTPUT_FOLDER, f"{output_id}.{extension}")
        # the model is CPU/GPU-bound - keep it off the event loop
        await run_in_threadpool(dewarp, image_path, output_path)
    except md_storage.StorageError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {e}")
    finally:
        if upload_path:
            try:
                os.remove(upload_path)
            except OSError:
                pass

    # <source label>.<ext>, an image, as the elg adapter names a single HTTP output
    if content is None:
        entry = md_storage.stage_output(msg, output_path, f"{md_storage.source_label(msg)}.{extension}", "image", extension)
        return md_storage.disk_response([entry])
    return {"response": {"type": "stored", "uri": f"/files/{output_id}.{extension}"}}


@app.get("/files/{filename}")
def serve_file(filename: str, background_tasks: BackgroundTasks):
    output_dir = os.path.realpath(OUTPUT_FOLDER)
    file_path = os.path.realpath(os.path.join(output_dir, filename))
    # only files directly in OUTPUT_FOLDER; '../' paths could read any file
    if os.path.dirname(file_path) != output_dir or not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    background_tasks.add_task(os.remove, file_path)
    return FileResponse(file_path)


# /config (service.json with the adapter of the storage mode), /help (help/index.md), /health
md_service.add_routes(app)


if __name__ == "__main__":
    import uvicorn

    print(f"storage mode: {md_storage.describe_mode()}")
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "9006")))
