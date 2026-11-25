import { cva, type VariantProps } from "class-variance-authority";
import type { ComponentProps } from "react";
import { cn } from "./cn";

const styles = cva(
  "inline-flex shrink-0 items-center justify-center gap-1.5 rounded-md font-medium whitespace-nowrap transition-colors disabled:opacity-50 [&_svg]:size-4",
  {
    variants: {
      variant: {
        primary: "bg-accent text-accent-ink hover:brightness-110",
        outline: "border border-line bg-panel text-ink hover:bg-raised",
        ghost: "text-soft hover:bg-raised hover:text-ink",
        danger: "border border-line text-danger hover:bg-raised",
      },
      size: { md: "h-8 px-3 text-[13px]", icon: "size-8" },
    },
    defaultVariants: { variant: "outline", size: "md" },
  },
);

type Props = ComponentProps<"button"> & VariantProps<typeof styles>;

export function Button({ className, variant, size, type = "button", ...props }: Props) {
  return <button type={type} className={cn(styles({ variant, size }), className)} {...props} />;
}
