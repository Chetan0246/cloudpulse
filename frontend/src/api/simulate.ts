import { apiClient } from './client';
import type { FailureType, IncidentSeverity, SimulateResponse } from './types';

export const simulateApi = {
  inject: (
    resourceId: string,
    failureType: FailureType,
    severity?: IncidentSeverity,
    parameters?: Record<string, any>
  ): Promise<SimulateResponse> =>
    apiClient
      .post<SimulateResponse>('/simulate/failure', {
        resource_id: resourceId,
        failure_type: failureType,
        ...(severity ? { severity } : {}),
        ...(parameters ? { parameters } : {}),
      })
      .catch((err) => {
        // Fallback to alias if /simulate/failure is not available
        if (err.response?.status === 404) {
          return apiClient
            .post<SimulateResponse>('/simulate/inject', {
              resource_id: resourceId,
              failure_type: failureType,
              ...(severity ? { severity } : {}),
              ...(parameters ? { parameters } : {}),
            })
            .then((r) => r.data);
        }
        throw err;
      })
      .then((r) => (r as any).data || r),

  reset: (resourceId: string): Promise<SimulateResponse> =>
    apiClient
      .post<SimulateResponse>(`/simulate/reset/${resourceId}`)
      .then((r) => r.data),

  recover: (resourceId: string): Promise<SimulateResponse> =>
    apiClient
      .post<SimulateResponse>('/simulate/recover', { resource_id: resourceId })
      .then((r) => r.data),
};
