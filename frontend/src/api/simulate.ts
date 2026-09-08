import { apiClient } from './client';
import type { FailureType, Resource, SimulateResponse } from './types';

export const simulateApi = {
  inject: (resourceId: string, failureType: FailureType): Promise<SimulateResponse> =>
    apiClient
      .post<SimulateResponse>('/simulate/inject', {
        resource_id: resourceId,
        failure_type: failureType,
      })
      .then((r) => r.data),

  reset: (resourceId: string): Promise<SimulateResponse> =>
    apiClient
      .post<SimulateResponse>(`/simulate/reset/${resourceId}`)
      .then((r) => r.data),
};
