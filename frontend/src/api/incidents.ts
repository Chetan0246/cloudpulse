import { apiClient } from './client';
import type { Incident, IncidentSummary } from './types';

export const incidentsApi = {
  list: (params?: { resource_id?: string; status?: string; limit?: number }): Promise<IncidentSummary[]> =>
    apiClient.get<IncidentSummary[]>('/incidents/', { params }).then((r) => r.data),

  get: (incidentId: string): Promise<Incident> =>
    apiClient.get<Incident>(`/incidents/${incidentId}`).then((r) => r.data),
};
