import { vi } from 'vitest';

vi.mock('chart.js', () => {
  class Chart {
    static register() {}
    constructor() {
      this.data = { labels: [], datasets: [] };
      this.options = {};
      this.canvas = null;
    }
    destroy() {}
    update() {}
    getDatasetMeta() {
      return { data: [] };
    }
  }
  return { Chart, registerables: [] };
});

HTMLCanvasElement.prototype.getContext = function getContext() {
  const canvas = this;
  const noop = () => {};
  return {
    canvas,
    measureText: () => ({ width: 0 }),
    getImageData: () => ({ data: [], width: 0, height: 0 }),
    createLinearGradient: () => ({ addColorStop: noop }),
    createRadialGradient: () => ({ addColorStop: noop }),
    save: noop,
    restore: noop,
    clearRect: noop,
    fillRect: noop,
    strokeRect: noop,
    beginPath: noop,
    closePath: noop,
    moveTo: noop,
    lineTo: noop,
    arc: noop,
    fill: noop,
    stroke: noop,
    clip: noop,
    scale: noop,
    rotate: noop,
    translate: noop,
    setTransform: noop,
    transform: noop,
    drawImage: noop,
    putImageData: noop,
    setLineDash: noop,
    getLineDash: () => [],
    fillText: noop,
    strokeText: noop,
    rect: noop,
  };
};