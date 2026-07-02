// Client-side cookie utilities.
// These functions manage cookies in the browser only.
// Server actions handle cookie updates on the server side.

function writeClientCookie(serializedCookie: string) {
  // biome-ignore lint/suspicious/noDocumentCookie: This project still uses document.cookie for broad browser support.
  document.cookie = serializedCookie;
}

export function setClientCookie(key: string, value: string, days = 7) {
  const expires = new Date(Date.now() + days * 864e5).toUTCString();
  writeClientCookie(`${key}=${value}; expires=${expires}; path=/`);
}
