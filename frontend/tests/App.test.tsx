import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import App from "../src/App";

vi.mock("../src/lib/api", () => ({
  fetchTeams: vi.fn().mockResolvedValue([]),
}));

afterEach(cleanup);

test("renders sidebar and create team prompt", async () => {
  render(<App />);
  expect(await screen.findByTestId("sidebar")).toBeInTheDocument();
  expect(
    screen.getByText("Create a team to get started"),
  ).toBeInTheDocument();
});

test("renders add team button", async () => {
  render(<App />);
  expect(await screen.findByTestId("add-team-btn")).toBeInTheDocument();
});
