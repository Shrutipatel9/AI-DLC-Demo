// The only photo entry point for UI code (FE-004: UI never imports the API client).
export {
  UPLOAD_TIMEOUT_MS,
  getPhotoSet,
  getRequirements,
  loadPhoto,
  uploadPhoto,
  type AngleInfo,
  type CaptureMethod,
  type IdentityResult,
  type PhotoEntry,
  type PhotoRequirements,
  type PhotoRule,
  type PhotoSet,
} from "./api";
export {
  continueState,
  entryFor,
  flaggedAngles,
  isComplete,
  nextAngle,
  progressText,
  type ContinueState,
} from "./photo-set";
export { ACCEPT_ATTRIBUTE, fileProblem, megabytes, type FileProblem } from "./files";
export {
  CameraError,
  cameraSupported,
  captureFrame,
  openCamera,
  stopCamera,
  type CameraProblem,
} from "./camera";
