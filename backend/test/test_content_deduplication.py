"""测试内容去重功能"""

import asyncio
import hashlib
import tempfile
from pathlib import Path

import pytest
from zixuetong.knowledge.implementations.lightrag import LightRAGKnowledgeBase
from zixuetong.repositories.knowledge_content_hash_repository import KnowledgeContentHashRepository
from zixuetong.storage.postgres.manager import pg_manager


@pytest.fixture
async def knowledge_base():
    """创建测试知识库"""
    kb = LightRAGKnowledgeBase()
    test_db_id = "test_dedup_kb"

    # 创建测试知识库
    try:
        await kb.create_database(
            db_id=test_db_id,
            name="去重测试知识库",
            description="用于测试内容去重功能",
            operator_id="test_user",
        )
        yield kb, test_db_id
    finally:
        # 清理测试数据
        try:
            await kb.delete_database(test_db_id, operator_id="test_user")
        except Exception:
            pass


@pytest.mark.asyncio
async def test_duplicate_content_prevention(knowledge_base):
    """测试重复内容阻止功能"""
    kb, db_id = knowledge_base

    # 创建临时测试文件
    test_content = "这是一个测试文档的内容。用于验证去重功能是否正常工作。"
    content_hash = hashlib.sha256(test_content.encode()).hexdigest()

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(test_content)
        temp_file = f.name

    try:
        # 第一次上传文件
        result1 = await kb.add_file(
            db_id=db_id,
            file_path=temp_file,
            filename="test_doc_1.txt",
            operator_id="test_user",
        )
        file_id_1 = result1["file_id"]

        # 解析文件
        await kb.parse_file(db_id=db_id, file_id=file_id_1, operator_id="test_user")

        # 入库第一个文件
        await kb.index_file(db_id=db_id, file_id=file_id_1, operator_id="test_user")

        # 验证 content_hash 已记录
        hash_repo = KnowledgeContentHashRepository()
        exists = await hash_repo.exists(db_id, content_hash)
        assert exists, "第一次入库后，content_hash 应该被记录"

        # 第二次上传相同内容的文件（不同文件名）
        result2 = await kb.add_file(
            db_id=db_id,
            file_path=temp_file,
            filename="test_doc_2.txt",
            operator_id="test_user",
        )
        file_id_2 = result2["file_id"]

        # 解析第二个文件
        await kb.parse_file(db_id=db_id, file_id=file_id_2, operator_id="test_user")

        # 尝试入库第二个文件，应该被阻止
        with pytest.raises(ValueError, match="该文件内容已在知识库中存在"):
            await kb.index_file(db_id=db_id, file_id=file_id_2, operator_id="test_user")

        print("✓ 重复内容成功被阻止")

    finally:
        # 清理临时文件
        Path(temp_file).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_content_hash_cleanup_on_kb_delete():
    """测试删除知识库时清理 content_hash 记录"""
    kb = LightRAGKnowledgeBase()
    test_db_id = "test_cleanup_kb"

    try:
        # 创建测试知识库
        await kb.create_database(
            db_id=test_db_id,
            name="清理测试知识库",
            operator_id="test_user",
        )

        # 手动插入一条 content_hash 记录
        hash_repo = KnowledgeContentHashRepository()
        test_hash = "test_hash_for_cleanup"
        await hash_repo.record_indexed_content(
            db_id=test_db_id,
            content_hash=test_hash,
            file_id="test_file",
        )

        # 验证记录存在
        exists_before = await hash_repo.exists(test_db_id, test_hash)
        assert exists_before, "记录应该存在"

        # 删除知识库（由于外键约束，content_hash 记录应该被级联删除）
        await kb.delete_database(test_db_id, operator_id="test_user")

        # 验证记录已被删除
        exists_after = await hash_repo.exists(test_db_id, test_hash)
        assert not exists_after, "删除知识库后，content_hash 记录应该被清理"

        print("✓ 知识库删除后 content_hash 记录成功清理")

    finally:
        try:
            await kb.delete_database(test_db_id, operator_id="test_user")
        except Exception:
            pass


if __name__ == "__main__":
    # 运行测试
    pg_manager.initialize()

    async def run_tests():
        print("开始测试内容去重功能...\n")

        # 测试 1: 重复内容阻止
        print("测试 1: 重复内容阻止")
        kb = LightRAGKnowledgeBase()
        test_db_id = "test_dedup_kb"

        try:
            await kb.create_database(
                db_id=test_db_id,
                name="去重测试知识库",
                operator_id="test_user",
            )
            await test_duplicate_content_prevention((kb, test_db_id))
        finally:
            try:
                await kb.delete_database(test_db_id, operator_id="test_user")
            except Exception:
                pass

        print("\n测试 2: 知识库删除时清理 content_hash")
        await test_content_hash_cleanup_on_kb_delete()

        print("\n所有测试通过!")

    asyncio.run(run_tests())
