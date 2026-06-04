import os
import uuid

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.staticfiles import StaticFiles

app = Starlette()

MEDIA_DIR = "/websoft9/media"


async def healthz(request):
    return JSONResponse({"status": "ok"})


async def upload(request):
    try:
        form = await request.form()
        file = form.get("file")
        if file is None:
            return JSONResponse({"error": "No file provided"}, status_code=400)

        ext = os.path.splitext(file.filename)[1] if file.filename else ""
        filename = f"{uuid.uuid4().hex}{ext}"
        filepath = os.path.join(MEDIA_DIR, filename)

        os.makedirs(MEDIA_DIR, exist_ok=True)
        content = await file.read()
        with open(filepath, "wb") as f:
            f.write(content)

        url = f"/api/media/images/{filename}"
        return JSONResponse({"url": url})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


app.add_route("/healthz", healthz)
app.add_route("/upload", upload, methods=["POST"])

app.mount("/images", StaticFiles(directory=MEDIA_DIR), name="images")