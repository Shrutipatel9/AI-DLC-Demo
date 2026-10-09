"use client";

// The photo step (US5.1, US5.2, US5.3, US5.5, US5.6, US5.10, US5.11): requirements, one capture
// step per configured angle, then the review screen.
//
// State rules ([IV] §1, §2, §6):
// - the server's PhotoSet is the only truth; every upload answer replaces it entirely;
// - the moment an upload starts, the same-person result is reset to "pending" (null), which
//   is never treated as consistent;
// - the review screen never navigates on its own: only the Continue click leaves it.
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState, type ReactNode } from "react";

import { toast } from "@/components/feedback/toast";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { isApiError } from "@/lib/api/errors";
import {
  getPhotoSet,
  getRequirements,
  isComplete,
  nextAngle,
  uploadPhoto,
  type CaptureMethod,
  type IdentityResult,
  type PhotoRequirements,
  type PhotoSet,
} from "@/lib/photos";

import { AngleStep, type Rejection } from "./angle-step";
import { photoErrorMessage } from "./messages";
import { RequirementsScreen } from "./requirements-screen";
import { ReviewScreen } from "./review-screen";

type Screen =
  | { kind: "loading" }
  | { kind: "error" }
  | { kind: "not_ready" }
  | { kind: "requirements" }
  | { kind: "capture"; angle: string }
  | { kind: "review" };

interface Loaded {
  requirements: PhotoRequirements;
  photoSet: PhotoSet;
}

async function load(): Promise<Loaded | "not_ready" | "error"> {
  try {
    const [requirements, photoSet] = await Promise.all([getRequirements(), getPhotoSet()]);
    return { requirements, photoSet };
  } catch (error) {
    if (isApiError(error) && error.code === "QUESTIONNAIRE_NOT_SUBMITTED") return "not_ready";
    if (isApiError(error)) toast.error(photoErrorMessage(error));
    return "error";
  }
}

export const STEP_LABEL = "Step 3 of 5 · Photos";

