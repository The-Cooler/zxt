import asyncio
import os
import traceback
from collections.abc import Callable
from contextlib import asynccontextmanager
from functools import partial
from types import MethodType

from lightrag import LightRAG, QueryParam
from lightrag.base import DocStatus
from lightrag.kg.shared_storage import initialize_pipeline_status
from lightrag.llm.openai import openai_complete_if_cache, openai_embed
from lightrag.utils import EmbeddingFunc
from lightrag.utils import compute_mdhash_id, get_content_summary, sanitize_text_for_encoding
from neo4j import GraphDatabase

from zixuetong import config
from zixuetong.knowledge.base import FileStatus, KnowledgeBase
from zixuetong.knowledge.chunking.ragflow_like.dispatcher import chunk_markdown
from zixuetong.knowledge.chunking.ragflow_like.presets import resolve_chunk_processing_params
from zixuetong.models.embed import get_embedding_model_info_by_id
from zixuetong.plugins.parser.unified import Parser
from zixuetong.utils import logger
from zixuetong.utils.datetime_utils import utc_isoformat


INDEX_MODE_FAST = "fast"
INDEX_MODE_STANDARD = "standard"
INDEX_MODE_GRAPH = "graph"
INDEX_MODES = {INDEX_MODE_FAST, INDEX_MODE_STANDARD, INDEX_MODE_GRAPH}
MAX_GRAPH_NODES_LIMIT = 1000
MAX_GRAPH_RELATIONS_LIMIT = 3000


def _coerce_positive_int(value, *, max_value: int) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    if parsed <= 0:
        return None
    return min(parsed, max_value)


def resolve_ingestion_options(params: dict | None) -> dict:
    params = params or {}
    index_mode = str(params.get("index_mode") or INDEX_MODE_STANDARD).strip().lower()
    if index_mode not in INDEX_MODES:
        index_mode = INDEX_MODE_STANDARD

    return {
        "index_mode": index_mode,
        "max_graph_nodes": _coerce_positive_int(
            params.get("max_graph_nodes"),
            max_value=MAX_GRAPH_NODES_LIMIT,
        ),
        "max_graph_relations": _coerce_positive_int(
            params.get("max_graph_relations"),
            max_value=MAX_GRAPH_RELATIONS_LIMIT,
        ),
    }


def limit_extracted_graph_results(
    chunk_results: list,
    *,
    max_nodes: int | None,
    max_relations: int | None,
) -> list:
    if max_nodes is None and max_relations is None:
        return chunk_results

    allowed_nodes: set[str] | None = None
    remaining_nodes = max_nodes
    if max_nodes is not None:
        allowed_nodes = set()
        for maybe_nodes, _maybe_edges in chunk_results:
            for entity_name in maybe_nodes:
                if entity_name in allowed_nodes:
                    continue
                if remaining_nodes is not None and remaining_nodes <= 0:
                    break
                allowed_nodes.add(entity_name)
                remaining_nodes -= 1
            if remaining_nodes is not None and remaining_nodes <= 0:
                break

    remaining_relations = max_relations
    limited_results = []
    for maybe_nodes, maybe_edges in chunk_results:
        if allowed_nodes is None:
            limited_nodes = maybe_nodes
        else:
            limited_nodes = {
                entity_name: entities
                for entity_name, entities in maybe_nodes.items()
                if entity_name in allowed_nodes
            }

        limited_edges = {}
        for edge_key, edges in maybe_edges.items():
            src_id, tgt_id = edge_key
            if allowed_nodes is not None and (src_id not in allowed_nodes or tgt_id not in allowed_nodes):
                continue
            if remaining_relations is not None and remaining_relations <= 0:
                break
            limited_edges[edge_key] = edges
            if remaining_relations is not None:
                remaining_relations -= 1

        limited_results.append((limited_nodes, limited_edges))

    return limited_results


