const API_BASE = 'http://localhost:8000/api';

type HealthResponse = {
  status: string;
  message: string;
};

/** Stage 1 client: health check only. Later-stage endpoints are not implemented yet. */
export const api = {
  getHealth: async (): Promise<HealthResponse> => {
    const res = await fetch(`${API_BASE}/health`);
    if (!res.ok) {
      throw new Error(`Health check failed: ${res.status}`);
    }
    return res.json();
  },
};
