import { SearchX } from "lucide-react";
import Link from "next/link";

import { Logo } from "@/components/brand/logo";
import { buttonVariants } from "@/components/ui/button";

export default function NotFound() {
  return (
    <main id="main" className="mx-auto max-w-[480px] px-4 py-20 text-center">
      <Logo className="mb-10" />
      <span
        aria-hidden="true"
        className="mx-auto mb-5 flex size-16 items-center justify-center rounded-2xl bg-accent-soft text-accent-strong"
      >
        <SearchX className="size-8" />
      </span>
      <h1 className="text-2xl font-bold text-heading">We couldn&apos;t find that page.</h1>
      <Link
        href="/login"
        className={`${buttonVariants()} mt-6`}
        data-testid="not-found-next-step-link"
      >
        Go to my next step
      </Link>
    </main>
  );
}
