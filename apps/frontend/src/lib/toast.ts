"use client";

import { toast as sonnerToast } from "sonner";

import { persistDisplayedError } from "@/lib/error-feedback";

function persistentErrorToast(
  message: Parameters<typeof sonnerToast.error>[0],
  options?: Parameters<typeof sonnerToast.error>[1],
) {
  void persistDisplayedError(message, options);
  return sonnerToast.error(message, options);
}

export const toast = Object.assign((...args: Parameters<typeof sonnerToast>) => sonnerToast(...args), sonnerToast, {
  error: persistentErrorToast,
}) as typeof sonnerToast;
