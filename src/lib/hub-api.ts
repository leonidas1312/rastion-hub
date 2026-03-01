export interface User {
  id: number;
  username: string;
  avatar_url: string;
}

export interface DecisionPlugin {
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

const DECISION_PLUGIN_CATEGORY_RULES: Array<[string, string]> = [
  ['calendar', 'Scheduling'],
  ['schedule', 'Scheduling'],
  ['planner', 'Scheduling'],
  ['planning', 'Scheduling'],
  ['knapsack', 'Combinatorial'],
  ['set_cover', 'Combinatorial'],
  ['maxcut', 'Graph'],
  ['graph', 'Graph'],
  ['portfolio', 'Portfolio'],
  ['tsp', 'Routing'],
  ['route', 'Routing'],
  ['vehicle', 'Routing']
];

const SOLVER_CATEGORY_RULES: Array<[string, string]> = [
  ['qubo', 'QUBO'],
  ['qaoa', 'Quantum'],
  ['quantum', 'Quantum'],
  ['tabu', 'Heuristic'],
  ['grasp', 'Heuristic'],
  ['baseline', 'Heuristic'],
  ['highs', 'MILP'],
  ['ortools', 'MILP'],
  ['scip', 'MILP'],
  ['mip', 'MILP'],
  ['milp', 'MILP'],
  ['qp', 'QP']
];

type ListResponse<T> =
  | T[]
  | {
      items: T[];
      total: number;
      page: number;
      page_size: number;
    };

export interface PaginatedResult<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
  hasMore: boolean;
}

function defaultApiUrl(): string {
  if (import.meta.env.DEV && typeof window !== 'undefined') {
    return `${window.location.protocol}//${window.location.hostname}:8000`;
  }
  return 'https://rastion-hub.onrender.com';
}

export const API_URL = (import.meta.env.PUBLIC_HUB_API_URL || defaultApiUrl()).replace(/\/$/, '');
const API_TIMEOUT_MS = 25000;

function normalizeCategory(value?: string | null): string | null {
  const cleaned = value?.trim();
  return cleaned ? cleaned : null;
}

export function resolveDecisionPluginCategory(plugin: DecisionPlugin): string {
  const explicit = normalizeCategory(plugin.category);
  if (explicit) {
    return explicit;
  }

  const haystack = `${plugin.name} ${plugin.description || ''}`.toLowerCase();
  for (const [token, category] of DECISION_PLUGIN_CATEGORY_RULES) {
    if (haystack.includes(token)) {
      return category;
    }
  }
  return 'General';
}

export function resolveSolverCategory(solver: Solver): string {
  const explicit = normalizeCategory(solver.category);
  if (explicit) {
    return explicit;
  }

  const haystack = `${solver.name} ${solver.description || ''}`.toLowerCase();
  for (const [token, category] of SOLVER_CATEGORY_RULES) {
    if (haystack.includes(token)) {
      return category;
    }
  }
  return 'General';
}

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

async function fetchJsonWithTimeout<T>(url: string, fallbackError: string): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), API_TIMEOUT_MS);

  try {
    const response = await fetch(url, { signal: controller.signal });
    return await parseResponse<T>(response, fallbackError);
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new Error(`Hub API request timed out after ${Math.round(API_TIMEOUT_MS / 1000)}s.`);
    }

    if (error instanceof TypeError) {
      throw new Error(
        `Unable to reach hub API at ${API_URL}. Check backend availability and CORS settings.`
      );
    }

    throw error;
  } finally {
    clearTimeout(timer);
  }
}

function toPaginatedResult<T>(
  payload: ListResponse<T>,
  fallbackPage: number,
  fallbackPageSize: number
): PaginatedResult<T> {
  if (Array.isArray(payload)) {
    return {
      items: payload,
      total: payload.length,
      page: fallbackPage,
      pageSize: fallbackPageSize,
      hasMore: false
    };
  }

  const total = Number.isFinite(payload.total) ? Number(payload.total) : payload.items.length;
  const page = Number.isFinite(payload.page) ? Number(payload.page) : fallbackPage;
  const pageSize = Number.isFinite(payload.page_size) ? Number(payload.page_size) : fallbackPageSize;
  const shownSoFar = page * pageSize;

  return {
    items: payload.items,
    total,
    page,
    pageSize,
    hasMore: shownSoFar < total
  };
}

export async function listDecisionPlugins(q?: string, category?: string): Promise<DecisionPlugin[]> {
  const paged = await listDecisionPluginsPage(q, category, 1, 100);
  return paged.items;
}

export async function listDecisionPluginsPage(
  q?: string,
  category?: string,
  page = 1,
  pageSize = 20
): Promise<PaginatedResult<DecisionPlugin>> {
  const url = new URL(`${API_URL}/decision-plugins`);
  if (q && q.trim()) {
    url.searchParams.set('q', q.trim());
  }
  if (category && category.trim()) {
    url.searchParams.set('category', category.trim());
  }
  url.searchParams.set('page', String(Math.max(1, Math.floor(page))));
  url.searchParams.set('page_size', String(Math.max(1, Math.floor(pageSize))));

  const data = await fetchJsonWithTimeout<ListResponse<DecisionPlugin>>(
    url.toString(),
    'Unable to load decision plugins.'
  );

  return toPaginatedResult(data, page, pageSize);
}

export async function listSolvers(q?: string, category?: string): Promise<Solver[]> {
  const url = new URL(`${API_URL}/solvers`);
  if (q && q.trim()) {
    url.searchParams.set('q', q.trim());
  }
  if (category && category.trim()) {
    url.searchParams.set('category', category.trim());
  }

  const data = await fetchJsonWithTimeout<ListResponse<Solver>>(
    url.toString(),
    'Unable to load solvers.'
  );

  return Array.isArray(data) ? data : data.items;
}

export async function downloadDecisionPlugin(id: number): Promise<Blob> {
  const response = await fetch(`${API_URL}/decision-plugins/${id}/download`);
  if (!response.ok) {
    throw new Error('Decision plugin download failed.');
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
