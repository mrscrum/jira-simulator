import "@testing-library/jest-dom/vitest";
import { vi } from "vitest";

// Mock Plotly components to avoid canvas/WebGL issues in jsdom
vi.mock("react-plotly.js/factory", () => ({
  __esModule: true,
  default: () => () => null,
}));
vi.mock("plotly.js-basic-dist-min", () => ({
  __esModule: true,
  default: {},
}));
