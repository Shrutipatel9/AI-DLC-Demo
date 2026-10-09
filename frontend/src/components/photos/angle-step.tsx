"use client";

// One capture step per configured angle (US5.2, US5.3, US5.5, US5.10). File upload is always
// offered (AC5.3.3); the camera is offered when the browser has one. While the server checks a
// photo the step shows a checking state; the result is announced by the flow's live region.
import { Camera, Lightbulb, LoaderCircle, TriangleAlert, Upload } from "lucide-react";
import { useId, useRef, useState, type ChangeEvent } from "react";

import { Button } from "@/components/ui/button";
import {
  ACCEPT_ATTRIBUTE,
  cameraSupported,
  entryFor,
  fileProblem,
  megabytes,
  progressText,
  type AngleInfo,
  type CaptureMethod,
  type PhotoRequirements,
  type PhotoSet,
} from "@/lib/photos";

import { CameraCapture } from "./camera-capture";
import { AngleIllustration } from "./illustrations";
import { fileProblemMessage, reasonMessage } from "./messages";
import { PhotoThumbnail } from "./photo-thumbnail";

export interface Rejection {
  angle: string;
  reasons: string[];
  /** Shown when the failure has no reason codes (a size or type refusal, a network error). */
  message?: string;
}

export function AngleStep({
  angle,
  position,
  requirements,
  photoSet,
  checking,
  rejection,
  onSubmit,
  onBack,
  backLabel,
}: {
  angle: AngleInfo;
  position: number;
  requirements: PhotoRequirements;
  photoSet: PhotoSet;
  checking: boolean;
  rejection: Rejection | null;
  onSubmit: (photo: Blob, fileName: string, method: CaptureMethod) => void;
  onBack: () => void;
  backLabel: string;
}) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [cameraOpen, setCameraOpen] = useState(false);
  const [localProblem, setLocalProblem] = useState<string | null>(null);
  const headingId = useId();
  const total = photoSet.requiredAngles.length;
  const current = entryFor(photoSet, angle.id);
  const ownRejection = rejection?.angle === angle.id ? rejection : null;
  const storedReasons = current.status === "rejected" ? (current.reasons ?? []) : [];
  const reasons = ownRejection ? ownRejection.reasons : storedReasons;
  const maxMb = megabytes(requirements.maxUploadBytes);

  function chooseFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = ""; // choosing the same file again still triggers a change
    if (!file) return;
    const problem = fileProblem(file, requirements.maxUploadBytes);
    if (problem) {
      setLocalProblem(fileProblemMessage(problem, maxMb));
      return;
    }
    setLocalProblem(null);
    onSubmit(file, file.name, "upload");
  }

  return (
    <section
      className="space-y-5"
      aria-labelledby={headingId}
      data-testid="photo-step"
      data-angle={angle.id}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h1
          id={headingId}
          className="text-2xl font-bold text-heading sm:text-[28px]"
          data-testid="photo-step-title"
        >
          Photo {position} of {total}: {angle.label}
        </h1>
        <p
          className="rounded-full bg-accent-soft px-3 py-1 text-sm font-semibold text-accent-deep"
          data-testid="photo-progress"
        >
          {progressText(photoSet)} photos done
        </p>
      </div>

      <div className="flex items-center gap-4 rounded-ui bg-brand-gradient-soft p-4">
        <AngleIllustration
          direction={angle.illustration}
          className="h-24 w-20 shrink-0"
          title={`Example: ${angle.label}`}
        />
        <p className="text-base font-medium text-heading" data-testid="photo-instruction">
          {angle.instruction}
        </p>
      </div>

      <details className="rounded-ui border border-card-border bg-white p-4" open>
        <summary className="flex cursor-pointer items-center gap-2 text-base font-semibold text-heading">
          <Lightbulb className="size-5 text-[#92590a]" aria-hidden="true" />
          Tips for a good photo
        </summary>
        <ul
          className="mt-3 list-disc space-y-1 pl-5 text-sm text-foreground"
          data-testid="photo-guidance"
        >
          {requirements.guidance.map((tip) => (
            <li key={tip}>{tip}</li>
          ))}
        </ul>
      </details>

      {current.status === "accepted" && current.imageUrl ? (
        <div className="flex items-center gap-3" data-testid="photo-current">
          <PhotoThumbnail
            imageUrl={current.imageUrl}
            alt={`Your current ${angle.label} photo`}
            className="w-20"
          />
          <p className="text-sm text-muted">Your current photo. A new one replaces it.</p>
        </div>
      ) : null}

      {checking ? (
        <p
          className="flex items-center gap-2 rounded-ui bg-accent-soft p-3 text-base font-medium text-accent-deep"
          data-testid="photo-checking"
        >
          <LoaderCircle className="h-5 w-5 animate-spin" aria-hidden="true" />
          Checking your photo…
        </p>
      ) : null}

      {!checking && (reasons.length > 0 || ownRejection?.message || localProblem) ? (
        <div
          className="space-y-2 rounded-ui border border-danger/30 bg-danger-soft p-4"
          data-testid="photo-reasons"
        >
          <p className="flex items-center gap-2 font-semibold text-heading">
            <TriangleAlert className="h-5 w-5 text-danger" aria-hidden="true" />
            This photo can&apos;t be used
          </p>
          <ul className="list-disc space-y-1 pl-5 text-sm text-foreground">
            {localProblem ? <li>{localProblem}</li> : null}
            {!localProblem && ownRejection?.message ? <li>{ownRejection.message}</li> : null}
            {!localProblem
              ? reasons.map((reason) => (
                  <li key={reason} data-testid={`photo-reason-${reason}`}>
                    {reasonMessage(reason, angle)}
                  </li>
                ))
              : null}
          </ul>
        </div>
      ) : null}

      {cameraOpen ? (
        <CameraCapture
          angle={angle}
          disabled={checking}
          onUse={(photo) => {
            setCameraOpen(false);
            onSubmit(photo, `${angle.id}-camera.jpg`, "camera");
          }}
          onClose={() => setCameraOpen(false)}
        />
      ) : null}

      <div className="flex flex-wrap gap-3">
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT_ATTRIBUTE}
          className="sr-only"
          tabIndex={-1}
          onChange={chooseFile}
          aria-label={`Choose a ${angle.label} photo`}
          data-testid="photo-file-input"
        />
        <Button
          onClick={() => inputRef.current?.click()}
          disabled={checking}
          data-testid="photo-upload-button"
        >
          <Upload className="h-4 w-4" aria-hidden="true" />
          Upload a photo
        </Button>
        {cameraSupported() && !cameraOpen ? (
          <Button
            variant="secondary"
            onClick={() => setCameraOpen(true)}
            disabled={checking}
            data-testid="photo-camera-button"
          >
            <Camera className="h-4 w-4" aria-hidden="true" />
            Use camera
          </Button>
        ) : null}
      </div>
      <p className="text-sm text-muted">JPEG, PNG or HEIC, up to {maxMb} MB.</p>

      <Button variant="link" onClick={onBack} disabled={checking} data-testid="photo-back-button">
        {backLabel}
      </Button>
    </section>
  );
}
