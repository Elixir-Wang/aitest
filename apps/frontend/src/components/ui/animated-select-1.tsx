"use client";

import {
  Children,
  type ComponentPropsWithoutRef,
  type ReactNode,
  cloneElement,
  isValidElement,
  useCallback,
  useMemo,
  useEffect,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";

import { ChevronDown } from "lucide-react";

import { cn } from "@/lib/utils";

type SelectOptionProps = {
  value: string;
  children: string;
  setValue?: (value: string) => void;
  handleSelection?: (text: string) => void;
  closeDropdown?: () => void;
};

type MenuPosition = {
  left: number;
  top: number;
  width: number;
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
  const [menuPosition, setMenuPosition] = useState<MenuPosition | null>(null);
  const selectRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const childrenArray = Children.toArray(children);
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

  const updateMenuPosition = useCallback(() => {
    const trigger = triggerRef.current;
    if (!trigger) {
      return;
    }

    const rect = trigger.getBoundingClientRect();
    setMenuPosition({
      left: rect.left,
      top: rect.bottom + 8,
      width: rect.width,
    });
  }, []);

  useEffect(() => {
    if (!isOpened) {
      return;
    }

    updateMenuPosition();

    const handleScrollOrResize = () => {
      updateMenuPosition();
    };

    window.addEventListener("scroll", handleScrollOrResize, true);
    window.addEventListener("resize", handleScrollOrResize);
    return () => {
      window.removeEventListener("scroll", handleScrollOrResize, true);
      window.removeEventListener("resize", handleScrollOrResize);
    };
  }, [isOpened, updateMenuPosition]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as Node;
      if (selectRef.current?.contains(target) || menuRef.current?.contains(target)) {
        return;
      }
      setIsOpened(false);
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

  const openDropdown = () => {
    const trigger = triggerRef.current;
    if (trigger) {
      const rect = trigger.getBoundingClientRect();
      setMenuPosition({
        left: rect.left,
        top: rect.bottom + 8,
        width: rect.width,
      });
    }
    setIsOpened(true);
  };

  const toggleDropdown = () => {
    if (isOpened) {
      setIsOpened(false);
      return;
    }
    openDropdown();
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

  const dropdownMenu =
    typeof document !== "undefined" && isOpened && menuPosition
      ? createPortal(
          <div
            ref={menuRef}
            className="pointer-events-auto fixed z-[100] max-h-60 overflow-y-auto rounded-lg border border-border bg-popover py-0.5 text-sm text-popover-foreground shadow-sm"
            style={{
              left: menuPosition.left,
              top: menuPosition.top,
              width: menuPosition.width,
            }}
          >
            {childrenWithProps}
          </div>,
          document.body,
        )
      : null;

  const { disabled, onClick, ...buttonProps } = props;

  return (
    <div ref={selectRef} className="relative">
      <button
        ref={triggerRef}
        className={cn(
          "flex h-8 w-full min-w-44 cursor-pointer items-center justify-between gap-2 overflow-hidden rounded-lg border border-input bg-transparent px-2.5 py-1 text-left text-sm text-foreground transition-colors outline-none hover:bg-muted focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-input/30 dark:hover:bg-input/50",
          className,
        )}
        disabled={disabled}
        onClick={(event) => {
          onClick?.(event);
          if (disabled || event.defaultPrevented) {
            return;
          }
          toggleDropdown();
        }}
        type="button"
        {...buttonProps}
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

        <ChevronDown className={cn("shrink-0 transition-transform duration-200", isOpened && "rotate-180")} />
      </button>

      {dropdownMenu}
    </div>
  );
}

export function SelectOption({ children, value, setValue, handleSelection, closeDropdown }: SelectOptionProps) {
  return (
    <div
      className="cursor-pointer rounded-md px-2.5 py-1 text-sm leading-normal transition-colors duration-200 hover:bg-muted"
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
