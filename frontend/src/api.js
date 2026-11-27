export class ApiError extends Error {
  constructor(message, status, detail) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

export async function api(
  path,
  { method = "GET", body, signal, responseType = "json" } = {},
) {
  const multipart = body instanceof FormData;
  let response;
  try {
    response = await fetch(`/api${path}`, {
      method,
      credentials: "include",
      headers:
        body === undefined || multipart
          ? undefined
          : { "Content-Type": "application/json" },
      body:
        body === undefined
          ? undefined
          : multipart
            ? body
            : JSON.stringify(body),
      signal,
    });
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw new ApiError(
      "We could not connect. Check your connection and try again.",
      0,
    );
  }
  if (response.status === 204) return null;
  if (response.ok && responseType === "blob") return response.blob();
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = data?.detail;
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((item) => item.msg).join(". ")
          : detail?.message ||
            "We could not complete that request. Please try again.";
    throw new ApiError(message, response.status, detail);
  }
  return data;
}
