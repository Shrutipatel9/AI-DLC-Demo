import Link from "next/link";

export default function NotFound() {
  return (
    <main id="main" className="mx-auto max-w-[480px] px-4 py-16 text-center">
      <h1 className="text-2xl font-bold text-heading">We couldn&apos;t find that page.</h1>
      <Link
        href="/login"
        className="mt-6 inline-block font-semibold text-accent-strong underline"
        data-testid="not-found-next-step-link"
      >
        Go to my next step
      </Link>
    </main>
  );
}
