/** User-safe error messages — never surface raw API bodies or stack traces. */

const GENERIC = "Something went wrong. Please try again.";
const UNAVAILABLE = "Service temporarily unavailable. Please try again later.";
const RATE_LIMITED = "Too many requests. Please wait a moment and try again.";

export function userFacingApiError(status: number, rawDetail?: string): string {
  if (status === 429) return RATE_LIMITED;
  if (status === 422 && rawDetail?.trim()) return rawDetail.trim();
  if (status >= 500) return UNAVAILABLE;
  if (status === 503) return UNAVAILABLE;
  if (status === 502) return UNAVAILABLE;
  return GENERIC;
}

export function userFacingNetworkError(): string {
  if (import.meta.env.DEV) {
    return "Could not reach the API. Start the backend with: cd api && uvicorn app.main:app --reload";
  }
  return UNAVAILABLE;
}

export function userFacingStreamError(status: number): string {
  return userFacingApiError(status);
}

export function userFacingAgentMessage(message: string): string {
  if (import.meta.env.DEV) return message;
  if (/error|failed|exception|traceback|HTTP \d/i.test(message)) {
    return UNAVAILABLE;
  }
  return message;
}
