"""
This module defines `app` and database for the frontend

The database for the frontend is going to save the charts and equations
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI()
app.mount("/static", StaticFiles(directory="./server/web/static"), name="static")
