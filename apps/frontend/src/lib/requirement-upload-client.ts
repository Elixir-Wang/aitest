"use client";

import { API_BASE_URL, ApiRequestError, apiAuthHeaders, apiErrorFromXhr, apiRequest } from "@/lib/api-client";

export type RequirementUploadConfig = {
  max_files: number;
  max_file_size_bytes: number;
  max_batch_size_bytes: number;
  chunk_size_bytes: number;
  concurrency: number;
  session_ttl_hours: number;
  supported_extensions: string[];
};

export const DEFAULT_REQUIREMENT_UPLOAD_CONFIG: RequirementUploadConfig = {
  max_files: 10,
  max_file_size_bytes: 20 * 1024 * 1024,
  max_batch_size_bytes: 200 * 1024 * 1024,
  chunk_size_bytes: 5 * 1024 * 1024,
  concurrency: 3,
  session_ttl_hours: 24,
  supported_extensions: [".pdf", ".doc", ".docx", ".txt", ".md", ".markdown"],
};

type RequirementUploadResponse = {
  document: {
    id: string;
    project_id: string;
    name: string;
  };
  files: Array<{
    id: string;
    original_filename: string;
    conversion_status: string;
    conversion_summary: string;
    created_at: string;
  }>;
};

type UploadMode = "new" | "append";

type UploadSessionFile = {
  id: string;
  filename: string;
  size: number;
  chunk_count: number;
  uploaded_parts: number[];
};

type UploadSession = {
  id: string;
  chunk_size_bytes: number;
  concurrency: number;
  files: UploadSessionFile[];
};

type UploadOptions = {
  projectId: string;
  files: File[];
  mode: UploadMode;
  documentName: string;
  existingDocumentId: string;
  projectVersionId: string;
  onProgress: (file: File, progress: number) => void;
};

type PendingPart = {
  file: File;
  sessionFile: UploadSessionFile;
  partNumber: number;
  start: number;
  end: number;
};

const STORAGE_PREFIX = "ai-testing:requirement-upload:";
const MAX_CHUNK_RETRIES = 3;

export function getRequirementUploadConfig(projectId: string) {
  return apiRequest<RequirementUploadConfig>(`/projects/${projectId}/requirements/upload-config`);
}

export function requirementUploadFileKey(file: File) {
  return `${file.name}-${file.lastModified}-${file.size}`;
}

export async function uploadRequirementFiles(options: UploadOptions): Promise<RequirementUploadResponse> {
  const signature = uploadSignature(options);
  const storageKey = `${STORAGE_PREFIX}${options.projectId}`;
  let session = await restoreSession(storageKey, signature, options.projectId);
  if (!session) {
    session = await apiRequest<UploadSession>(`/projects/${options.projectId}/requirements/upload-sessions`, {
      method: "POST",
      body: JSON.stringify({
        mode: options.mode,
        document_name: options.mode === "new" ? options.documentName.trim() : "",
        existing_document_id: options.mode === "append" ? options.existingDocumentId : "",
        project_version_id: options.mode === "new" ? options.projectVersionId : "",
        files: options.files.map((file) => ({
          filename: file.name,
          size: file.size,
        })),
      }),
    });
    localStorage.setItem(storageKey, JSON.stringify({ signature, uploadId: session.id }));
  }

  ensureSessionMatchesFiles(session, options.files);
  await uploadMissingParts(session, options);
  const result = await apiRequest<RequirementUploadResponse>(
    `/projects/${options.projectId}/requirements/upload-sessions/${session.id}/complete`,
    { method: "POST" },
  );
  localStorage.removeItem(storageKey);
  return result;
}

async function restoreSession(storageKey: string, signature: string, projectId: string) {
  const stored = parseStoredSession(localStorage.getItem(storageKey));
  if (!stored) {
    return null;
  }
  if (stored.signature !== signature) {
    await cancelStoredSession(projectId, stored.uploadId);
    localStorage.removeItem(storageKey);
    return null;
  }
  try {
    return await apiRequest<UploadSession>(`/projects/${projectId}/requirements/upload-sessions/${stored.uploadId}`);
  } catch (error) {
    if (error instanceof ApiRequestError && [404, 410].includes(error.status)) {
      localStorage.removeItem(storageKey);
      return null;
    }
    throw error;
  }
}

async function cancelStoredSession(projectId: string, uploadId: string) {
  try {
    await apiRequest(`/projects/${projectId}/requirements/upload-sessions/${uploadId}`, { method: "DELETE" });
  } catch (error) {
    if (!(error instanceof ApiRequestError) || ![404, 410].includes(error.status)) {
      throw error;
    }
  }
}

