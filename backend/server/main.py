import asyncio
import os
import sys

# ==============================================================================
# 解决 Windows 下 psycopg 异步模式不支持 ProactorEventLoop 的问题
# 注意：这段代码必须放在应用的极早期，最好在导入 FastAPI 或初始化数据库之前
# ==============================================================================
if sys.platform == "win32":
    # 把当前文件 (main.py) 的上一级的上一级 (即根目录 自学通) 加入到 sys.path
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server.routers import router
from server.utils.lifespan import lifespan
from server.utils.common_utils import setup_logging
from server.utils.access_log_middleware import AccessLogMiddleware

# 设置日志配置
setup_logging()

app = FastAPI(lifespan=lifespan)
# 所有业务接口统一挂载到 /api，具体分组在 server.routers 中集中注册。
app.include_router(router, prefix="/api")

# CORS 设置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 添加访问日志中间件（记录请求处理时间）
app.add_middleware(AccessLogMiddleware)

if __name__ == "__main__":
    # uvicorn.run(app, host="0.0.0.0", port=5050, threads=10, workers=10, reload=True)

    uvicorn.run(
        "server.main:app",
        host="0.0.0.0",
        port=5050,
        reload=True,
        # 与 docker-compose 开发环境保持一致，避免 package 下代码变更不触发热重载。
        reload_dirs=["server", "package"],
    )
