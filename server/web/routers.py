from server.web.app import app
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="./server/web/templates")


# Serve the main dashboard page
@app.route("/")
async def index():
    return templates.TemplateResponse("index.html")


# Optional debug route to see raw live data
# @app.route("/debug")
# def debug():
#     with streaming.live_data_lock:
#         return streaming.live_data.copy()
