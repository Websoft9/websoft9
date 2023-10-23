from starlette.applications import Starlette
from starlette.staticfiles import StaticFiles

app = Starlette()
app.mount("/images", StaticFiles(directory="/websoft9/media"), name="images")