import { LogoMark } from "@/components/brand/logo";

/**
 * The full-screen FaceIQ loader shown while the app decides where to go (restoring the session,
 * finding the next step, signing in after a code). It covers the page, so nothing else flashes
 * underneath while a redirect is in flight. Pure CSS animation; reduced motion stops it.
 */
export function PageLoader({
  message,
  detail,
  testId,
}: {
  message: string;
  detail?: string;
  testId?: string;
}) {
  return (
    <div className="page-loader" data-testid="page-loader">
      <div role="status" aria-live="polite" className="page-loader-panel" data-testid={testId}>
        <span aria-hidden="true" className="page-loader-mark">
          <span className="page-loader-ring" />
          <span className="page-loader-scan" />
          <LogoMark className="size-11" />
        </span>
        <span className="text-lg font-semibold text-heading">{message}</span>
        {detail ? <span className="text-sm text-subheading">{detail}</span> : null}
        <span aria-hidden="true" className="page-loader-dots">
          <span />
          <span />
          <span />
        </span>
      </div>
    </div>
  );
}
