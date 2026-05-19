"use client";

export function setLocalStorageValue(key: string, value: string) {
  try {
    window.localStorage.setItem(key, value);
  } catch (error) {
    if (process.env.NODE_ENV !== "production") {
      console.error("[localStorage] Failed to write value:", error);
    }
  }
}

export function setSessionStorageValue(key: string, value: string) {
  try {
    window.sessionStorage.setItem(key, value);
  } catch (error) {
    if (process.env.NODE_ENV !== "production") {
      console.error("[sessionStorage] Failed to write value:", error);
    }
  }
}

export function getLocalStorageValue(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

export function getSessionStorageValue(key: string): string | null {
  try {
    return window.sessionStorage.getItem(key);
  } catch {
    return null;
  }
}

export function removeLocalStorageValue(key: string) {
  try {
    window.localStorage.removeItem(key);
  } catch (error) {
    if (process.env.NODE_ENV !== "production") {
      console.error("[localStorage] Failed to remove value:", error);
    }
  }
}

export function removeSessionStorageValue(key: string) {
  try {
    window.sessionStorage.removeItem(key);
  } catch (error) {
    if (process.env.NODE_ENV !== "production") {
      console.error("[sessionStorage] Failed to remove value:", error);
    }
  }
}
