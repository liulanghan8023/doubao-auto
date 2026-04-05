async function parseJson(response) {
  const text = await response.text();
  return text ? JSON.parse(text) : {};
}

export async function request(url, options = {}) {
  const response = await fetch(url, options);
  const payload = await parseJson(response);
  if (!response.ok) {
    throw new Error(payload.detail || payload.message || "Request failed");
  }
  return payload;
}
