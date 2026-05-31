"use client";

import { useState } from "react";

import { Check, Copy } from "lucide-react";

import { Button } from "@/components/ui/button";

type OneClipboardProps = {
  text: string;
  label?: string;
  copiedLabel?: string;
};

export function OneClipboard({ text, label = "复制", copiedLabel = "已复制" }: OneClipboardProps) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  }

  return (
    <Button className="h-7 gap-1.5 px-2 text-xs" onClick={handleCopy} type="button" variant="outline">
      {copied ? <Check className="size-4 text-emerald-500" /> : <Copy className="size-4" />}
      <span>{copied ? copiedLabel : label}</span>
    </Button>
  );
}
