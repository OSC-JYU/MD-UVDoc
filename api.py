from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import uuid
import json
import cv2
import numpy as np
import torch

from utils import IMG_SIZE, bilinear_unwarping, load_model

from pydantic import BaseModel


app = FastAPI(
    title="UVDoc API",
    description="API for UVDoc",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

OUTPUT_FOLDER = 'output'
if not os.path.exists(OUTPUT_FOLDER):
    os.makedirs(OUTPUT_FOLDER)

def unwarp_img(img_path):
    """
    Unwarp a document image using the model from ckpt_path.
    """

    # Load image
    img = cv2.imread(img_path)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32) / 255
    inp = torch.from_numpy(cv2.resize(img, IMG_SIZE).transpose(2, 0, 1)).unsqueeze(0)

    # Make prediction
    inp = inp.to(device)
    point_positions2D, _ = model(inp)

    # Unwarp
    size = img.shape[:2][::-1]
    unwarped = bilinear_unwarping(
        warped_img=torch.from_numpy(img.transpose(2, 0, 1)).unsqueeze(0).to(device),
        point_positions=torch.unsqueeze(point_positions2D[0], dim=0),
        img_size=tuple(size),
    )
    unwarped = (unwarped[0].detach().cpu().numpy().transpose(1, 2, 0) * 255).astype(np.uint8)

    # Save result
    unwarped_BGR = cv2.cvtColor(unwarped, cv2.COLOR_RGB2BGR)
    return unwarped_BGR



@app.get("/")
async def root():
    return {"message": "UVDoc API for MessyDesk"}

@app.post("/process")
async def process_files(
    request: UploadFile = File(...),
    content: UploadFile = File(...)
):
    try:
        print("Processing files...")
        # Start execution time counter
        import time
        start_time = time.time()

        # read request as JSON
        request_data = await request.read()
        request_json = json.loads(request_data.decode('utf-8'))
        print(request_json)

        # save content to file with UUID 
        fileuuid = str(uuid.uuid4())
        content_path = os.path.join(UPLOAD_FOLDER, fileuuid)
        with open(content_path, 'wb') as f:
            f.write(await content.read())

        f = unwarp_img(content_path)
        cv2.imwrite(os.path.join(OUTPUT_FOLDER, fileuuid + ".jpg"), f)
        # delete content file
        os.remove(content_path)

        # End execution time counter
        end_time = time.time()
        return {"execution_time": round(end_time - start_time, 1), "response": {"uri": '/files/' + fileuuid + ".jpg"}}
        
    except Exception as e:
        print(e)
        raise HTTPException(
            status_code=500,
            detail=f"Processing failed: {str(e)}"
        )

@app.get("/files/{filename}")
async def serve_file(filename: str, background_tasks: BackgroundTasks):
    file_path = os.path.join(OUTPUT_FOLDER, filename)
    if not os.path.isfile(file_path):
        raise HTTPException(
            status_code=404,
            detail="File not found"
        )
    def remove_file(path: str):
        try:
            os.remove(path)
        except Exception as e:
            print(f"Error deleting file {path}: {e}")
            
    background_tasks.add_task(remove_file, file_path)
    return FileResponse(file_path, background=background_tasks)


if __name__ == "__main__":
    ckpt_path = './model/best_model.pkl'
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(device)
    print('loading model ', ckpt_path)
    model = load_model(ckpt_path, device)
    model.to(device)
    model.eval()
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9006) 
