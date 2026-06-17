import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from sqlalchemy import inspect, text

from .config import OUTPUTS_DIR, UPLOADS_DIR
from .database import Base, SessionLocal, engine
from .routers import api, projects
from .services.openclaw_runtime import (
    GATEWAY_PORT,
    ensure_gateway_auth_config,
    gateway_manager,
    install_gateway_exit_hooks,
    openclaw_available,
)
from .utils import seed_test_llm_defaults

logger = logging.getLogger(__name__)

Base.metadata.create_all(bind=engine)


def _ensure_columns() -> None:
    """轻量迁移：为已存在的 SQLite 表补齐新增列，避免重建数据库。"""
    additions = {
        "projects": {
            "output_language": "VARCHAR(16) DEFAULT 'zh'",
            "generate_draft": "BOOLEAN DEFAULT 1",
            "keep_hyperframes": "BOOLEAN DEFAULT 1",
        },
        "jobs": {
            "log_path": "VARCHAR(1024)",
        },
    }
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table, cols in additions.items():
            if not inspector.has_table(table):
                continue
            existing = {c["name"] for c in inspector.get_columns(table)}
            for name, ddl in cols.items():
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


_ensure_columns()


def _seed_defaults() -> None:
    db = SessionLocal()
    try:
        seed_test_llm_defaults(db)
    finally:
        db.close()


_seed_defaults()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时拉起 OpenClaw Gateway 常驻进程，关闭时终止。"""
    install_gateway_exit_hooks()
    if openclaw_available():
        try:
            await asyncio.get_event_loop().run_in_executor(None, ensure_gateway_auth_config)
            logger.info("[Startup] 启动 OpenClaw Gateway 常驻进程...")
            await asyncio.get_event_loop().run_in_executor(None, gateway_manager.start)
            logger.info("[Startup] OpenClaw Gateway 已就绪")
        except Exception as exc:
            logger.warning("[Startup] Gateway 启动失败（任务将 fallback --local）: %s", exc)
    else:
        logger.warning("[Startup] OpenClaw 未安装，跳过 Gateway 启动")
    yield
    gateway_manager.stop()
    logger.info("[Shutdown] OpenClaw Gateway 已关闭")

app = FastAPI(title="FrameCraft Agent API", version="1.0.0", lifespan=lifespan)

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
    oc = openclaw_available()
    gw = gateway_manager.is_ready()
    return {
        "status": "ok",
        "orchestrator": "openclaw",
        "openclaw": oc,
        "gateway": gw,
        "gateway_url": f"ws://127.0.0.1:{GATEWAY_PORT}" if gw else None,
        "chat_engine": "openclaw-agent",
        "pipeline": "agent-only",
        "build": "2026-06-16-openclaw",
    }


app.mount("/files/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")
app.mount("/files/outputs", StaticFiles(directory=str(OUTPUTS_DIR)), name="outputs")
