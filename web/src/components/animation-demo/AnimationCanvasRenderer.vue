<template>
  <div class="animation-renderer">
    <svg class="animation-stage" viewBox="0 0 100 100" role="img" :aria-label="scene.title">
      <defs>
        <marker
          id="animation-arrow"
          markerWidth="6"
          markerHeight="6"
          refX="5"
          refY="3"
          orient="auto"
          markerUnits="strokeWidth"
        >
          <path d="M0,0 L6,3 L0,6 Z" class="arrow-marker" />
        </marker>
      </defs>

      <line
        v-for="connection in visibleConnections"
        :key="connection.key"
        :x1="connection.from.x"
        :y1="connection.from.y"
        :x2="connection.to.x"
        :y2="connection.to.y"
        class="connection-line"
        marker-end="url(#animation-arrow)"
      />

      <g
        v-for="element in scene.elements"
        :key="element.id"
        class="stage-element"
        :class="[elementClass(element), { highlighted: isHighlighted(element.id) }]"
        :style="{ opacity: isVisible(element.id) ? 1 : 0 }"
      >
        <circle
          v-if="element.type === 'circle'"
          :cx="centerX(element)"
          :cy="centerY(element)"
          :r="Math.max(element.width, element.height) / 2"
        />
        <rect
          v-else-if="element.type !== 'text'"
          :x="element.x"
          :y="element.y"
          :width="element.width"
          :height="element.height"
          rx="2"
        />
        <text
          :x="centerX(element)"
          :y="element.type === 'text' ? element.y : centerY(element)"
          :class="{ caption: element.type === 'text' }"
          text-anchor="middle"
          dominant-baseline="middle"
        >
          {{ element.label }}
        </text>
      </g>
    </svg>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  scene: {
    type: Object,
    required: true
  },
  sceneTime: {
    type: Number,
    default: 0
  }
})

const activeActions = computed(() =>
  (props.scene.actions || []).filter((action) => props.sceneTime >= Number(action.at || 0))
)

const centerX = (element) => Number(element.x || 0) + Number(element.width || 0) / 2
const centerY = (element) => Number(element.y || 0) + Number(element.height || 0) / 2

const elementClass = (element) => {
  if (element.type === 'text') return 'element-text'
  if (element.color === 'accent') return 'element-accent'
  if (element.color === 'muted') return 'element-muted'
  return 'element-primary'
}

const isVisible = (elementId) => {
  const fadeActions = (props.scene.actions || []).filter(
    (action) => action.type === 'fade_in' && action.element_id === elementId
  )
  if (fadeActions.length === 0) return true
  return fadeActions.some((action) => props.sceneTime >= Number(action.at || 0))
}

const isHighlighted = (elementId) =>
  (props.scene.actions || []).some((action) => {
    if (action.type !== 'highlight' || action.element_id !== elementId) return false
    const start = Number(action.at || 0)
    return props.sceneTime >= start && props.sceneTime <= start + Number(action.duration || 0)
  })

const elementById = computed(() => {
  const result = new Map()
  for (const element of props.scene.elements || []) {
    result.set(element.id, element)
  }
  return result
})

const visibleConnections = computed(() =>
  activeActions.value
    .filter((action) => action.type === 'connect' && action.element_id && action.target_id)
    .map((action) => {
      const from = elementById.value.get(action.element_id)
      const to = elementById.value.get(action.target_id)
      if (!from || !to) return null
      return {
        key: `${action.element_id}-${action.target_id}-${action.at}`,
        from: { x: centerX(from), y: centerY(from) },
        to: { x: centerX(to), y: centerY(to) }
      }
    })
    .filter(Boolean)
)
</script>

<style lang="less" scoped>
.animation-renderer {
  width: 100%;
  aspect-ratio: 16 / 9;
  min-height: 220px;
  border: 1px solid var(--gray-150);
  border-radius: 8px;
  background: var(--gray-10);
  overflow: hidden;
}

.animation-stage {
  width: 100%;
  height: 100%;
  display: block;
}

.stage-element {
  transition:
    opacity 0.2s ease,
    filter 0.2s ease;

  rect,
  circle {
    stroke-width: 0.7;
  }

  text {
    fill: var(--color-text);
    font-size: 3.6px;
    font-weight: 600;
    letter-spacing: 0;
    pointer-events: none;
  }

  .caption {
    fill: var(--color-text-secondary);
    font-size: 3px;
    font-weight: 500;
  }
}

.element-primary {
  rect,
  circle {
    fill: var(--main-50);
    stroke: var(--main-500);
  }
}

.element-accent {
  rect,
  circle {
    fill: var(--color-accent-50);
    stroke: var(--color-accent-700);
  }
}

.element-muted {
  rect,
  circle {
    fill: var(--gray-50);
    stroke: var(--gray-300);
  }
}

.element-text {
  text {
    fill: var(--color-text-secondary);
  }
}

.highlighted {
  filter: drop-shadow(0 0 4px rgba(36, 131, 154, 0.45));

  rect,
  circle {
    stroke-width: 1.2;
  }
}

.connection-line {
  stroke: var(--main-500);
  stroke-width: 0.8;
  stroke-linecap: round;
}

.arrow-marker {
  fill: var(--main-500);
}

@media (max-width: 767px) {
  .animation-renderer {
    min-height: 180px;
  }
}
</style>
