/* eslint-disable @typescript-eslint/unbound-method -- detecting missing methods, not calling them */
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

afterEach(cleanup);

// jsdom lacks these; a real browser check covers the native behaviour.
HTMLDialogElement.prototype.showModal = function (this: HTMLDialogElement) {
  this.open = true;
  this.querySelector<HTMLElement>("button, input")?.focus();
};
HTMLDialogElement.prototype.close = function (this: HTMLDialogElement) {
  this.open = false;
};
window.matchMedia ??= vi.fn().mockReturnValue({
  matches: false,
  addEventListener: () => undefined,
  removeEventListener: () => undefined,
});
