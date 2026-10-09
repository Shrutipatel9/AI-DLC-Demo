import { cn } from "@/lib/utils";

/** The product name, used in every page title and the wordmark (NFR-011: one place to rebrand). */
export const BRAND_NAME = "FaceIQ";

/**
 * The FaceIQ mark: a face outline over a small landmark mesh, on the brand gradient. Drawn
 * from the static `/images/faceiq-mark.svg` (the same art as the app icon), so it adds no
 * JavaScript. Decorative: the wordmark text, or the surrounding link's label, names it.
 */
export function LogoMark({ className }: { className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "inline-block size-8 shrink-0 bg-[url(/images/faceiq-mark.svg)] bg-contain bg-no-repeat",
        className,
      )}
    />
  );
}

/** Mark + "FaceIQ" wordmark. `tone="light"` is for dark backgrounds. */
export function Logo({
  className,
  tone = "dark",
  size = "md",
}: {
  className?: string;
  tone?: "dark" | "light";
  size?: "md" | "lg";
}) {
  return (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      <LogoMark className={size === "lg" ? "size-10" : "size-8"} />
      <span
        className={cn(
          "font-display font-extrabold tracking-tight",
          size === "lg" ? "text-2xl" : "text-xl",
          tone === "light" ? "text-white" : "text-heading",
        )}
      >
        Face
        <span className={tone === "light" ? "text-[#a5f3fc]" : "text-brand-gradient"}>IQ</span>
      </span>
    </span>
  );
}
