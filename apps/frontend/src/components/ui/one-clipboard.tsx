"use client";

import { useState } from "react";

import { Check, Copy } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";

type OneClipboardProps = {
  text: string;
  label?: string;
  copiedLabel?: string;
};

async function copyToClipboard(text: string): Promise<boolean> {
  if (!text) return false;

  if (navigator.clipboard && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      // Fall through to textarea method
    }
  }

  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.style.position = "fixed";
  textarea.style.left = "-9999px";
  textarea.style.top = "-9999px";
  document.body.appendChild(textarea);
  textarea.focus();
  textarea.select();

  try {
    const success = document.execCommand("copy");
    return success;
  } catch {
    return false;
  } finally {
    document.body.removeChild(textarea);
  }
}

export function OneClipboard({ text, label = "复制", copiedLabel = "已复制" }: OneClipboardProps) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    if (!text) {
      toast.error("复制内容为空");
      return;
    }

    const success = await copyToClipboard(text);
    if (success) {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } else {
      toast.error("复制失败，请手动复制");
    }
  }

  return (
    <Button className="h-7 gap-1.5 px-2 text-xs" onClick={handleCopy} type="button" variant="outline">
      {copied ? <Check className="size-4 text-emerald-500" /> : <Copy className="size-4" />}
      <span>{copied ? copiedLabel : label}</span>
    </Button>
  );
}
