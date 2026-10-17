"""PostgreSQL 数据库管理器 - 支持知识库和业务数据"""

import json
import os
from contextlib import asynccontextmanager

from psycopg_pool import AsyncConnectionPool
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from zixuetong.storage.postgres.models_business import Base as BusinessBase
from zixuetong.storage.postgres import models_knowledge  # noqa: F401
from zixuetong.utils import logger

from server.utils.singleton import SingletonMeta


class PostgresManager(metaclass=SingletonMeta):
    """PostgreSQL 数据库管理器 - 支持知识库和业务数据"""

    # 知识库 PostgreSQL URL 环境变量名
    KB_DATABASE_URL_ENV = "POSTGRES_URL"

    def __init__(self):
        self.async_engine = None
        self.AsyncSession = None
        self.langgraph_pool = None
        self._initialized = False

    def initialize(self):
        """初始化数据库连接"""
        if self._initialized:
            return

        db_url = os.getenv(self.KB_DATABASE_URL_ENV)
        if not db_url:
            logger.error(
                f"环境变量 {self.KB_DATABASE_URL_ENV} 未设置，"
                "请在 docker-compose.yml 或 .env 中配置 PostgreSQL 连接字符串"
            )
            return

        try:
            # 创建异步 SQLAlchemy 引擎
            self.async_engine = create_async_engine(
                db_url,
                json_serializer=lambda obj: json.dumps(obj, ensure_ascii=False),
                json_deserializer=json.loads,
                pool_pre_ping=True,
                pool_recycle=1800,
            )

            # 创建异步会话工厂
            self.AsyncSession = async_sessionmaker(
                bind=self.async_engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )

            # ==========================================
            # 2. 为 LangGraph 专门初始化一个原生 psycopg_pool
            # ==========================================
            # 注意：psycopg 不认识 "+asyncpg" 这样的 SQLAlchemy 方言标识。
            # 如果你的 db_url 是 "postgresql+asyncpg://user:pwd@host/db"，
            # 需要把它清洗成标准的 "postgresql://user:pwd@host/db"
            langgraph_db_url = db_url.replace("+asyncpg", "").replace("+psycopg", "")

            # 创建 LangGraph 专属连接池
            self.langgraph_pool = AsyncConnectionPool(
                conninfo=langgraph_db_url,
                max_size=10,  # 根据你的 Agent 并发情况设置，通常 5-10 足够了
                kwargs={"autocommit": True},  # LangGraph Checkpoint 强依赖 autocommit
            )

            self._initialized = True
            logger.info(f"PostgreSQL manager initialized for knowledge base: {db_url.split('@')[0]}://***")
        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL manager: {e}")
            # 不抛出异常，允许应用启动，但在使用时会报错

    def _check_initialized(self):
        """检查是否已初始化"""
        if not self._initialized:
            raise RuntimeError("PostgreSQL manager not initialized. Please check configuration.")

    async def create_tables(self):
        """按当前 SQLAlchemy 模型一次性创建所有表。"""
        self._check_initialized()
        async with self.async_engine.begin() as conn:
            await conn.run_sync(BusinessBase.metadata.create_all)
            # create_all 不会给已存在的表补列，新增列在这里显式补。
            await conn.execute(
                text(
                    "ALTER TABLE knowledge_files "
                    "ADD COLUMN IF NOT EXISTS graph_status VARCHAR(32) DEFAULT 'pending'"
                )
            )
        await self.ensure_system_owner()
        logger.info("PostgreSQL tables created/checked from SQLAlchemy models")

    async def drop_tables(self):
        """删除所有表（慎用！）"""
        self._check_initialized()
        async with self.async_engine.begin() as conn:
            await conn.run_sync(BusinessBase.metadata.drop_all)
        logger.info("PostgreSQL tables dropped")

    async def ensure_system_owner(self):
        """确保单用户模式唯一使用的系统 owner 存在。"""
        self._check_initialized()

        async with self.get_async_session_context() as session:
            result = await session.execute(
                text(
                    """
                    SELECT id
                    FROM users
                    ORDER BY id
                    LIMIT 1
                    """
                )
            )
            if result.scalar_one_or_none() is not None:
                return

            await session.execute(
                text(
                    """
                    INSERT INTO users (
                        username,
                        user_id,
                        created_at
                    )
                    VALUES (
                        '系统所有者',
                        'system-owner',
                        NOW()
                    )
                    ON CONFLICT DO NOTHING
                    """
                )
            )

            result = await session.execute(
                text(
                    """
                    SELECT id
                    FROM users
                    ORDER BY id
                    LIMIT 1
                    """
                )
            )
            if result.scalar_one_or_none() is None:
                raise RuntimeError("无法创建单用户模式系统 owner，请检查 users 表中的唯一键冲突")

            logger.info("Created single-user system owner")

    @property
    def is_postgresql(self) -> bool:
        """检查是否是 PostgreSQL 数据库"""
        if not self._initialized:
            return False
        return self.async_engine.dialect.name == "postgresql"

    async def get_async_session(self) -> AsyncSession:
        """获取异步数据库会话"""
        self._check_initialized()
        return self.AsyncSession()

    @asynccontextmanager
    async def get_async_session_context(self):
        """获取异步数据库会话的上下文管理器"""
        self._check_initialized()
        session = self.AsyncSession()
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"PostgreSQL async operation failed: {e}")
            raise
        finally:
            await session.close()

    async def close(self):
        """关闭引擎"""
        if self.async_engine:
            await self.async_engine.dispose()

        if self.langgraph_pool:
            await self.langgraph_pool.close()

    async def execute(self, statement):
        """直接执行 SQL 语句（用于迁移脚本）"""
        self._check_initialized()
        async with self.get_async_session_context() as session:
            return await session.execute(statement)

    async def add(self, instance):
        """添加实例到会话（用于迁移脚本）"""
        self._check_initialized()
        async with self.get_async_session_context() as session:
            session.add(instance)

    async def commit(self):
        """提交当前会话"""
        self._check_initialized()
        async with self.get_async_session_context():
            pass  # commit is automatic in context manager


# 创建全局 PostgreSQL 管理器实例
pg_manager = PostgresManager()
