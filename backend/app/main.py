from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import OUTPUTS_DIR, UPLOADS_DIR
from .database import Base, engine
from .routers import api, projects

Base.metadata.create_all(bind=engine)

app = FastAPI(title="FrameCraft Agent API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router)
app.include_router(api.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


app.mount("/files/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")
app.mount("/files/outputs", StaticFiles(directory=str(OUTPUTS_DIR)), name="outputs")