async function uploadMissingParts(session: UploadSession, options: UploadOptions) {
  const completedBytes = new Map<string, number>();
  const inFlightBytes = new Map<string, Map<number, number>>();
  const pending: PendingPart[] = [];
  const maxChunkCount = Math.max(...session.files.map((file) => file.chunk_count));

  for (let fileIndex = 0; fileIndex < session.files.length; fileIndex += 1) {
    const sessionFile = session.files[fileIndex];
    const file = options.files[fileIndex];
    const uploadedParts = new Set(sessionFile.uploaded_parts);
    const uploadedBytes = sessionFile.uploaded_parts.reduce(
      (total, partNumber) => total + partSize(sessionFile.size, session.chunk_size_bytes, partNumber),
      0,
    );
    completedBytes.set(sessionFile.id, uploadedBytes);
    inFlightBytes.set(sessionFile.id, new Map());
    options.onProgress(file, Math.round((uploadedBytes / file.size) * 100));

    for (let partNumber = 0; partNumber < maxChunkCount; partNumber += 1) {
      if (partNumber >= sessionFile.chunk_count || uploadedParts.has(partNumber)) {
        continue;
      }
      const start = partNumber * session.chunk_size_bytes;
      pending.push({
        file,
        sessionFile,
        partNumber,
        start,
        end: Math.min(file.size, start + session.chunk_size_bytes),
      });
    }
  }

  // Round-robin by part number so the three workers make progress across files.
  pending.sort((left, right) => left.partNumber - right.partNumber);
  const workerCount = Math.min(Math.max(session.concurrency, 1), pending.length);
  let nextIndex = 0;
  const worker = async () => {
    while (nextIndex < pending.length) {
      const task = pending[nextIndex];
      nextIndex += 1;
      const progressForChunk = (loaded: number) => {
        inFlightBytes.get(task.sessionFile.id)?.set(task.partNumber, loaded);
        reportFileProgress(task.file, task.sessionFile.id, completedBytes, inFlightBytes, options.onProgress);
      };
      await uploadPartWithRetry(session, options.projectId, task, progressForChunk);
      inFlightBytes.get(task.sessionFile.id)?.delete(task.partNumber);
      completedBytes.set(task.sessionFile.id, (completedBytes.get(task.sessionFile.id) ?? 0) + task.end - task.start);
      reportFileProgress(task.file, task.sessionFile.id, completedBytes, inFlightBytes, options.onProgress);
    }
  };
  await Promise.all(Array.from({ length: workerCount }, () => worker()));
}

async function uploadPartWithRetry(
  session: UploadSession,
  projectId: string,
  task: PendingPart,
  onProgress: (loaded: number) => void,
) {
  const blob = task.file.slice(task.start, task.end);
  const chunkSha256 = await sha256(blob);
  let lastError: unknown;
  for (let attempt = 0; attempt <= MAX_CHUNK_RETRIES; attempt += 1) {
    try {
      await uploadPart(projectId, session.id, task.sessionFile.id, task.partNumber, blob, chunkSha256, onProgress);
      return;
    } catch (error) {
      lastError = error;
      if (attempt < MAX_CHUNK_RETRIES) {
        await delay(500 * 2 ** attempt);
      }
    }
  }
  throw lastError;
}

function uploadPart(
  projectId: string,
  uploadId: string,
  fileId: string,
  partNumber: number,
  blob: Blob,
  chunkSha256: string,
  onProgress: (loaded: number) => void,
) {
  return new Promise<void>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open(
      "PUT",
      `${API_BASE_URL}/projects/${projectId}/requirements/upload-sessions/${uploadId}/files/${fileId}/parts/${partNumber}`,
    );
    xhr.withCredentials = true;
    for (const [name, value] of apiAuthHeaders()) {
      xhr.setRequestHeader(name, value);
    }
    xhr.setRequestHeader("Content-Type", "application/octet-stream");
    if (chunkSha256) {
      xhr.setRequestHeader("X-Chunk-SHA256", chunkSha256);
    }
    xhr.upload.onprogress = (event) => onProgress(event.loaded);
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve();
      } else {
        reject(apiErrorFromXhr(xhr, "文件分片上传失败"));
      }
    };
    xhr.onerror = () => reject(apiErrorFromXhr(xhr, "网络异常，文件分片上传失败"));
    xhr.send(blob);
  });
}

function reportFileProgress(
  file: File,
  fileId: string,
  completedBytes: Map<string, number>,
  inFlightBytes: Map<string, Map<number, number>>,
  onProgress: UploadOptions["onProgress"],
) {
  const inFlight = [...(inFlightBytes.get(fileId)?.values() ?? [])].reduce((total, value) => total + value, 0);
  const loaded = Math.min(file.size, (completedBytes.get(fileId) ?? 0) + inFlight);
  onProgress(file, Math.min(99, Math.round((loaded / file.size) * 100)));
}

function ensureSessionMatchesFiles(session: UploadSession, files: File[]) {
  const matches =
    session.files.length === files.length &&
    session.files.every(
      (sessionFile, index) => sessionFile.filename === files[index].name && sessionFile.size === files[index].size,
    );
  if (!matches) {
    throw new Error("续传会话与当前所选文件不一致，请重新选择原文件。");
  }
}

function uploadSignature(options: UploadOptions) {
  return JSON.stringify({
    mode: options.mode,
    documentName: options.mode === "new" ? options.documentName.trim() : "",
    projectVersionId: options.mode === "new" ? options.projectVersionId : "",
    existingDocumentId: options.mode === "append" ? options.existingDocumentId : "",
    files: options.files.map((file) => [file.name, file.size, file.lastModified]),
  });
}

function parseStoredSession(value: string | null): { signature: string; uploadId: string } | null {
  if (!value) {
    return null;
  }
  try {
    const parsed = JSON.parse(value);
    return typeof parsed.signature === "string" && typeof parsed.uploadId === "string" ? parsed : null;
  } catch {
    return null;
  }
}

function partSize(fileSize: number, chunkSize: number, partNumber: number) {
  return Math.min(chunkSize, fileSize - partNumber * chunkSize);
}

async function sha256(blob: Blob) {
  if (!globalThis.crypto?.subtle) {
    return "";
  }
  const digest = await globalThis.crypto.subtle.digest("SHA-256", await blob.arrayBuffer());
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

function delay(milliseconds: number) {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}
