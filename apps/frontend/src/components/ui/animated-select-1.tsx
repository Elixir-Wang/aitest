"use client";

import {
  type ComponentPropsWithoutRef,
  type ReactNode,
  cloneElement,
  isValidElement,
  useMemo,
  useEffect,
  useRef,
  useState,
} from "react";

import { CaretDown } from "@phosphor-icons/react";
import { AnimatePresence, motion } from "motion/react";

import { cn } from "@/lib/utils";

type SelectOptionProps = {
  value: string;
  children: string;
  setValue?: (value: string) => void;
  handleSelection?: (text: string) => void;
  closeDropdown?: () => void;
};

export function Select({
  children,
  className,
  placeholder,
  setValue,
  value,
  ...props
}: {
  children: ReactNode;
  placeholder: string;
  className?: string;
  setValue: (value: string) => void;
  value?: string;
} & Omit<ComponentPropsWithoutRef<"button">, "value">) {
  const [isOpened, setIsOpened] = useState(false);
  const [displayText, setDisplayText] = useState(value ?? "");
  const selectRef = useRef<HTMLDivElement>(null);
  const childrenArray = Array.isArray(children) ? children : [children];
  const selectedLabel = useMemo(() => {
    const selected = childrenArray.find((child) => isValidElement<SelectOptionProps>(child) && child.props.value === value);
    if (!selected || !isValidElement<SelectOptionProps>(selected)) {
      return value ?? "";
    }
    return selected.props.children;
  }, [childrenArray, value]);

  useEffect(() => {
    setDisplayText(selectedLabel);
  }, [selectedLabel]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (selectRef.current && !selectRef.current.contains(event.target as Node)) {
        setIsOpened(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  const closeDropdown = () => setIsOpened(false);

  const handleSelection = (text: string) => {
    setDisplayText(text);
  };

  const childrenWithProps = childrenArray.map((child, index) => {
    if (isValidElement<SelectOptionProps>(child)) {
      return cloneElement(child, {
        setValue,
        handleSelection,
        closeDropdown,
        key: child.props.value || index,
      });
    }
    return child;
  });

  return (
    <div ref={selectRef} className="relative">
      <button
        className={cn(
          "flex h-8 w-full min-w-44 cursor-pointer items-center justify-between gap-2 overflow-hidden rounded-lg border border-input bg-transparent px-2.5 py-1 text-left text-sm text-foreground transition-colors outline-none hover:bg-muted focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 dark:bg-input/30 dark:hover:bg-input/50",
          className,
        )}
        onClick={() => setIsOpened(!isOpened)}
        type="button"
        {...props}
      >
        <div className="relative flex h-full flex-1 overflow-hidden">
          <div
            className={cn(
              "absolute inset-0 flex items-center justify-start text-muted-foreground transition-opacity duration-200",
              displayText ? "opacity-0" : "opacity-100",
            )}
          >
            {placeholder}
          </div>
          {displayText && <div className="absolute inset-0 flex items-center justify-start">{displayText}</div>}
        </div>

        <CaretDown className={cn("shrink-0 transition-transform duration-200", isOpened && "rotate-180")} />
      </button>

      <AnimatePresence>
        {isOpened && (
          <motion.div
            animate={{ opacity: 1, y: 0 }}
            className="absolute top-full right-0 left-0 z-50 mt-2 rounded-lg border border-border bg-popover p-1 text-popover-foreground shadow-sm"
            exit={{ opacity: 0, y: -10 }}
            initial={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.2 }}
          >
            {childrenWithProps}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export function SelectOption({ children, value, setValue, handleSelection, closeDropdown }: SelectOptionProps) {
  return (
    <div
      className="cursor-pointer rounded-lg px-3 py-2 transition-colors duration-200 hover:bg-muted"
      onClick={() => {
        setValue?.(value);
        handleSelection?.(children);
        closeDropdown?.();
      }}
    >
      {children}
    </div>
  );
}
