"use client";

import { useMemo, useState } from "react";

import { Pencil, X } from "lucide-react";

import { MarkdownPreview } from "@/components/ai-testing/markdown-preview";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

type StandardMarkdownEditorProps = {
  className?: string;
  content: string;
  onChange: (content: string) => void;
};

type MarkdownBlock =
  | { text: string; type: "paragraph" }
  | { level: number; text: string; type: "heading" }
  | { items: string[]; ordered: boolean; type: "list" }
  | { content: string; type: "blockquote" }
  | { content: string; type: "source" };

export function StandardMarkdownEditor({ className, content, onChange }: StandardMarkdownEditorProps) {
  const blocks = useMemo(() => parseMarkdownBlocks(content), [content]);

  function updateBlock(index: number, nextBlock: MarkdownBlock) {
    const nextBlocks = blocks.map((block, blockIndex) => (blockIndex === index ? nextBlock : block));
    onChange(serializeMarkdownBlocks(nextBlocks));
  }

  if (!blocks.length) {
    return (
      <article className={cn("markdown-preview requirement-markdown-editor", className)}>
        <EditableText
          className="requirement-markdown-editor-empty"
          onCommit={(text) => onChange(text.trim())}
          placeholder="输入标准文件内容"
          tag="p"
          text=""
        />
      </article>
    );
  }

  return (
    <article className={cn("markdown-preview requirement-document-preview requirement-markdown-editor", className)}>
      {blocks.map((block, index) => (
        <EditableBlock block={block} index={index} key={getBlockKey(block)} onChange={updateBlock} />
      ))}
    </article>
  );
}

function EditableBlock({
  block,
  index,
  onChange,
}: {
  block: MarkdownBlock;
  index: number;
  onChange: (index: number, block: MarkdownBlock) => void;
}) {
  if (block.type === "heading") {
    const tag = `h${Math.min(Math.max(block.level, 1), 6)}` as EditableTextTag;
    return (
      <EditableText
        onCommit={(text) => onChange(index, { ...block, text })}
        placeholder="标题"
        tag={tag}
        text={block.text}
      />
    );
  }

  if (block.type === "paragraph") {
    return (
      <EditableText
        onCommit={(text) => onChange(index, { ...block, text })}
        placeholder="正文"
        tag="p"
        text={block.text}
      />
    );
  }

  if (block.type === "blockquote") {
    return (
      <blockquote>
        <EditableText
          onCommit={(text) => onChange(index, { ...block, content: text })}
          placeholder="引用内容"
          tag="p"
          text={stripBlockquotePrefix(block.content)}
        />
      </blockquote>
    );
  }

  if (block.type === "list") {
    const ListTag = block.ordered ? "ol" : "ul";
    return (
      <ListTag>
        {block.items.map((item, itemIndex) => (
          <EditableText
            key={getListItemKey(item, itemIndex)}
            onCommit={(text) => {
              const items = block.items.map((currentItem, currentIndex) => (currentIndex === itemIndex ? text : currentItem));
              onChange(index, { ...block, items });
            }}
            placeholder="列表项"
            tag="li"
            text={item}
          />
        ))}
      </ListTag>
    );
  }

  return <SourceBlockEditor block={block} index={index} onChange={onChange} />;
}

type EditableTextTag = "h1" | "h2" | "h3" | "h4" | "h5" | "h6" | "li" | "p";

function EditableText({
  className,
  onCommit,
  placeholder,
  tag,
  text,
}: {
  className?: string;
  onCommit: (text: string) => void;
  placeholder: string;
  tag: EditableTextTag;
  text: string;
}) {
  const Tag = tag;

  return (
    <Tag
      className={cn("requirement-markdown-editor-text", className)}
      contentEditable
      data-placeholder={placeholder}
      onBlur={(event) => onCommit(event.currentTarget.innerText.trim())}
      suppressContentEditableWarning
    >
      {text}
    </Tag>
  );
}

