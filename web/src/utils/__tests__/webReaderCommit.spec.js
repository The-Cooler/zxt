import assert from 'node:assert/strict'

import {
  buildWebReaderCommitPayload,
  getSuccessfulWebReaderItems,
  getUncleanedWebReaderItems,
  findWebReaderItemBySessionId
} from '../webReaderCommit.js'

const run = () => {
  const items = [
    {
      status: 'success',
      data: { session_id: 'session-a' },
      cleanedPages: [{ source_url: 'https://example.com/a' }],
      indexParams: { index_mode: 'standard', chunk_size: 1000 }
    },
    {
      status: 'success',
      data: { session_id: 'session-b' },
      cleanedPages: [],
      indexParams: { index_mode: 'fast' }
    },
    {
      status: 'error',
      data: { session_id: 'session-c' },
      cleanedPages: [{ source_url: 'https://example.com/c' }]
    }
  ]

  assert.deepEqual(
    getSuccessfulWebReaderItems(items).map((item) => item.data.session_id),
    ['session-a', 'session-b']
  )
  assert.deepEqual(
    getUncleanedWebReaderItems(getSuccessfulWebReaderItems(items)).map(
      (item) => item.data.session_id
    ),
    ['session-b']
  )
  assert.equal(findWebReaderItemBySessionId(items, 'session-a'), items[0])
  assert.equal(findWebReaderItemBySessionId(items, 'missing'), null)

  assert.deepEqual(
    buildWebReaderCommitPayload(items[0], {
      autoIndex: true,
      parentId: 'folder-1'
    }),
    {
      auto_index: true,
      parent_id: 'folder-1',
      chunk_params: { index_mode: 'standard', chunk_size: 1000 }
    }
  )

  console.log('webReaderCommit helpers: all assertions passed')
}

run()
