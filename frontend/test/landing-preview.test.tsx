import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { InterfacePreview } from "@/components/landing/interface-preview";

describe("Landing interface preview", () => {
  it("is labelled as example data and never presented as a real result", () => {
    render(<InterfacePreview />);
    const figure = screen.getByRole("figure", { name: /example data, not a real verification result/ });
    expect(within(figure).getByText("Example data")).toBeInTheDocument();
    expect(within(figure).getByText(/not a real result/)).toBeInTheDocument();
  });

  it("renders the real evidence card without linking to a document that does not exist", () => {
    render(<InterfacePreview />);
    const card = screen.getByRole("article", { name: "Evidence P1" });
    expect(within(card).getByText(/Verified excerpt/)).toBeInTheDocument();
    expect(within(card).getByText(/AI assessment/)).toBeInTheDocument();
    expect(within(card).queryByRole("link", { name: /View in document/ })).toBeNull();
  });
});
