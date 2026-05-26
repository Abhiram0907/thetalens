const DEPLOYED_API_BASE = "https://thetalens-api.onrender.com";

/** Backend origin for API calls. Empty in local dev (Vite proxies /api). */
export const API_BASE = (
  import.meta.env.VITE_API_BASE ?? (import.meta.env.PROD ? DEPLOYED_API_BASE : "")
).replace(/\/$/, "");
