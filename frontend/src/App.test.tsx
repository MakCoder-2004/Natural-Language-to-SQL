import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import App from "./App";

describe("App", () => {
  it("renders the foundation shell", () => {
    render(<App />);

    expect(screen.getByRole("heading", { name: /ask your postgresql data/i })).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(/foundation services/i);
  });
});
