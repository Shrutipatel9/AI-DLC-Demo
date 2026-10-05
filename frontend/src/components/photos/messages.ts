// Plain-language messages for the photo screens. The UI branches on codes only. Every
// rejection message describes the photo and how to fix it, never the person (AC5.5.4).
import { messageFor } from "@/components/auth/messages";
import type { ApiError } from "@/lib/api/errors";
import type { AngleInfo, CameraProblem, FileProblem } from "@/lib/photos";

/** The message for one rejection reason (``PHOTO_REJECTED`` details or a stored rejection). */
export function reasonMessage(reason: string, angle: AngleInfo | undefined): string {
  switch (reason) {
    case "UNREADABLE":
      return "We couldn't open this file. Please choose another photo.";
    case "TOO_SMALL":
      return "This photo's resolution is too low. Use your camera's normal photo setting, not a screenshot or thumbnail.";
    case "NO_FACE":
      return "We couldn't find a face in this photo. Make sure your face is in the frame and well lit.";
    case "MULTIPLE_FACES":
      return "This photo needs exactly one face. Make sure only your head is in the frame.";
    case "TOO_DARK":
      return "This photo is too dark. Face a window or add more light, without strong shadows.";
    case "TOO_BRIGHT":
      return "This photo is too bright. Move out of direct light or turn the light down.";
    case "FACE_TOO_SMALL":
      return "Move closer so your face fills more of the frame.";
    case "FACE_TOO_LARGE":
      return "Move the camera back so your whole head and neck fit in the frame.";
    case "POSE_MISMATCH":
      return angle
        ? `This photo doesn't match the ${angle.label} angle. ${angle.turnHint}`
        : "This photo doesn't match the requested angle. Follow the turn instruction above.";
    case "EYES_COVERED":
      return "Your eyes look covered. Take off glasses or a hat and keep hair away from your eyes.";
    case "MOUTH_COVERED":
      return "Your mouth looks covered. Keep your hands and anything else away from your mouth.";
    default:
      return "This photo can't be used. Please check the tips and try again.";
  }
}

export const MISMATCH_MESSAGE =
  "These photos don't appear to show the same person. Please retake this photo in the same light and position as the others.";

export const CONTINUE_REASON: Record<"pending" | "mismatch" | "incomplete", string> = {
  pending: "Checking your photos…",
  mismatch: "Retake the highlighted photo to continue.",
  incomplete: "Add a photo for every angle to continue.",
};

/** The message for a file the browser already knows it can't upload. */
export function fileProblemMessage(problem: FileProblem, maxMegabytes: number): string {
  if (problem === "type") return "Please choose a JPEG, PNG or HEIC photo.";
  if (problem === "empty") return "This file is empty. Please choose another photo.";
  return `This photo is larger than ${maxMegabytes} MB. Please choose a smaller photo.`;
}

export function cameraMessage(problem: CameraProblem): string {
  if (problem === "denied") {
    return "Camera access was not allowed. You can upload a photo instead, or allow the camera in your browser settings.";
  }
  if (problem === "unavailable") {
    return "We couldn't find a camera on this device. Please upload a photo instead.";
  }
  return "The camera didn't start. Please try again or upload a photo instead.";
}

/** The toast text for a photo API failure other than a rejection. */
export function photoErrorMessage(error: ApiError): string {
  switch (error.code) {
    case "PHOTO_REJECTED":
      return "This photo can't be used. See the reasons below.";
    case "PHOTO_TOO_LARGE":
    case "PHOTO_UNSUPPORTED_TYPE":
      return error.message;
    case "QUESTIONNAIRE_NOT_SUBMITTED":
      return "Please finish the questionnaire first.";
    default:
      return messageFor(error);
  }
}
