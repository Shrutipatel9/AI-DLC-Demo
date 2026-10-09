"use client";

// Camera capture for one angle (US5.3; AC5.3.1, AC5.3.2, AC5.3.4). The live view is mirrored
// like a selfie, with the angle guide drawn over it; the captured frame is not mirrored.
// A denied or missing camera shows a message and nothing else: file upload stays next to it.
import { Camera, RotateCcw } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  CameraError,
  captureFrame,
  openCamera,
  stopCamera,
  type AngleInfo,
  type CameraProblem,
} from "@/lib/photos";

import { AngleIllustration } from "./illustrations";
import { cameraMessage } from "./messages";

type Phase =
  | { kind: "starting" }
  | { kind: "live" }
  | { kind: "preview"; blob: Blob; url: string }
  | { kind: "error"; problem: CameraProblem };

export function CameraCapture({
  angle,
  disabled,
  onUse,
  onClose,
}: {
  angle: AngleInfo;
  disabled: boolean;
  onUse: (photo: Blob) => void;
  onClose: () => void;
}) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [phase, setPhase] = useState<Phase>({ kind: "starting" });

  useEffect(() => {
    let active = true;
    openCamera()
      .then((stream) => {
        if (!active) {
          stopCamera(stream);
          return;
        }
        streamRef.current = stream;
        setPhase({ kind: "live" });
      })
      .catch((error: unknown) => {
        if (!active) return;
        setPhase({
          kind: "error",
          problem: error instanceof CameraError ? error.problem : "failed",
        });
      });
    return () => {
      active = false;
      stopCamera(streamRef.current);
      streamRef.current = null;
    };
  }, []);

  // Attach the stream whenever the live view is (re)mounted.
  useEffect(() => {
    const video = videoRef.current;
    if (phase.kind !== "live" || !video || !streamRef.current) return;
    video.srcObject = streamRef.current;
    void video.play?.()?.catch(() => undefined);
  }, [phase.kind]);

  useEffect(
    () => () => {
      if (phase.kind === "preview") URL.revokeObjectURL(phase.url);
    },
    [phase],
  );

  const capture = useCallback(async () => {
    const video = videoRef.current;
    if (!video) return;
    try {
      const blob = await captureFrame(video);
      setPhase({ kind: "preview", blob, url: URL.createObjectURL(blob) });
    } catch {
      setPhase({ kind: "error", problem: "failed" });
    }
  }, []);

  if (phase.kind === "error") {
    return (
      <div className="space-y-3" data-testid="camera-error">
        <p role="alert" className="text-base text-heading">
          {cameraMessage(phase.problem)}
        </p>
        <Button variant="secondary" onClick={onClose} data-testid="camera-close-button">
          Close camera
        </Button>
      </div>
    );
  }

  if (phase.kind === "preview") {
    return (
      <div className="space-y-3" data-testid="camera-preview">
        <div className="mx-auto aspect-[3/4] max-h-[55vh] overflow-hidden rounded-ui border border-card-border bg-black">
          {/* eslint-disable-next-line @next/next/no-img-element -- a local blob: preview of the captured frame */}
          <img
            src={phase.url}
            alt={`Preview of your ${angle.label} photo`}
            className="h-full w-full object-contain"
          />
        </div>
        <div className="flex flex-wrap gap-3">
          <Button
            onClick={() => onUse(phase.blob)}
            disabled={disabled}
            data-testid="camera-use-button"
          >
            Use this photo
          </Button>
          <Button
            variant="secondary"
            onClick={() => setPhase({ kind: "live" })}
            disabled={disabled}
            data-testid="camera-retake-button"
          >
            <RotateCcw className="h-4 w-4" aria-hidden="true" />
            Retake
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-3" data-testid="camera-view">
      <div className="relative mx-auto aspect-[3/4] max-h-[55vh] overflow-hidden rounded-ui border border-card-border bg-black">
        <div className="absolute inset-0 -scale-x-100">
          <video
            ref={videoRef}
            className="h-full w-full object-cover"
            playsInline
            muted
            autoPlay
            data-testid="camera-video"
            aria-label={`Camera view for the ${angle.label} photo`}
          />
          <div
            className="pointer-events-none absolute inset-0 flex items-center justify-center p-8 text-white/70"
            data-testid="camera-guide"
          >
            <AngleIllustration direction={angle.illustration} className="h-3/4 w-auto" />
          </div>
        </div>
        {phase.kind === "starting" ? (
          <p role="status" className="absolute inset-x-0 top-1/2 text-center text-base text-white">
            Starting the camera…
          </p>
        ) : null}
      </div>
      <p className="text-sm text-muted">Line your head up with the outline: {angle.instruction}</p>
      <div className="flex flex-wrap gap-3">
        <Button
          onClick={() => void capture()}
          disabled={phase.kind !== "live" || disabled}
          data-testid="camera-capture-button"
        >
          <Camera className="h-4 w-4" aria-hidden="true" />
          Take photo
        </Button>
        <Button variant="secondary" onClick={onClose} data-testid="camera-cancel-button">
          Cancel
        </Button>
      </div>
    </div>
  );
}
