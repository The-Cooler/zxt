import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from zixuetong.services.task_service import tasker
from zixuetong.services.mcp_service import ensure_builtin_mcp_servers_in_db
from zixuetong.services.model_provider_service import ensure_builtin_model_providers_in_db
from zixuetong.services.subagent_service import init_builtin_subagents
from zixuetong.services.run_queue_service import close_queue_clients, get_redis_client
from zixuetong.storage.postgres.manager import pg_manager
from zixuetong.knowledge import knowledge_base
from zixuetong.utils import logger
from zixuetong.agents.backends.sandbox import init_sandbox_provider, shutdown_sandbox_provider
from zixuetong import get_version


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan事件管理器"""
    # 初始化数据库连接
    try:
        pg_manager.initialize()
        await pg_manager.create_tables()
    except Exception as e:
        logger.error(f"Failed to initialize database during startup: {e}")

    # 确保内置 MCP 服务器定义存在于数据库
    try:
        await ensure_builtin_mcp_servers_in_db()
    except Exception as e:
        logger.error(f"Failed to ensure builtin MCP servers during startup: {e}")

    # 初始化内置模型供应商配置
    try:
        async with pg_manager.get_async_session_context() as session:
            await ensure_builtin_model_providers_in_db(session)
    except Exception as e:
        logger.error(f"Failed to ensure builtin model providers during startup: {e}")

    # 初始化模型缓存（v2 模型选择使用）
    try:
        from zixuetong.services.model_cache import model_cache
        from zixuetong.services.model_provider_service import get_all_model_providers

        async with pg_manager.get_async_session_context() as session:
            providers = await get_all_model_providers(session)
            model_cache.rebuild(providers)
    except Exception as e:
        logger.error(f"Failed to initialize model cache during startup: {e}")

    # 初始化内置 SubAgent
    try:
        await init_builtin_subagents()
    except Exception as e:
        logger.error(f"Failed to initialize builtin subagents during startup: {e}")
        raise

    # 初始化知识库管理器
    if os.environ.get("LITE_MODE", "").lower() in ("true", "1"):
        logger.info("LITE_MODE enabled, skipping knowledge base initialization")
    else:
        try:
            await knowledge_base.initialize()
        except Exception as e:
            logger.error(f"Failed to initialize knowledge base manager: {e}")

    # 预热 Redis（run 队列）
    try:
        redis = await get_redis_client()
        await redis.ping()
    except Exception as e:
        logger.warning(f"Run queue redis unavailable on startup: {e}")

    try:
        init_sandbox_provider()
    except Exception as e:
        logger.error(f"Failed to initialize sandbox provider during startup: {e}")

    # =========================================================
    # 2. 核心修复：在这里执行一次 setup()，建完表就拉倒
    # =========================================================
    checkpointer = AsyncPostgresSaver(pg_manager.langgraph_pool)
    await checkpointer.setup()
    print("LangGraph Checkpoint tables verified/created!")

    await tasker.start()

    try:
        from zixuetong.services.clawbot.bridge_service import clawbot_bridge

        await clawbot_bridge.start()
    except Exception as e:
        logger.warning(f"ClawBot startup skipped: {e}")

    from zixuetong.services.learning_reminder_service import learning_reminder_scheduler

    await learning_reminder_scheduler.start()

    logger.info(f"""

░██     ░██                       ░██
 ░██   ░██
  ░██ ░██   ░██    ░██ ░██    ░██ ░██
   ░████    ░██    ░██  ░██  ░██  ░██
    ░██     ░██    ░██   ░█████   ░██
    ░██     ░██   ░███  ░██  ░██  ░██
    ░██      ░█████░██ ░██    ░██ ░██  v{get_version()}

    """)
    logger.info("自学通 backend startup complete")
    yield
    await learning_reminder_scheduler.stop()
    await tasker.shutdown()

    try:
        from zixuetong.services.clawbot.bridge_service import clawbot_bridge

        await clawbot_bridge.stop()
    except Exception as e:
        logger.warning(f"ClawBot shutdown error: {e}")

    shutdown_sandbox_provider()
    await close_queue_clients()
    await pg_manager.close()
