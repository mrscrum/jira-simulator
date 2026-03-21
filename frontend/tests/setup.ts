import "@testing-library/jest-dom/vitest";
import { vi } from "vitest";

// Mock react-plotly.js to avoid canvas/WebGL issues in jsdom
vi.mock("react-plotly.js", () => ({
  __esModule: true,
  default: () => null,
}));
