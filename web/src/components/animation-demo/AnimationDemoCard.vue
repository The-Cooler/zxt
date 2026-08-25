<template>
  <section class="animation-demo-card">
    <div class="animation-demo-header">
      <div class="animation-demo-title-group">
        <Film size="16" class="animation-demo-icon" />
        <div class="animation-demo-title-text">
          <h3>{{ demo.title }}</h3>
          <p>{{ sceneLabel }}</p>
        </div>
      </div>
      <div class="animation-demo-duration">{{ formattedTime }} / {{ totalDurationLabel }}</div>
    </div>

    <AnimationCanvasRenderer :scene="currentScene" :scene-time="sceneTime" />

    <div class="animation-demo-caption">
      <strong>{{ currentScene.title }}</strong>
      <span>{{ currentScene.narration }}</span>
    </div>

    <div class="animation-demo-progress" aria-hidden="true">
      <div class="animation-demo-progress-bar" :style="{ width: `${progressPercent}%` }"></div>
    </div>

    <div class="animation-demo-toolbar">
      <button type="button" class="icon-button" :aria-label="playing ? '暂停' : '播放'" @click="togglePlaying">
        <Pause v-if="playing" size="16" />
        <Play v-else size="16" />
      </button>
      <button type="button" class="icon-button" aria-label="重播" @click="restart">
        <RotateCcw size="16" />
      </button>
      <div class="speed-control" aria-label="播放速度">
        <button
          v-for="option in speedOptions"
          :key="option"
          type="button"
          :class="{ active: speed === option }"
          @click="speed = option"
        >
          {{ option }}x
        </button>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { Film, Pause, Play, RotateCcw } from 'lucide-vue-next'
import AnimationCanvasRenderer from './AnimationCanvasRenderer.vue'

const props = defineProps({
  demo: {
    type: Object,
    required: true
  }
})

const speedOptions = [0.75, 1, 1.5]
const playing = ref(false)
const currentTime = ref(0)
const speed = ref(1)
let frameId = null
let lastFrameTime = 0

const scenes = computed(() => (Array.isArray(props.demo?.scenes) ? props.demo.scenes : []))
const totalDuration = computed(() =>
  Math.max(
    scenes.value.reduce((sum, scene) => sum + Number(scene.duration_seconds || 0), 0),
    1
  )
)

const sceneRanges = computed(() => {
  let cursor = 0
  return scenes.value.map((scene, index) => {
    const start = cursor
    const duration = Number(scene.duration_seconds || 1)
    cursor += duration
    return { scene, index, start, end: cursor }
  })
})

const currentRange = computed(() => {
  return (
    sceneRanges.value.find((range) => currentTime.value >= range.start && currentTime.value < range.end) ||
    sceneRanges.value[sceneRanges.value.length - 1] || {
      scene: { title: '动画演示', narration: '', elements: [], actions: [], duration_seconds: 1 },
      index: 0,
      start: 0,
      end: 1
    }
  )
})

const currentScene = computed(() => currentRange.value.scene)
const sceneTime = computed(() => Math.max(0, currentTime.value - currentRange.value.start))
const progressPercent = computed(() => Math.min(100, (currentTime.value / totalDuration.value) * 100))
const sceneLabel = computed(() => `第 ${currentRange.value.index + 1} / ${Math.max(scenes.value.length, 1)} 段`)
const formattedTime = computed(() => `${Math.floor(currentTime.value)}s`)
const totalDurationLabel = computed(() => `${Math.floor(totalDuration.value)}s`)

const tick = (timestamp) => {
  if (!playing.value) return
  if (!lastFrameTime) lastFrameTime = timestamp
  const delta = ((timestamp - lastFrameTime) / 1000) * speed.value
  lastFrameTime = timestamp
  currentTime.value = Math.min(totalDuration.value, currentTime.value + delta)
  if (currentTime.value >= totalDuration.value) {
    playing.value = false
    return
  }
  frameId = requestAnimationFrame(tick)
}

const togglePlaying = () => {
  if (currentTime.value >= totalDuration.value) {
    currentTime.value = 0
  }
  playing.value = !playing.value
}

const restart = () => {
  currentTime.value = 0
  lastFrameTime = 0
  playing.value = true
}

watch(playing, (value) => {
  if (frameId) {
    cancelAnimationFrame(frameId)
    frameId = null
  }
  lastFrameTime = 0
  if (value) {
    frameId = requestAnimationFrame(tick)
  }
})

onBeforeUnmount(() => {
  if (frameId) cancelAnimationFrame(frameId)
})
</script>

<style lang="less" scoped>
.animation-demo-card {
  width: 100%;
  margin: 12px 0;
  padding: 12px;
  border: 1px solid var(--gray-150);
  border-radius: 8px;
  background: var(--gray-0);
}

.animation-demo-header,
.animation-demo-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.animation-demo-header {
  margin-bottom: 10px;
}

.animation-demo-title-group {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.animation-demo-icon {
  color: var(--main-600);
  flex-shrink: 0;
}

.animation-demo-title-text {
  min-width: 0;

  h3,
  p {
    margin: 0;
    letter-spacing: 0;
  }

  h3 {
    color: var(--color-text);
    font-size: 14px;
    font-weight: 600;
    line-height: 20px;
  }

  p {
    color: var(--color-text-secondary);
    font-size: 12px;
    line-height: 18px;
  }
}

.animation-demo-duration {
  color: var(--color-text-tertiary);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.animation-demo-caption {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-height: 48px;
  margin: 10px 0 8px;
  color: var(--color-text-secondary);
  font-size: 13px;
  line-height: 20px;

  strong {
    color: var(--color-text);
    font-size: 13px;
  }
}

.animation-demo-progress {
  height: 4px;
  margin-bottom: 10px;
  border-radius: 999px;
  background: var(--gray-100);
  overflow: hidden;
}

.animation-demo-progress-bar {
  height: 100%;
  border-radius: inherit;
  background: var(--main-500);
  transition: width 0.12s linear;
}

.icon-button {
  width: 36px;
  height: 36px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--gray-150);
  border-radius: 8px;
  background: var(--gray-0);
  color: var(--color-text);
  cursor: pointer;
  transition: all 0.2s ease;

  &:hover {
    border-color: var(--main-300);
    color: var(--main-700);
    background: var(--main-30);
  }
}

.speed-control {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px;
  border: 1px solid var(--gray-150);
  border-radius: 8px;
  background: var(--gray-25);

  button {
    min-width: 44px;
    height: 32px;
    border: 0;
    border-radius: 6px;
    background: transparent;
    color: var(--color-text-secondary);
    cursor: pointer;
    font-size: 12px;
    font-variant-numeric: tabular-nums;

    &.active {
      background: var(--gray-0);
      color: var(--main-700);
      border: 1px solid var(--main-200);
    }
  }
}

@media (max-width: 767px) {
  .animation-demo-header,
  .animation-demo-toolbar {
    align-items: flex-start;
    flex-direction: column;
  }

  .speed-control {
    width: 100%;

    button {
      flex: 1;
    }
  }
}
</style>
