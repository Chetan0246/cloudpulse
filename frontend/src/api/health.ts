import { apiClient } from './client';

export interface HealthResponse {
  status: string;
  service: string;
}

export const healthApi = {
  check: (): Promise<HealthResponse> =>
    apiClient.get<HealthResponse>('/health').then((r) => r.data),

  ready: (): Promise<HealthResponse> =>
    apiClient.get<HealthResponse>('/health/ready').then((r) => r.data),
};
