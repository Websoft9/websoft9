from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.staticfiles import StaticFiles

app = Starlette()


async def healthz(request):
	return JSONResponse({"status": "ok"})


app.add_route("/healthz", healthz)


app.mount("/images", StaticFiles(directory="/websoft9/media"), name="images")