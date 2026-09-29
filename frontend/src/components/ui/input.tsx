import type { InputHTMLAttributes } from "react";

import { cn } from "../../lib/cn";

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "h-11 w-full rounded-lg border border-line bg-surface px-3 text-base text-ink placeholder:text-ink-secondary",
        className,
      )}
      {...props}
    />
  );
}
