/** Backend origin for API calls. Empty in local dev (Vite proxies /api). */
export const API_BASE = (import.meta.env.VITE_API_BASE ?? "").replace(/\/$/, "");
