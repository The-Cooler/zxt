"""知识库内容哈希 Repository"""

from sqlalchemy import delete, select

from zixuetong.storage.postgres.manager import pg_manager
from zixuetong.storage.postgres.models_knowledge import KnowledgeContentHash
from zixuetong.utils.datetime_utils import utc_now_naive


class KnowledgeContentHashRepository:
    """知识库内容哈希 Repository"""

    async def get_by_db_and_hash(self, db_id: str, content_hash: str) -> KnowledgeContentHash | None:
        """根据数据库ID和内容哈希查询记录"""
        async with pg_manager.get_async_session_context() as session:
            result = await session.execute(
                select(KnowledgeContentHash).where(
                    KnowledgeContentHash.db_id == db_id,
                    KnowledgeContentHash.content_hash == content_hash,
                )
            )
            return result.scalar_one_or_none()

    async def exists(self, db_id: str, content_hash: str) -> bool:
        """检查指定数据库中是否已存在该内容哈希"""
        record = await self.get_by_db_and_hash(db_id, content_hash)
        return record is not None

    async def record_indexed_content(
        self, db_id: str, content_hash: str, file_id: str, original_filename: str | None = None
    ) -> KnowledgeContentHash:
        """记录已入库的内容哈希"""
        existing = await self.get_by_db_and_hash(db_id, content_hash)
        if existing:
            # 更新最后一次使用的文件ID
            existing.last_file_id = file_id
            async with pg_manager.get_async_session_context() as session:
                session.add(existing)
                await session.commit()
                await session.refresh(existing)
            return existing

        # 创建新记录
        record = KnowledgeContentHash(
            db_id=db_id,
            content_hash=content_hash,
            original_filename=original_filename,
            first_indexed_at=utc_now_naive(),
            last_file_id=file_id,
        )
        async with pg_manager.get_async_session_context() as session:
            session.add(record)
            await session.commit()
            await session.refresh(record)
        return record

    async def delete_by_db_id(self, db_id: str) -> int:
        """删除指定知识库的所有内容哈希记录"""
        async with pg_manager.get_async_session_context() as session:
            result = await session.execute(
                select(KnowledgeContentHash).where(KnowledgeContentHash.db_id == db_id)
            )
            records = result.scalars().all()
            for record in records:
                await session.delete(record)
            await session.commit()
            return len(records)

    async def delete_by_db_and_hash(self, db_id: str, content_hash: str) -> None:
        """删除指定知识库中的特定内容哈希记录"""
        async with pg_manager.get_async_session_context() as session:
            await session.execute(
                delete(KnowledgeContentHash).where(
                    KnowledgeContentHash.db_id == db_id,
                    KnowledgeContentHash.content_hash == content_hash,
                )
            )
            await session.commit()
