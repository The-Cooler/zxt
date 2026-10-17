import assert from 'node:assert/strict'

import { isIndexedWithoutGraph } from '../ingestionMode.js'

const run = () => {
  // 图谱未生成（快速入库）→ 显示「生成图谱」
  assert.equal(
    isIndexedWithoutGraph({ status: 'indexed', graph_status: 'pending' }, 'lightrag'),
    true
  )

  // 图谱生成失败同样需要重新提供入口
  assert.equal(
    isIndexedWithoutGraph({ status: 'indexed', graph_status: 'failed' }, 'lightrag'),
    true
  )

  // 图谱已生成 → 不再显示「生成图谱」
  assert.equal(
    isIndexedWithoutGraph({ status: 'indexed', graph_status: 'built' }, 'lightrag'),
    false
  )

  // processing_params 里的 index_mode 是历史快照，不能作为判断依据：
  // 复用旧参数做快速入库后，快照仍是 standard，但图谱并没有重新生成。
  assert.equal(
    isIndexedWithoutGraph(
      {
        status: 'indexed',
        graph_status: 'pending',
        processing_params: { index_mode: 'standard' }
      },
      'lightrag'
    ),
    true
  )

  // 入库状态被回退成 error_indexing，但向量表里仍有 chunk：
  // 入库实际已完成，应该提供「生成图谱」而不是「重试入库」。
  assert.equal(
    isIndexedWithoutGraph(
      { status: 'error_indexing', graph_status: 'pending', vector_chunk_count: 34 },
      'lightrag'
    ),
    true
  )

  // 未入库的文件不提供图谱入口
  assert.equal(
    isIndexedWithoutGraph({ status: 'parsed', graph_status: 'pending' }, 'lightrag'),
    false
  )

  // 非 LightRAG 知识库没有该入口
  assert.equal(
    isIndexedWithoutGraph({ status: 'indexed', graph_status: 'pending' }, 'other'),
    false
  )

  console.log('ingestionMode isIndexedWithoutGraph: all assertions passed')
}

run()
