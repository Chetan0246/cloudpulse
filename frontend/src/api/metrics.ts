import { apiClient } from './client';
import type { ReliabilityMetric, FleetReliabilityOverview } from './types';

export const metricsApi = {
  list: (params?: { resource_id?: string; window_type?: string; limit?: number }): Promise<ReliabilityMetric[]> =>
    apiClient.get<ReliabilityMetric[]>('/metrics', { params }).then((r) => r.data),

  getLatest: (resourceId: string, windowType: string = 'DAILY'): Promise<ReliabilityMetric> =>
    apiClient
      .get<ReliabilityMetric>(`/metrics/${resourceId}`, {
        params: { window_type: windowType },
      })
      .then((r) => r.data),

  getOverview: (windowType: string = 'DAILY'): Promise<FleetReliabilityOverview> =>
    apiClient
      .get<FleetReliabilityOverview>('/metrics/overview', {
        params: { window_type: windowType },
      })
      .then((r) => r.data),
};

