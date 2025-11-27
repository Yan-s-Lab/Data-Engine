from fastapi import FastAPI
from .api import collections, samples

app = FastAPI(title="Collection Gateway")

app.include_router(collections.router)
app.include_router(samples.router)
