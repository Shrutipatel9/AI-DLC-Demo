import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import type { ButtonHTMLAttributes, Ref } from "react";

import { cn } from "@/lib/utils";

// shadcn/ui-style button. Primary uses --accent-strong for full normal-text contrast.
const buttonVariants = cva(
  "inline-flex min-h-11 items-center justify-center gap-2 rounded-[var(--radius)] px-4 text-base font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-60",
  {
    variants: {
      variant: {
        primary: "bg-accent-strong text-white hover:bg-[#1f6159]",
        secondary: "border border-card-border bg-white text-heading hover:bg-[#eef2f5]",
        link: "min-h-0 px-0 text-accent-strong underline underline-offset-4 hover:text-[#1f6159]",
      },
      width: { auto: "", full: "w-full" },
    },
    defaultVariants: { variant: "primary", width: "auto" },
  },
);

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {
  asChild?: boolean;
  ref?: Ref<HTMLButtonElement>;
}

export function Button({ className, variant, width, asChild = false, ...props }: ButtonProps) {
  const Component = asChild ? Slot : "button";
  return <Component className={cn(buttonVariants({ variant, width }), className)} {...props} />;
}
