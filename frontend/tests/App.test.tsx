import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import App from "../src/App";

test("renders the coming soon heading", () => {
  render(<App />);
  expect(
    screen.getByText("Jira Team Simulator — coming soon"),
  ).toBeDefined();
});
