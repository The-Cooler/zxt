import assert from 'node:assert/strict'

import { buildWebReaderTree } from '../webReaderTree.js'

const run = () => {
  const tree = buildWebReaderTree({
    rootPage: {
      final_url: 'https://example.com',
      title: 'Root'
    },
    discoveredMap: {
      'https://example.com/a': {
        url: 'https://example.com/a',
        title: 'A',
        parents: ['https://example.com'],
        depth: 1
      },
      'https://example.com/a/child': {
        url: 'https://example.com/a/child',
        title: 'A child',
        parents: ['https://example.com/a'],
        depth: 2
      },
      'https://example.com/orphan': {
        url: 'https://example.com/orphan',
        title: 'Orphan',
        parents: ['https://example.com/missing'],
        depth: 2
      }
    }
  })

  assert.equal(tree.length, 1)
  assert.equal(tree[0].key, 'https://example.com')
  assert.equal(tree[0].children.length, 2)
  assert.equal(tree[0].children[0].key, 'https://example.com/a')
  assert.equal(tree[0].children[0].children[0].key, 'https://example.com/a/child')
  assert.equal(tree[0].children[1].key, 'https://example.com/orphan')

  console.log('webReaderTree buildWebReaderTree: all assertions passed')
}

run()
