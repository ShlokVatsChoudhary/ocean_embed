// jsdom implements neither ResizeObserver nor canvas, and the map and profile panels
// depend on both. These stubs are deliberately dumb: the tests assert that the panels
// mount and receive the right data, not that pixels are correct.
import { vi } from 'vitest'

globalThis.ResizeObserver = class {
  observe() {}
  unobserve() {}
  disconnect() {}
}

globalThis.matchMedia = globalThis.matchMedia || (() => ({
  matches: false, addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {},
}))

HTMLCanvasElement.prototype.getContext = () => ({
  setTransform() {}, clearRect() {}, fillRect() {}, beginPath() {}, moveTo() {}, lineTo() {},
  stroke() {}, fill() {}, save() {}, restore() {}, rect() {}, clip() {}, arc() {},
  measureText: (t) => ({ width: String(t).length * 6 }), fillText() {}, strokeText() {},
  createLinearGradient: () => ({ addColorStop() {} }),
  set fillStyle(v) {}, get fillStyle() { return '#000' },
  set strokeStyle(v) {}, get strokeStyle() { return '#000' },
  set lineWidth(v) {}, get lineWidth() { return 1 },
  set font(v) {}, get font() { return '10px sans-serif' },
  set globalAlpha(v) {}, get globalAlpha() { return 1 },
  set textAlign(v) {}, get textAlign() { return 'left' },
  set textBaseline(v) {}, get textBaseline() { return 'top' },
})

if (!window.requestAnimationFrame) {
  window.requestAnimationFrame = (cb) => setTimeout(() => cb(Date.now()), 0)
}
