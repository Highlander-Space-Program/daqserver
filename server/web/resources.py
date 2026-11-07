from fastapi.templating import Jinja2Templates

from server.web.connection import ConnectionManager


templates = Jinja2Templates(directory="./server/web/templates")
manager = ConnectionManager()
