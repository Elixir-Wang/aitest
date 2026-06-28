/**
 * API client for page exploration
 */

export interface CreateExplorationRequest {
  project_id: string;
  start_url: string;
  scope?: string;
  max_depth?: number;
  max_pages?: number;
  max_duration_seconds?: number;
}

export interface ExplorationRun {
  run_id: string;
  project_id: string;
  start_url: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  created_at: string;
  started_at?: string;
  completed_at?: string;
  pages_discovered: number;
  duration_seconds?: number;
  error?: string;
}

export interface PageArtifact {
  page_id: string;
  title: string;
  normalized_path: string;
  explored_at: string;
  elements: PageElement[];
}

export interface PageElement {
  id: string;
  name: string;
  role: string;
  locators: ElementLocator[];
}

export interface ElementLocator {
  kind: string;
  code: string;
  priority: number;
  validation?: {
    is_unique: boolean;
    is_visible: boolean;
  };
}

class ExplorationAPI {
  private baseUrl = '/api/exploration';

  /**
   * Create a new exploration run
   */
  async createRun(request: CreateExplorationRequest): Promise<ExplorationRun> {
    const response = await fetch(`${this.baseUrl}/runs`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || 'Failed to create exploration run');
    }

    return response.json();
  }

  /**
   * Get exploration run status
   */
  async getRun(runId: string): Promise<ExplorationRun> {
    const response = await fetch(`${this.baseUrl}/runs/${runId}`);

    if (!response.ok) {
      if (response.status === 404) {
        throw new Error('Run not found');
      }
      throw new Error('Failed to get run status');
    }

    return response.json();
  }

  /**
   * Get all runs for a project
   */
  async getProjectRuns(projectId: string): Promise<ExplorationRun[]> {
    // This endpoint would need to be implemented in the backend
    const response = await fetch(`${this.baseUrl}/projects/${projectId}/runs`);

    if (!response.ok) {
      throw new Error('Failed to get project runs');
    }

    return response.json();
  }

  /**
   * Get page artifact
   */
  async getPageArtifact(projectId: string, pageId: string): Promise<PageArtifact> {
    // This endpoint would need to be implemented in the backend
    const response = await fetch(
      `/api/projects/${projectId}/page_exploration/pages/${pageId}`
    );

    if (!response.ok) {
      if (response.status === 404) {
        throw new Error('Page not found');
      }
      throw new Error('Failed to get page artifact');
    }

    return response.json();
  }

  /**
   * List all pages for a project
   */
  async listPages(projectId: string): Promise<PageArtifact[]> {
    // This endpoint would need to be implemented in the backend
    const response = await fetch(
      `/api/projects/${projectId}/page_exploration/pages`
    );

    if (!response.ok) {
      throw new Error('Failed to list pages');
    }

    return response.json();
  }
}

export const explorationAPI = new ExplorationAPI();