class LightRagKB(KnowledgeBase):
    """基于 LightRAG 的知识库实现"""

    def __init__(self, work_dir: str, **kwargs):
        """
        初始化 LightRAG 知识库

        Args:
            work_dir: 工作目录
            **kwargs: 其他配置参数
        """
        super().__init__(work_dir)

        # 存储 LightRAG 实例映射 {db_id: LightRAG}
        self.instances: dict[str, LightRAG] = {}
        self._db_write_locks: dict[str, asyncio.Lock] = {}
        self._db_instance_locks: dict[str, asyncio.Lock] = {}
        self._lock_guard = asyncio.Lock()

        logger.info("LightRagKB initialized")

    @property
    def kb_type(self) -> str:
        """知识库类型标识"""
        return "lightrag"

    @staticmethod
    def _prepare_lightrag_insert_payload(chunks: list[dict]) -> tuple[str, str | None, bool]:
        if not chunks:
            return "", None, False

        if len(chunks) == 1:
            return chunks[0]["content"], None, False

        delimiter = "\n<|ZIXUETONG_CHUNK_DELIM|>\n"
        payload = delimiter.join(chunk["content"] for chunk in chunks if chunk.get("content"))
        return payload, delimiter, False  # 允许 LightRAG 基于进行二次切分，避免超限

    @staticmethod
    def _is_current_doc_chunks(chunks: dict, file_id: str) -> bool:
        return bool(chunks) and all(chunk.get("full_doc_id") == file_id for chunk in chunks.values())

    @asynccontextmanager
    async def _scoped_graph_limits(
        self,
        rag: LightRAG,
        *,
        file_id: str,
        max_nodes: int | None,
        max_relations: int | None,
    ):
        if max_nodes is None and max_relations is None:
            yield
            return

        original_method: Callable = rag._process_extract_entities

        async def limited_process_extract_entities(
            rag_self,
            chunks: dict,
            pipeline_status=None,
            pipeline_status_lock=None,
        ) -> list:
            chunk_results = await original_method(chunks, pipeline_status, pipeline_status_lock)
            if not self._is_current_doc_chunks(chunks, file_id):
                return chunk_results

            limited_results = limit_extracted_graph_results(
                chunk_results,
                max_nodes=max_nodes,
                max_relations=max_relations,
            )
            logger.info(
                f"Applied graph extraction limits for file {file_id}: "
                f"max_nodes={max_nodes}, max_relations={max_relations}"
            )
            return limited_results

        rag._process_extract_entities = MethodType(limited_process_extract_entities, rag)
        try:
            yield
        finally:
            rag._process_extract_entities = original_method

    async def _fast_insert_chunks(
        self,
        rag: LightRAG,
        *,
        markdown_content: str,
        chunks: list[dict],
        file_id: str,
        file_path: str | None,
    ) -> None:
        text_chunks = [chunk.get("content", "") for chunk in chunks if chunk.get("content")]
        if not text_chunks:
            text_chunks = [markdown_content]

        sanitized_chunks = [sanitize_text_for_encoding(content) for content in text_chunks]
        chunk_ids = [compute_mdhash_id(content, prefix="chunk-") for content in sanitized_chunks]

        custom_kg = {
            "chunks": [
                {
                    "content": content,
                    "source_id": f"{file_id}_{index}",
                    "file_path": file_path or "",
                    "chunk_order_index": index,
                }
                for index, content in enumerate(sanitized_chunks)
            ],
            "entities": [],
            "relationships": [],
        }
        await rag.ainsert_custom_kg(custom_kg, full_doc_id=file_id)
        updated_at = utc_isoformat()
        full_doc = {"content": sanitize_text_for_encoding(markdown_content), "file_path": file_path or "unknown_source"}
        await rag.full_docs.upsert({file_id: full_doc})
        await rag.doc_status.upsert(
            {
                file_id: {
                    "status": DocStatus.PROCESSED,
                    "chunks_count": len(chunk_ids),
                    "chunks_list": chunk_ids,
                    "content_summary": get_content_summary(markdown_content),
                    "content_length": len(markdown_content),
                    "created_at": updated_at,
                    "updated_at": updated_at,
                    "file_path": file_path or "unknown_source",
                    "metadata": {"ingestion_mode": INDEX_MODE_FAST},
                }
            }
        )
        await rag.full_docs.index_done_callback()
        await rag.doc_status.index_done_callback()

    def delete_database(self, db_id: str) -> dict:
        """删除数据库，同时清除Neo4j中的数据。LightRAG PostgreSQL 向量表由上游存储层管理。"""
        # Delete Neo4j data
        neo4j_uri = os.getenv("NEO4J_URI") or "bolt://localhost:7687"
        neo4j_username = os.getenv("NEO4J_USERNAME") or "neo4j"
        neo4j_password = os.getenv("NEO4J_PASSWORD") or "0123456789"

        try:
            driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_username, neo4j_password))
            with driver.session() as session:
                # 删除带有特定 db_id 标签的节点和关系
                session.run(
                    """
                    MATCH (n:`"""
                    + db_id
                    + """`)
                    DETACH DELETE n
                """
                )

                logger.info(f"Deleted Neo4j nodes and relationships for workspace {db_id}")
        except Exception as e:
            logger.error(f"Failed to delete Neo4j data for {db_id}: {e}")
        finally:
            if "driver" in locals():
                driver.close()

        # Delete local files and metadata
        return super().delete_database(db_id)

    def update_database(
        self,
        db_id: str,
        name: str,
        description: str,
        llm_info: dict = None,
        additional_params: dict | None = None,
    ) -> dict:
        """
        更新数据库配置

        当 llm_info 改变时，清除缓存的 LightRAG 实例，确保下次使用时使用新模型创建实例
        """
        if db_id not in self.databases_meta:
            raise ValueError(f"数据库 {db_id} 不存在")

        # 检查 llm_info 是否发生变化
        old_llm_info = self.databases_meta[db_id].get("llm_info", {})
        llm_info_changed = llm_info is not None and llm_info != old_llm_info
        logger.warning(f"old_llm_info: {old_llm_info}, new_llm_info: {llm_info}, llm_info_changed: {llm_info_changed}")

        # 调用父类方法更新基本信息
        result = super().update_database(db_id, name, description, llm_info, additional_params)

        # 如果 llm_info 发生变化，清除缓存的实例，确保下次使用新模型
        if llm_info_changed and db_id in self.instances:
            logger.info(f"LLM model changed, invalidating cached LightRAG instance for {db_id}")
            del self.instances[db_id]

        return result

    async def _create_kb_instance(self, db_id: str, kb_config: dict) -> LightRAG:
        """创建 LightRAG 实例"""
        logger.info(f"Creating LightRAG instance for {db_id}")

        if db_id not in self.databases_meta:
            raise ValueError(f"Database {db_id} not found")

        llm_info = self.databases_meta[db_id].get("llm_info", {})
        embed_info = self.databases_meta[db_id].get("embed_info", {})
        # 读取在创建数据库时透传的附加参数（包括语言）
        metadata = self.databases_meta[db_id].get("metadata", {}) or {}
        addon_params = {}
        if isinstance(metadata.get("addon_params"), dict):
            addon_params.update(metadata.get("addon_params", {}))
        # 兼容直接放在 metadata 下的 language
        if isinstance(metadata.get("language"), str) and metadata.get("language"):
            addon_params.setdefault("language", metadata.get("language"))
        # 默认语言从环境变量读取，默认 English
        addon_params.setdefault("language", os.getenv("SUMMARY_LANGUAGE") or "English")

        # 创建工作目录
        working_dir = os.path.join(self.work_dir, db_id)
        os.makedirs(working_dir, exist_ok=True)

        # 创建 LightRAG 实例
        rag = LightRAG(
            working_dir=working_dir,
            workspace=db_id,
            llm_model_func=self._get_llm_func(llm_info),
            embedding_func=self._get_embedding_func(embed_info),
            vector_storage=os.getenv("LIGHTRAG_VECTOR_STORAGE") or "PGVectorStorage",
            kv_storage="JsonKVStorage",
            graph_storage="Neo4JStorage",
            doc_status_storage="JsonDocStatusStorage",
            log_file_path=os.path.join(working_dir, "lightrag.log"),
            addon_params=addon_params,
        )

        return rag

    async def _initialize_kb_instance(self, instance: LightRAG) -> None:
        """初始化 LightRAG 实例"""
        logger.info(f"Initializing LightRAG instance for {instance.working_dir}")
        await instance.initialize_storages()
        await initialize_pipeline_status()

    @staticmethod
    async def _ensure_doc_processed(rag: LightRAG, file_id: str) -> None:
        """确保 LightRAG 文档处理成功，否则抛出异常。"""
        status_doc = await rag.doc_status.get_by_id(file_id)
        if not status_doc:
            raise ValueError(f"LightRAG 文档状态缺失: {file_id}")

        status = status_doc.get("status")
        status_value = status.value if hasattr(status, "value") else status
        if status_value not in {"processed", "preprocessed"}:
            error_msg = status_doc.get("error_msg") or "unknown error"
            raise ValueError(f"LightRAG 实体关系抽取失败: file_id={file_id}, status={status_value}, error={error_msg}")

    async def _get_lightrag_instance(self, db_id: str) -> LightRAG | None:
        """获取或创建 LightRAG 实例"""
        if db_id in self.instances:
            logger.info(f"Using cached LightRAG instance for {db_id}")
            return self.instances[db_id]

        if db_id not in self.databases_meta:
            return None

        instance_lock = await self._get_db_instance_lock(db_id)
        async with instance_lock:
            if db_id in self.instances:
                logger.info(f"Using cached LightRAG instance for {db_id}")
                return self.instances[db_id]

            try:
                # 创建实例
                rag = await self._create_kb_instance(db_id, {})

                # 异步初始化存储
                await self._initialize_kb_instance(rag)

                self.instances[db_id] = rag
                return rag

            except Exception as e:
                logger.error(f"Failed to create LightRAG instance for {db_id}: {e}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                return None

    async def _get_db_write_lock(self, db_id: str) -> asyncio.Lock:
        async with self._lock_guard:
            return self._db_write_locks.setdefault(db_id, asyncio.Lock())

    async def _get_db_instance_lock(self, db_id: str) -> asyncio.Lock:
        async with self._lock_guard:
            return self._db_instance_locks.setdefault(db_id, asyncio.Lock())

    def _get_llm_func(self, llm_info: dict):
        """获取 LLM 函数"""
        from zixuetong.models import select_model

        # 如果用户选择了LLM，使用用户选择的；否则使用环境变量默认值
        if llm_info and llm_info.get("model_spec"):
            model_spec = llm_info["model_spec"]
            logger.info(f"Using user-selected LLM spec: {model_spec}")
        elif llm_info and llm_info.get("provider") and llm_info.get("model_name"):
            model_spec = f"{llm_info['provider']}/{llm_info['model_name']}"
            logger.info(f"Using user-selected LLM: {model_spec}")
        else:
            model_spec = config.default_model
            logger.info(f"Using default LLM from environment: {model_spec}")

        model = select_model(model_spec=model_spec)

        async def llm_model_func(prompt, system_prompt=None, history_messages=[], **kwargs):
            return await openai_complete_if_cache(
                model=model.model_name,
                prompt=prompt,
                system_prompt=system_prompt,
                history_messages=history_messages,
                api_key=model.api_key,
                base_url=model.base_url,
                **kwargs,
            )

        return llm_model_func

    def _get_embedding_func(self, embed_info: dict):
        """获取 embedding 函数"""
        config_dict = get_embedding_model_info_by_id(embed_info["model_id"])
        logger.debug(f"Embedding config dict: {config_dict}")

        if config_dict.get("model_id") and config_dict["model_id"].startswith("ollama"):
            from lightrag.llm.ollama import ollama_embed

            from zixuetong.utils import get_docker_safe_url

            host = get_docker_safe_url(config_dict["base_url"].replace("/api/embed", ""))
            logger.debug(f"Ollama host: {host}")
            return EmbeddingFunc(
                embedding_dim=config_dict["dimension"],
                max_token_size=8192,
                func=lambda texts: ollama_embed(
                    texts=texts,
                    embed_model=config_dict["name"],
                    api_key=config_dict["api_key"],
                    host=host,
                ),
            )

        # 尝试获取模型名称，支持多种键名以保持兼容性
        if "name" in config_dict and config_dict["name"]:
            model_name = config_dict["name"]
        elif "model" in config_dict and config_dict["model"]:
            model_name = config_dict["model"]
        else:
            raise ValueError(f"Neither 'name' nor 'model' found in config_dict or both are empty: {config_dict}")
        return EmbeddingFunc(
            embedding_dim=config_dict["dimension"],
            max_token_size=8192,
            model_name=model_name,
            func=partial(
                openai_embed.func,
                model=model_name,
                api_key=config_dict["api_key"],
                base_url=config_dict["base_url"].replace("/embeddings", ""),
            ),
        )

    async def index_file(
        self, db_id: str, file_id: str, operator_id: str | None = None, params: dict | None = None
    ) -> dict:
        """
        Index parsed file (Status: INDEXING -> INDEXED/ERROR_INDEXING)

        Args:
            db_id: Database ID
            file_id: File ID
            operator_id: ID of the user performing the operation
            params: Override processing params to apply during indexing (merged on top of stored params)

        Returns:
            Updated file metadata
        """
        if db_id not in self.databases_meta:
            raise ValueError(f"Database {db_id} not found")

        db_write_lock = await self._get_db_write_lock(db_id)
        async with db_write_lock:
            rag = await self._get_lightrag_instance(db_id)
            if not rag:
                raise ValueError(f"Failed to get LightRAG instance for {db_id}")

            # Get file meta
            if file_id not in self.files_meta:
                raise ValueError(f"File {file_id} not found")
            file_meta = self.files_meta[file_id]

            # Validate current status - only allow indexing from these states
            current_status = file_meta.get("status")
            allowed_statuses = {
                FileStatus.PARSED,
                FileStatus.ERROR_INDEXING,
                FileStatus.INDEXED,  # For re-indexing
                "done",  # Legacy status
            }

            if current_status not in allowed_statuses:
                raise ValueError(
                    f"Cannot index file with status '{current_status}'. "
                    f"File must be parsed first (status should be one of: {', '.join(allowed_statuses)})"
                )

            # Check markdown file exists
            if not file_meta.get("markdown_file"):
                await self._mark_file_unparsed(file_id, operator_id)
                raise ValueError("File has not been parsed yet (no markdown_file)")

            # Clear previous error if any
            if "error" in file_meta:
                self.files_meta[file_id].pop("error", None)

            # Update status and add to processing queue
            self.files_meta[file_id]["status"] = FileStatus.INDEXING
            self.files_meta[file_id]["updated_at"] = utc_isoformat()
            if operator_id:
                self.files_meta[file_id]["updated_by"] = operator_id
            await self._persist_file(file_id)

            # Add to processing queue
            self._add_to_processing_queue(file_id)

            try:
                # Read markdown
                markdown_content = await self._read_markdown_from_minio(file_meta["markdown_file"])
                file_path = file_meta.get("path")
                filename = file_meta.get("filename") or file_id
                params = resolve_chunk_processing_params(
                    kb_additional_params=self.databases_meta.get(db_id, {}).get("metadata"),
                    file_processing_params=file_meta.get("processing_params"),
                    request_params=params,
                )
                ingestion_options = resolve_ingestion_options(params)
                self.files_meta[file_id]["processing_params"] = params
                await self._save_metadata()

                chunks = chunk_markdown(markdown_content, file_id, filename, params)
                chunk_input, split_by_character, split_by_character_only = self._prepare_lightrag_insert_payload(chunks)
                if not chunk_input:
                    chunk_input = markdown_content

                # Clean up existing chunks if any (for re-indexing)
                await self.delete_file_chunks_only(db_id, file_id)

                # Insert
                if ingestion_options["index_mode"] == INDEX_MODE_FAST:
                    await self._fast_insert_chunks(
                        rag,
                        markdown_content=markdown_content,
                        chunks=chunks,
                        file_id=file_id,
                        file_path=file_path,
                    )
                else:
                    async with self._scoped_graph_limits(
                        rag,
                        file_id=file_id,
                        max_nodes=ingestion_options["max_graph_nodes"],
                        max_relations=ingestion_options["max_graph_relations"],
                    ):
                        await rag.ainsert(
                            input=chunk_input,
                            ids=file_id,
                            file_paths=file_path,
                            split_by_character=split_by_character,
                            split_by_character_only=split_by_character_only,
                        )
                    await self._ensure_doc_processed(rag, file_id)

                logger.info(
                    f"Indexed file {file_id} into LightRAG with {len(chunks)} chunks, "
                    f"chunk_preset_id={params.get('chunk_preset_id')}, "
                    f"index_mode={ingestion_options['index_mode']}"
                )

                # Update status
                self.files_meta[file_id]["status"] = FileStatus.INDEXED
                self.files_meta[file_id]["updated_at"] = utc_isoformat()
                if operator_id:
                    self.files_meta[file_id]["updated_by"] = operator_id
                await self._persist_file(file_id)

                return self.files_meta[file_id]

            except Exception as e:
                logger.error(f"Indexing failed for {file_id}: {e}")
                self.files_meta[file_id]["status"] = FileStatus.ERROR_INDEXING
                self.files_meta[file_id]["error"] = str(e)
                self.files_meta[file_id]["updated_at"] = utc_isoformat()
                if operator_id:
                    self.files_meta[file_id]["updated_by"] = operator_id
                await self._persist_file(file_id)
                raise

            finally:
                # Remove from processing queue
                self._remove_from_processing_queue(file_id)

    async def update_content(self, db_id: str, file_ids: list[str], params: dict | None = None) -> list[dict]:
        """更新内容 - 根据file_ids重新解析文件并更新向量库"""
        if db_id not in self.databases_meta:
            raise ValueError(f"Database {db_id} not found")

        db_write_lock = await self._get_db_write_lock(db_id)
        async with db_write_lock:
            rag = await self._get_lightrag_instance(db_id)
            if not rag:
                raise ValueError(f"Failed to get LightRAG instance for {db_id}")

            # 处理默认参数
            if params is None:
                params = {}
            processed_items_info = []

            for file_id in file_ids:
                # 从元数据中获取文件信息
                if file_id not in self.files_meta:
                    logger.warning(f"File {file_id} not found in metadata, skipping")
                    continue

                file_meta = self.files_meta[file_id]
                file_path = file_meta.get("path")

                if not file_path:
                    logger.warning(f"File path not found for {file_id}, skipping")
                    continue

                # 添加到处理队列
                self._add_to_processing_queue(file_id)

                try:
                    # 更新状态为处理中
                    resolved_params = resolve_chunk_processing_params(
                        kb_additional_params=self.databases_meta.get(db_id, {}).get("metadata"),
                        file_processing_params=self.files_meta[file_id].get("processing_params"),
                        request_params=params,
                    )
                    self.files_meta[file_id]["processing_params"] = resolved_params
                    self.files_meta[file_id]["status"] = "processing"
                    await self._persist_file(file_id)

                    # 重新解析文件为 markdown
                    params["image_bucket"] = "public"
                    params["image_prefix"] = f"{db_id}/kb-images"
                    markdown_content = await Parser.aparse(source=file_path, params=params)
                    markdown_content_lines = markdown_content[:100].replace("\n", " ")
                    logger.info(f"Markdown content: {markdown_content_lines}...")
                    filename = file_meta.get("filename") or file_id
                    chunks = chunk_markdown(markdown_content, file_id, filename, resolved_params)
                    chunk_input, split_by_character, split_by_character_only = self._prepare_lightrag_insert_payload(
                        chunks
                    )
                    if not chunk_input:
                        chunk_input = markdown_content

                    # 先删除现有的 LightRAG 数据（仅删除chunks，保留元数据）
                    await self.delete_file_chunks_only(db_id, file_id)

                    # 使用 LightRAG 重新插入内容
                    await rag.ainsert(
                        input=chunk_input,
                        ids=file_id,
                        file_paths=file_path,
                        split_by_character=split_by_character,
                        split_by_character_only=split_by_character_only,
                    )
                    await self._ensure_doc_processed(rag, file_id)

                    logger.info(f"Updated file {file_path} in LightRAG. Done.")

                    # 更新元数据状态
                    self.files_meta[file_id]["status"] = "done"
                    await self._persist_file(file_id)

                    # 从处理队列中移除
                    self._remove_from_processing_queue(file_id)

                    # 返回更新后的文件信息
                    updated_file_meta = file_meta.copy()
                    updated_file_meta["status"] = "done"
                    updated_file_meta["file_id"] = file_id
                    processed_items_info.append(updated_file_meta)

                except Exception as e:
                    error_msg = str(e)
                    logger.error(f"更新file {file_path} 失败: {error_msg}, {traceback.format_exc()}")
                    self.files_meta[file_id]["status"] = "failed"
                    self.files_meta[file_id]["error"] = error_msg
                    await self._persist_file(file_id)

                    # 从处理队列中移除
                    self._remove_from_processing_queue(file_id)

                    # 返回失败的文件信息
                    failed_file_meta = file_meta.copy()
                    failed_file_meta["status"] = "failed"
                    failed_file_meta["file_id"] = file_id
                    failed_file_meta["error"] = error_msg
                    processed_items_info.append(failed_file_meta)

            return processed_items_info

    async def aquery(self, query_text: str, db_id: str, agent_call: bool = False, **kwargs) -> str:
        """异步查询知识库"""
        rag = await self._get_lightrag_instance(db_id)
        if not rag:
            raise ValueError(f"Database {db_id} not found")

        try:
            # QueryParam 支持的参数列表
            valid_params = {
                "mode",
                "only_need_context",
                "only_need_prompt",
                "response_type",
                "stream",
                "top_k",
                "chunk_top_k",
                "max_entity_tokens",
                "max_relation_tokens",
                "max_total_tokens",
                "hl_keywords",
                "ll_keywords",
                "conversation_history",
                "history_turns",
                "model_func",
                "user_prompt",
                "enable_rerank",
                "include_references",
            }

            # 过滤 kwargs，只保留 QueryParam 支持的参数
            query_params = self._get_query_params(db_id)
            query_params = query_params | kwargs
            filtered_kwargs = {k: v for k, v in query_params.items() if k in valid_params}

            # 设置查询参数
            params_dict = {
                "mode": "mix",
                "only_need_context": True,
                "top_k": 10,
            } | filtered_kwargs
            param = QueryParam(**params_dict)

            # 执行查询
            response = await rag.aquery_data(query_text, param)
            logger.debug(f"Query response: {str(response)[:1000]}...")

            if agent_call:
                scope = query_params.get("retrieval_content_scope", "chunks")
                data = response.get("data", {}) or {}

                if scope == "chunks":
                    return data.get("chunks", [])

                result = {}
                if scope in ["graph", "all"]:
                    # 过滤掉无关信息，保留实体和关系的核心内容
                    exclude_keys = {"source_id", "file_path", "created_at"}

                    ents = data.get("entities", [])
                    rels = data.get("relationships", [])

                    result["entities"] = [{k: v for k, v in e.items() if k not in exclude_keys} for e in ents]
                    result["relationships"] = [{k: v for k, v in r.items() if k not in exclude_keys} for r in rels]
                    result["references"] = data.get("references", [])

                if scope == "all":
                    result["chunks"] = data.get("chunks", [])

                return result

            return response

        except Exception as e:
            logger.error(f"Query error: {e}, {traceback.format_exc()}")
            return ""

    async def delete_file_chunks_only(self, db_id: str, file_id: str) -> None:
        """仅删除文件的chunks数据，保留元数据（用于更新操作）"""
        rag = await self._get_lightrag_instance(db_id)
        if rag:
            try:
                # 使用 LightRAG 删除文档
                await rag.adelete_by_doc_id(file_id)
                logger.info(f"Deleted chunks for file {file_id} from LightRAG")
            except Exception as e:
                logger.error(f"Error deleting file {file_id} from LightRAG: {e}")
        # 注意：这里不删除 files_meta[file_id]，保留元数据用于后续操作

    async def delete_file(self, db_id: str, file_id: str) -> None:
        """删除文件（包括元数据）"""
        # 先删除 LightRAG 中的 chunks 数据
        await self.delete_file_chunks_only(db_id, file_id)

        # 删除文件记录
        if file_id in self.files_meta:
            del self.files_meta[file_id]
            from zixuetong.repositories.knowledge_file_repository import KnowledgeFileRepository

            await KnowledgeFileRepository().delete(file_id)

    async def get_file_basic_info(self, db_id: str, file_id: str) -> dict:
        """获取文件基本信息（仅元数据）"""
        if file_id not in self.files_meta:
            raise Exception(f"File not found: {file_id}")

        return {"meta": self.files_meta[file_id]}

    async def get_file_content(self, db_id: str, file_id: str) -> dict:
        """获取文件内容信息（chunks和lines）"""
        if file_id not in self.files_meta:
            raise Exception(f"File not found: {file_id}")

        # 使用 LightRAG 获取 chunks
        content_info = {"lines": []}

        # 添加超时保护，避免 LightRAG 实例初始化卡住
        try:
            rag = await asyncio.wait_for(
                self._get_lightrag_instance(db_id),
                timeout=30.0  # 30 秒超时
            )
        except asyncio.TimeoutError:
            logger.error(f"Timeout getting LightRAG instance for {db_id}")
            rag = None

        if rag:
            try:
                # 获取文档的所有 chunks
                # LightRAG v1.4+ 使用 JsonKVStorage，通过 _data 属性访问所有数据
                if hasattr(rag.text_chunks, "_data"):
                    all_chunks = dict(rag.text_chunks._data)
                else:
                    logger.warning("text_chunks does not have _data attribute, cannot get file content")
                    return content_info

                # 筛选属于该文档的 chunks
                doc_chunks = []
                for chunk_id, chunk_data in all_chunks.items():
                    if isinstance(chunk_data, dict) and chunk_data.get("full_doc_id") == file_id:
                        chunk_data["id"] = chunk_id
                        chunk_data["content_vector"] = []
                        doc_chunks.append(chunk_data)

                # 按 chunk_order_index 排序
                doc_chunks.sort(key=lambda x: x.get("chunk_order_index", 0))
                content_info["lines"] = doc_chunks

            except Exception as e:
                logger.error(f"Failed to get file content from LightRAG: {e}")
                content_info["lines"] = []

        # Try to read markdown content if available
        file_meta = self.files_meta[file_id]
        if file_meta.get("markdown_file"):
            try:
                # 添加超时保护，避免 MinIO 下载永久挂起
                content = await asyncio.wait_for(
                    self._read_markdown_from_minio(file_meta["markdown_file"]),
                    timeout=10.0  # 10 秒超时
                )
                content_info["content"] = content
            except asyncio.TimeoutError:
                logger.error(f"Timeout reading markdown file for {file_id}")
            except Exception as e:
                logger.error(f"Failed to read markdown file for {file_id}: {e}")

        return content_info

    async def get_file_info(self, db_id: str, file_id: str) -> dict:
        """获取文件完整信息（基本信息+内容信息）- 保持向后兼容"""
        if file_id not in self.files_meta:
            raise Exception(f"File not found: {file_id}")

        # 合并基本信息和内容信息
        basic_info = await self.get_file_basic_info(db_id, file_id)
        content_info = await self.get_file_content(db_id, file_id)

        return {**basic_info, **content_info}

    def get_query_params_config(self, db_id: str, **kwargs) -> dict:
        """获取 LightRAG 知识库的查询参数配置"""
        options = [
            {
                "key": "mode",
                "label": "检索模式",
                "type": "select",
                "default": "mix",
                "options": [
                    {"value": "local", "label": "Local", "description": "上下文相关信息"},
                    {"value": "global", "label": "Global", "description": "全局知识"},
                    {"value": "hybrid", "label": "Hybrid", "description": "本地和全局混合"},
                    {"value": "naive", "label": "Naive", "description": "基本搜索"},
                    {"value": "mix", "label": "Mix", "description": "知识图谱和向量检索混合"},
                ],
            },
            {
                "key": "only_need_context",
                "label": "只使用上下文",
                "type": "boolean",
                "default": True,
                "description": "只返回上下文，不生成回答",
            },
            {
                "key": "only_need_prompt",
                "label": "只使用提示",
                "type": "boolean",
                "default": False,
                "description": "只返回提示，不进行检索",
            },
            {
                "key": "top_k",
                "label": "TopK",
                "type": "number",
                "default": 10,
                "min": 1,
                "max": 100,
                "description": "返回的最大结果数量",
            },
            {
                "key": "retrieval_content_scope",
                "label": "传递给 LLM 的内容",
                "type": "select",
                "default": "chunks",
                "options": [
                    {"value": "chunks", "label": "仅 Chunks", "description": "仅返回文档片段"},
                    {"value": "graph", "label": "仅 Entity/Relation", "description": "仅返回知识图谱信息"},
                    {"value": "all", "label": "全部", "description": "返回文档片段和知识图谱信息"},
                ],
            },
        ]

        return {"type": "lightrag", "options": options}

    async def export_data(self, db_id: str, format: str = "csv", **kwargs) -> str:
        """
        使用 LightRAG 原生功能导出知识库数据。
        [注意] 此功能当前已禁用。
        """
        # TODO: 修复 LightRAG 库原生导出问题。
        # 在 lightrag 库修复此问题前，暂时禁用此功能。
        raise NotImplementedError("LightRAG 原生导出功能暂不可用，等待上游库修复。")

        # --- 以下为待修复后启用的代码 ---
        # logger.info(f"Exporting data for db_id {db_id} in format {format} with options {kwargs}")

        # rag = await self._get_lightrag_instance(db_id)
        # if not rag:
        #     raise ValueError(f"Failed to get LightRAG instance for {db_id}")

        # export_dir = os.path.join(self.work_dir, db_id, "exports")
        # os.makedirs(export_dir, exist_ok=True)

        # timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        # output_filename = f"export_{db_id}_{timestamp}.{format}"
        # output_filepath = os.path.join(export_dir, output_filename)

        # include_vectors = kwargs.get('include_vectors', False)

        # # 直接调用 lightrag 的异步导出功能
        # # 之前的测试表明 aexport_data 确实存在，并且 to_thread 会导致 loop 问题
        # await rag.aexport_data(
        #     output_path=output_filepath,
        #     file_format=format,
        #     include_vector_data=include_vectors
        # )

        # logger.info(f"Successfully created export file: {output_filepath}")
        # return output_filepath