function SourceBlockEditor({
  block,
  index,
  onChange,
}: {
  block: Extract<MarkdownBlock, { type: "source" }>;
  index: number;
  onChange: (index: number, block: MarkdownBlock) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(block.content);

  if (editing) {
    return (
      <div className="requirement-markdown-editor-source">
        <Textarea className="min-h-44 font-mono text-sm" onChange={(event) => setDraft(event.target.value)} value={draft} />
        <div className="mt-2 flex justify-end gap-2">
          <Button
            onClick={() => {
              setDraft(block.content);
              setEditing(false);
            }}
            size="sm"
            type="button"
            variant="outline"
          >
            <X className="size-4" />
            取消
          </Button>
          <Button
            onClick={() => {
              onChange(index, { ...block, content: draft.trim() });
              setEditing(false);
            }}
            size="sm"
            type="button"
          >
            保存块
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="requirement-markdown-editor-source">
      <div className="mb-2 flex justify-end">
        <Button onClick={() => setEditing(true)} size="sm" type="button" variant="outline">
          <Pencil className="size-4" />
          编辑源码块
        </Button>
      </div>
      <MarkdownPreview content={block.content} />
    </div>
  );
}

function parseMarkdownBlocks(markdown: string): MarkdownBlock[] {
  const lines = markdown.trim().split(/\r?\n/);
  const blocks: MarkdownBlock[] = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index];
    if (!line.trim()) {
      index += 1;
      continue;
    }

    if (/^```/.test(line.trim())) {
      const source = [line];
      index += 1;
      while (index < lines.length) {
        source.push(lines[index]);
        if (/^```/.test(lines[index].trim())) {
          index += 1;
          break;
        }
        index += 1;
      }
      blocks.push({ content: source.join("\n"), type: "source" });
      continue;
    }

    if (isTableStart(lines, index)) {
      const source: string[] = [];
      while (index < lines.length && lines[index].trim()) {
        source.push(lines[index]);
        index += 1;
      }
      blocks.push({ content: source.join("\n"), type: "source" });
      continue;
    }

    const heading = line.match(/^(#{1,6})\s+(.+)$/);
    if (heading) {
      blocks.push({ level: heading[1].length, text: heading[2].trim(), type: "heading" });
      index += 1;
      continue;
    }

    if (/^>\s?/.test(line)) {
      const quote: string[] = [];
      while (index < lines.length && /^>\s?/.test(lines[index])) {
        quote.push(lines[index]);
        index += 1;
      }
      blocks.push({ content: quote.join("\n"), type: "blockquote" });
      continue;
    }

    const listMatch = line.match(/^(\s*)([-*+]|\d+[.)])\s+(.+)$/);
    if (listMatch) {
      const items: string[] = [];
      const ordered = /\d+[.)]/.test(listMatch[2]);
      while (index < lines.length) {
        const itemMatch = lines[index].match(/^(\s*)([-*+]|\d+[.)])\s+(.+)$/);
        if (!itemMatch || /\d+[.)]/.test(itemMatch[2]) !== ordered) {
          break;
        }
        items.push(itemMatch[3].trim());
        index += 1;
      }
      blocks.push({ items, ordered, type: "list" });
      continue;
    }

    const paragraph: string[] = [];
    const paragraphStart = index;
    while (index < lines.length && lines[index].trim()) {
      if (index !== paragraphStart && startsNewBlock(lines, index)) {
        break;
      }
      paragraph.push(lines[index].trim());
      index += 1;
    }
    blocks.push({ text: paragraph.join(" "), type: "paragraph" });
  }

  return blocks;
}

function serializeMarkdownBlocks(blocks: MarkdownBlock[]) {
  return blocks
    .map((block) => {
      if (block.type === "heading") {
        return `${"#".repeat(block.level)} ${block.text}`;
      }
      if (block.type === "list") {
        return block.items.map((item, index) => `${block.ordered ? `${index + 1}.` : "-"} ${item}`).join("\n");
      }
      if (block.type === "blockquote") {
        return stripBlockquotePrefix(block.content)
          .split("\n")
          .map((line) => `> ${line}`)
          .join("\n");
      }
      return block.type === "source" ? block.content : block.text;
    })
    .join("\n\n")
    .trim();
}

function startsNewBlock(lines: string[], index: number) {
  return (
    /^#{1,6}\s+/.test(lines[index]) ||
    /^```/.test(lines[index].trim()) ||
    /^>\s?/.test(lines[index]) ||
    /^(\s*)([-*+]|\d+[.)])\s+/.test(lines[index]) ||
    isTableStart(lines, index)
  );
}

function isTableStart(lines: string[], index: number) {
  return Boolean(lines[index]?.includes("|") && /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(lines[index + 1] ?? ""));
}

function stripBlockquotePrefix(content: string) {
  return content
    .split("\n")
    .map((line) => line.replace(/^>\s?/, ""))
    .join("\n");
}

function getBlockKey(block: MarkdownBlock) {
  if (block.type === "heading") {
    return `heading-${block.level}-${block.text}`;
  }
  if (block.type === "list") {
    return `list-${block.ordered ? "ordered" : "unordered"}-${block.items.join("|")}`;
  }
  return `${block.type}-${"content" in block ? block.content : block.text}`;
}

function getListItemKey(item: string, itemIndex: number) {
  return `${item}-${itemIndex.toString(36)}`;
}
