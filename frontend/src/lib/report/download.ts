// Save a Blob as a file in the browser (the PDF is read with the access token, so it cannot be a
// plain link). The object URL is revoked as soon as the click has been handled.
export const PDF_FILE_NAME = "facial-analysis-report.pdf";

export function saveBlob(blob: Blob, fileName: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}
