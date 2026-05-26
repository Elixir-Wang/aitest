"use client";

import React from "react";
import { Sparkle } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";

import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { cn } from "@/lib/utils";

const SPEED_FACTOR = 1;
const FORM_WIDTH = 360;
const FORM_HEIGHT = 220;

type AiEditInputProps = {
  disabled?: boolean;
  loading?: boolean;
  label?: string;
  title?: string;
  placeholder?: string;
  onSubmit: (instruction: string) => Promise<void> | void;
};

export function AiEditInput({
  disabled = false,
  loading = false,
  label = "AI修改",
  title = "AI文档修改",
  placeholder = "描述你希望如何修改当前文档...",
  onSubmit,
}: AiEditInputProps) {
  const wrapperRef = React.useRef<HTMLDivElement>(null);
  const textareaRef = React.useRef<HTMLTextAreaElement | null>(null);
  const [showForm, setShowForm] = React.useState(false);
  const [message, setMessage] = React.useState("");

  const triggerClose = React.useCallback(() => {
    setShowForm(false);
    textareaRef.current?.blur();
  }, []);

  const triggerOpen = React.useCallback(() => {
    if (disabled) {
      return;
    }
    setShowForm(true);
    setTimeout(() => textareaRef.current?.focus());
  }, [disabled]);

  React.useEffect(() => {
    function clickOutsideHandler(e: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node) && showForm && !loading) {
        triggerClose();
      }
    }
    document.addEventListener("mousedown", clickOutsideHandler);
    return () => document.removeEventListener("mousedown", clickOutsideHandler);
  }, [showForm, loading, triggerClose]);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const instruction = message.trim();
    if (!instruction || loading) {
      return;
    }
    setMessage("");
    triggerClose();
    await onSubmit(instruction);
  }

  function handleKeys(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Escape" && !loading) {
      triggerClose();
    }
  }

  return (
    <div className="relative flex items-center" ref={wrapperRef}>
      <Button disabled={disabled} onClick={triggerOpen} type="button">
        {loading ? <Spinner className="size-4" /> : <Sparkle className="size-4" />}
        {loading ? "AI修改中" : label}
      </Button>

      <AnimatePresence>
        {showForm ? (
          <motion.form
            animate={{ opacity: 1, scale: 1, y: 0 }}
            className="absolute top-[calc(100%+8px)] right-0 z-50 flex flex-col rounded-[14px] border bg-background p-3 shadow-lg"
            exit={{ opacity: 0, scale: 0.98, y: -4 }}
            initial={{ opacity: 0, scale: 0.98, y: -4 }}
            onSubmit={handleSubmit}
            style={{ width: FORM_WIDTH, height: FORM_HEIGHT }}
            transition={{
              type: "spring",
              stiffness: 550 / SPEED_FACTOR,
              damping: 45,
              mass: 0.7,
            }}
          >
            <div className="flex items-center justify-center pb-2 text-center font-medium text-foreground text-sm">
              {title}
            </div>
            <textarea
              className="min-h-0 flex-1 resize-none rounded-md border bg-background p-3 text-sm outline-0 focus-visible:ring-2 focus-visible:ring-ring"
              disabled={loading}
              name="message"
              onChange={(event) => setMessage(event.target.value)}
              onKeyDown={handleKeys}
              placeholder={placeholder}
              ref={textareaRef}
              required
              spellCheck={false}
              value={message}
            />
            <div className="mt-3 flex justify-center">
              <button
                className="rounded-full bg-gradient-to-r from-blue-400 via-blue-600 to-violet-600 px-5 py-2 font-semibold text-sm text-white shadow-sm transition-transform hover:scale-105 active:scale-100 disabled:cursor-not-allowed disabled:opacity-60"
                disabled={loading}
                type="submit"
              >
                {loading ? "修改中" : "AI修改"}
              </button>
            </div>
          </motion.form>
        ) : null}
      </AnimatePresence>
    </div>
  );
}
