import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import type { ButtonHTMLAttributes, Ref } from "react";

import { cn } from "@/lib/utils";

// FaceIQ button. Primary text on --accent-strong keeps full normal-text contrast (6.3:1).
export const buttonVariants = cva(
  "inline-flex min-h-11 items-center justify-center gap-2 rounded-ui px-5 text-base font-semibold transition-all duration-150 disabled:cursor-not-allowed disabled:opacity-60 [&_svg]:size-[18px] [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        primary:
          "bg-accent-strong text-white shadow-button hover:bg-accent-deep hover:shadow-button-hover active:translate-y-px",
        secondary:
          "border border-card-border bg-white text-heading shadow-sm hover:border-accent-soft-border hover:bg-accent-soft",
        ghost: "text-heading hover:bg-surface-muted",
        link: "min-h-0 px-0 text-accent-strong underline underline-offset-4 hover:text-accent-deep",
      },
      size: { md: "", lg: "min-h-12 px-6 text-[17px]" },
      width: { auto: "", full: "w-full" },
    },
    defaultVariants: { variant: "primary", size: "md", width: "auto" },
  },
);

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {
  asChild?: boolean;
  ref?: Ref<HTMLButtonElement>;
}

export function Button({
  className,
  variant,
  size,
  width,
  asChild = false,
  ...props
}: ButtonProps) {
  const Component = asChild ? Slot : "button";
  return (
    <Component className={cn(buttonVariants({ variant, size, width }), className)} {...props} />
  );
}
