export interface User {
  id: number;
  username: string;
  avatar_url: string;
}

export interface Benchmark {
  id: number;
  name: string;
  version: string;
  description: string;
  category?: string | null;
  download_count: number;
  rating: number;
  owner: User;
}

export interface Solver {
  id: number;
  name: string;
  version: string;
  description: string;
  category?: string | null;
  download_count: number;
  rating: number;
  owner: User;
}

type ListResponse<T> =
  | T[]
  | {
      items: T[];
      total: number;
      page: number;
      page_size: number;
    };

function defaultApiUrl(): string {
  if (typeof window !== 'undefined') {
    return `${window.location.protocol}//${window.location.hostname}:8000`;
  }
  //return 'http://127.0.0.1:8000';
  return 'https://rastion-hub.onrender.com';
}

export const API_URL = (import.meta.env.PUBLIC_HUB_API_URL || defaultApiUrl()).replace(/\/$/, '');

function extractErrorMessage(payload: unknown, fallback: string): string {
  if (!payload || typeof payload !== 'object') {
    return fallback;
  }

  if ('detail' in payload) {
    const detail = (payload as { detail?: unknown }).detail;
    if (typeof detail === 'string') {
      return detail;
    }
  }

  if ('message' in payload) {
    const message = (payload as { message?: unknown }).message;
    if (typeof message === 'string') {
      return message;
    }
  }

  return fallback;
}

async function parseResponse<T>(response: Response, fallbackError: string): Promise<T> {
  if (!response.ok) {
    let message = fallbackError;
    try {
      const payload = await response.json();
      message = extractErrorMessage(payload, fallbackError);
    } catch {
      // Keep fallback message when payload is not JSON.
    }
    throw new Error(message);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export async function listBenchmarks(q?: string, category?: string): Promise<Benchmark[]> {
  const url = new URL(`${API_URL}/problems`);
  if (q && q.trim()) {
    url.searchParams.set('q', q.trim());
  }
  if (category && category.trim()) {
    url.searchParams.set('category', category.trim());
  }

  const response = await fetch(url.toString());
  const data = await parseResponse<ListResponse<Benchmark>>(response, 'Unable to load benchmarks.');

  return Array.isArray(data) ? data : data.items;
}

export async function listSolvers(q?: string, category?: string): Promise<Solver[]> {
  const url = new URL(`${API_URL}/solvers`);
  if (q && q.trim()) {
    url.searchParams.set('q', q.trim());
  }
  if (category && category.trim()) {
    url.searchParams.set('category', category.trim());
  }

  const response = await fetch(url.toString());
  const data = await parseResponse<ListResponse<Solver>>(response, 'Unable to load solvers.');

  return Array.isArray(data) ? data : data.items;
}

export async function downloadBenchmark(id: number): Promise<Blob> {
  const response = await fetch(`${API_URL}/problems/${id}/download`);
  if (!response.ok) {
    throw new Error('Benchmark download failed.');
  }
  return response.blob();
}

export async function downloadSolver(id: number): Promise<Blob> {
  const response = await fetch(`${API_URL}/solvers/${id}/download`);
  if (!response.ok) {
    throw new Error('Solver download failed.');
  }
  return response.blob();
}
