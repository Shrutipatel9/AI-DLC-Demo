// Client-side preflight for a chosen file (AC5.2.3). The server checks again and decides; this
// only saves a pointless upload and explains the problem at once.

export const ACCEPTED_EXTENSIONS = [".jpg", ".jpeg", ".png", ".heic"];
export const ACCEPT_ATTRIBUTE = [
  ...ACCEPTED_EXTENSIONS,
  "image/jpeg",
  "image/png",
  "image/heic",
].join(",");

const ACCEPTED_TYPES = new Set(["image/jpeg", "image/png", "image/heic", "image/heif"]);

export type FileProblem = "type" | "size" | "empty";

/** Why the file can't be uploaded, or null when it may be. */
export function fileProblem(file: File, maxBytes: number): FileProblem | null {
  const name = file.name.toLowerCase();
  const typeOk =
    ACCEPTED_TYPES.has(file.type) || ACCEPTED_EXTENSIONS.some((ext) => name.endsWith(ext));
  if (!typeOk) return "type";
  if (file.size === 0) return "empty";
  if (file.size > maxBytes) return "size";
  return null;
}

/** Whole megabytes for messages ("10 MB"). */
export function megabytes(bytes: number): number {
  return Math.max(1, Math.floor(bytes / (1024 * 1024)));
}
