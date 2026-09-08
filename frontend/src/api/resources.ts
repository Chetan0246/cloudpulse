import { apiClient } from './client';
import type { Resource, ResourceSummary } from './types';

export const resourcesApi = {
  list: (): Promise<ResourceSummary[]> =>
    apiClient.get<ResourceSummary[]>('/resources/').then((r) => r.data),

  get: (resourceId: string): Promise<Resource> =>
    apiClient.get<Resource>(`/resources/${resourceId}`).then((r) => r.data),
};
