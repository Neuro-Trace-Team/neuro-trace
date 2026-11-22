import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Modal from "../src/components/Modal";
import DataTable from "../src/components/DataTable";

describe("shared controls", () => {
  it("focuses the modal, traps focus, closes with Escape and restores focus", async () => {
    const user = userEvent.setup();
    const close = vi.fn();
    const trigger = document.createElement("button");
    document.body.appendChild(trigger);
    trigger.focus();
    const view = render(<Modal title="Details" onClose={close}><button>Action</button></Modal>);
    expect(screen.getByRole("dialog", { name: "Details" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Close dialog" })).toHaveFocus();
    await user.tab({ shift: true });
    expect(screen.getByRole("button", { name: "Action" })).toHaveFocus();
    await user.keyboard("{Escape}");
    expect(close).toHaveBeenCalledOnce();
    view.unmount();
    expect(trigger).toHaveFocus();
    trigger.remove();
  });

  it("searches, sorts and paginates local rows", async () => {
    const user = userEvent.setup();
    render(<DataTable columns={["Name"]} rows={[["Charlie"], ["Alice"], ["Bob"]]} pageSize={2} />);
    expect(screen.getByText("Charlie")).toBeInTheDocument();
    expect(screen.queryByText("Bob")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Name" }));
    expect(screen.getByText("Alice")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Next page" }));
    expect(screen.getByText("Charlie")).toBeInTheDocument();
    await user.type(screen.getByRole("searchbox", { name: "Search" }), "bob");
    expect(screen.getByText("Bob")).toBeInTheDocument();
    expect(screen.queryByText("Alice")).not.toBeInTheDocument();
  });

  it("delegates server sorting and paging", async () => {
    const user = userEvent.setup();
    const sort = vi.fn();
    const page = vi.fn();
    render(<DataTable columns={["Name"]} rows={[["Alice"]]} currentPage={1} pageSize={1} totalCount={2} onPageChange={page} sortableColumns={{ Name: "name" }} onSortChange={sort} />);
    await user.click(screen.getByRole("button", { name: "Name" }));
    expect(sort).toHaveBeenCalledWith("name", "asc");
    await user.click(screen.getByRole("button", { name: "Next page" }));
    expect(page).toHaveBeenCalledWith(2);
  });
});
