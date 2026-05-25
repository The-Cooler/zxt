import assert from 'node:assert/strict'

import { isIndexedWithoutGraph } from '../ingestionMode.js'

const run = () => {
  assert.equal(
    isIndexedWithoutGraph(
      {
        status: 'indexed',
        processing_params: { index_mode: 'fast' }
      },
      'lightrag'
    ),
    true
  )

  assert.equal(
    isIndexedWithoutGraph(
      {
        status: 'indexed',
        processing_params: { index_mode: 'standard' }
      },
      'lightrag'
    ),
    false
  )

  assert.equal(
    isIndexedWithoutGraph(
      {
        status: 'parsed',
        processing_params: { index_mode: 'fast' }
      },
      'lightrag'
    ),
    false
  )

  assert.equal(
    isIndexedWithoutGraph(
      {
        status: 'indexed',
        processing_params: { index_mode: 'fast' }
      },
      'other'
    ),
    false
  )

  console.log('ingestionMode isIndexedWithoutGraph: all assertions passed')
}

run()