export function PhotoFlow() {
  const router = useRouter();
  const [screen, setScreen] = useState<Screen>({ kind: "loading" });
  const [data, setData] = useState<Loaded | null>(null);
  const [identity, setIdentity] = useState<IdentityResult | null>(null);
  const [checking, setChecking] = useState<string | null>(null);
  const [rejection, setRejection] = useState<Rejection | null>(null);
  const [announcement, setAnnouncement] = useState("");

  const apply = useCallback((result: Awaited<ReturnType<typeof load>>) => {
    if (result === "not_ready" || result === "error") {
      setScreen({ kind: result });
      return;
    }
    setData(result);
    setIdentity(result.photoSet.identity);
    // A complete set opens on the review screen; otherwise the rules come first (AC5.1.1).
    setScreen(isComplete(result.photoSet) ? { kind: "review" } : { kind: "requirements" });
  }, []);

  useEffect(() => {
    let active = true;
    void load().then((result) => {
      if (active) apply(result);
    });
    return () => {
      active = false;
    };
  }, [apply]);

  const reload = useCallback(() => {
    setScreen({ kind: "loading" });
    void load().then(apply);
  }, [apply]);

  const label = useCallback(
    (angle: string) => data?.requirements.angles.find((a) => a.id === angle)?.label ?? angle,
    [data],
  );

  const submit = useCallback(
    async (angle: string, photo: Blob, fileName: string, method: CaptureMethod) => {
      if (!data) return;
      setChecking(angle);
      setRejection(null);
      setIdentity(null); // pending: never shown as consistent while a fresh result is due
      setAnnouncement(`Checking your ${label(angle)} photo…`);
      try {
        const fresh = await uploadPhoto(angle, photo, fileName, method);
        setData({ ...data, photoSet: fresh });
        setIdentity(fresh.identity);
        const next = nextAngle(fresh, angle);
        setAnnouncement(
          next
            ? `${label(angle)} photo accepted. Next: ${label(next)}.`
            : `${label(angle)} photo accepted. All photos are added.`,
        );
        toast.success(`${label(angle)} photo accepted.`);
        setScreen(next ? { kind: "capture", angle: next } : { kind: "review" });
      } catch (error) {
        const reasons = isApiError(error) ? error.reasonsFor(angle) : [];
        const message =
          isApiError(error) && error.code !== "PHOTO_REJECTED"
            ? photoErrorMessage(error)
            : undefined;
        setRejection({ angle, reasons, message });
        setAnnouncement(`Your ${label(angle)} photo can't be used. See the reasons below.`);
        toast.error(isApiError(error) ? photoErrorMessage(error) : "Something went wrong.");
        // Show the server's current state again (a rejection may be recorded for the angle).
        try {
          const current = await getPhotoSet();
          setData({ ...data, photoSet: current });
          setIdentity(current.identity);
        } catch {
          setIdentity(data.photoSet.identity);
        }
      } finally {
        setChecking(null);
      }
    },
    [data, label],
  );

  if (screen.kind === "loading") {
    return (
      <p role="status" className="text-base text-muted" data-testid="photos-loading">
        Loading your photo step…
      </p>
    );
  }
  if (screen.kind === "error") {
    return (
      <div className="space-y-4" data-testid="photos-error">
        <p role="alert" className="text-base text-heading">
          We couldn&apos;t load your photo step. Please try again.
        </p>
        <Button onClick={reload} data-testid="photos-retry-button">
          Try again
        </Button>
      </div>
    );
  }
  if (screen.kind === "not_ready" || !data) {
    return (
      <div className="space-y-4" data-testid="photos-not-ready">
        <h1 className="text-2xl font-bold text-heading">Finish your questionnaire first</h1>
        <p className="text-base text-foreground">The photo step comes after the questionnaire.</p>
        <Link href="/onboarding" className={buttonVariants()} data-testid="photos-onboarding-link">
          Go to the questionnaire
        </Link>
      </div>
    );
  }

  const { requirements, photoSet } = data;
  const angles = requirements.angles;

  function back(from: string) {
    if (isComplete(photoSet)) {
      setScreen({ kind: "review" });
      return;
    }
    const index = photoSet.requiredAngles.indexOf(from);
    const previous = photoSet.requiredAngles[index - 1];
    setRejection(null);
    setScreen(previous ? { kind: "capture", angle: previous } : { kind: "requirements" });
  }

  let body: ReactNode;
  if (screen.kind === "requirements") {
    body = (
      <RequirementsScreen
        requirements={requirements}
        onContinue={() =>
          setScreen({ kind: "capture", angle: nextAngle(photoSet) ?? photoSet.requiredAngles[0] })
        }
      />
    );
  } else if (screen.kind === "capture") {
    const angle = angles.find((a) => a.id === screen.angle) ?? angles[0];
    const index = photoSet.requiredAngles.indexOf(angle.id);
    body = (
      <AngleStep
        key={angle.id}
        angle={angle}
        position={index + 1}
        requirements={requirements}
        photoSet={photoSet}
        checking={checking === angle.id}
        rejection={rejection}
        onSubmit={(photo, fileName, method) => void submit(angle.id, photo, fileName, method)}
        onBack={() => back(angle.id)}
        backLabel={
          isComplete(photoSet) ? "Back to review" : index === 0 ? "Back to the rules" : "Back"
        }
      />
    );
  } else {
    body = (
      <ReviewScreen
        photoSet={photoSet}
        identity={identity}
        angles={angles}
        onRetake={(angle) => {
          setRejection(null);
          setScreen({ kind: "capture", angle });
        }}
        onContinue={() => {
          toast.success("Your photos are saved.");
          router.push("/payment");
        }}
      />
    );
  }

  return (
    <div className="mx-auto max-w-[720px]">
      <p
        className="mb-3 inline-flex rounded-full border border-accent-soft-border bg-accent-soft px-3 py-1 text-sm font-semibold text-accent-deep"
        data-testid="photos-step-label"
      >
        {STEP_LABEL}
      </p>
      <p className="sr-only" role="status" aria-live="polite" data-testid="photo-announcement">
        {announcement}
      </p>
      <Card className="p-4 sm:p-8">{body}</Card>
    </div>
  );
}
