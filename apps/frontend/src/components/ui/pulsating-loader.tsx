"use client";

import { motion } from "motion/react";

import { cn } from "@/lib/utils";

type PulsatingDotsProps = {
  className?: string;
  dotClassName?: string;
};

export default function PulsatingDots({ className, dotClassName }: PulsatingDotsProps) {
  return (
    <div className={cn("flex items-center justify-center", className)} role="status" aria-label="AI 回复生成中">
      <div className="flex items-center gap-1.5">
        {[0, 0.24, 0.48].map((delay) => (
          <motion.div
            animate={{
              scale: [1, 1.45, 1],
              opacity: [0.45, 1, 0.45],
            }}
            className={cn("size-2 rounded-full bg-primary", dotClassName)}
            key={delay}
            transition={{
              delay,
              duration: 0.9,
              ease: "easeInOut",
              repeat: Infinity,
            }}
          />
        ))}
      </div>
    </div>
  );
}
