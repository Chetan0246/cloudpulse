import { describe, it, expect, vi, beforeEach } from 'vitest';
import { healthApi } from '../../api/health';
import { resourcesApi } from '../../api/resources';
import { incidentsApi } from '../../api/incidents';
import { metricsApi } from '../../api/metrics';
import { simulateApi } from '../../api/simulate';
import { apiClient } from '../../api/client';

describe('API Client & Endpoints Integration', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  describe('healthApi', () => {
    it('calls GET /health and returns liveness probe', async () => {
      vi.spyOn(apiClient, 'get').mockResolvedValue({
        data: { status: 'ok', service: 'cloudpulse-api' },
      });

      const res = await healthApi.check();
      expect(apiClient.get).toHaveBeenCalledWith('/health');
      expect(res.status).toBe('ok');
    });

    it('calls GET /health/ready and returns readiness probe', async () => {
      vi.spyOn(apiClient, 'get').mockResolvedValue({
        data: { status: 'ready', service: 'cloudpulse-api' },
      });

      const res = await healthApi.ready();
      expect(apiClient.get).toHaveBeenCalledWith('/health/ready');
      expect(res.status).toBe('ready');
    });
  });

  describe('resourcesApi', () => {
    it('calls GET /resources/ to list virtual resources', async () => {
      vi.spyOn(apiClient, 'get').mockResolvedValue({
        data: [{ resource_id: 'VM-001', current_state: 'HEALTHY' }],
      });

      const list = await resourcesApi.list();
      expect(apiClient.get).toHaveBeenCalledWith('/resources/');
      expect(list).toHaveLength(1);
    });

    it('calls GET /resources/{id} to get single resource', async () => {
      vi.spyOn(apiClient, 'get').mockResolvedValue({
        data: { resource_id: 'VM-001', cpu_utilization: 25.0 },
      });

      const res = await resourcesApi.get('VM-001');
      expect(apiClient.get).toHaveBeenCalledWith('/resources/VM-001');
      expect(res.resource_id).toBe('VM-001');
    });
  });

  describe('incidentsApi', () => {
    it('calls GET /incidents/ with query params', async () => {
      vi.spyOn(apiClient, 'get').mockResolvedValue({
        data: [{ incident_id: 'inc-123', status: 'OPEN' }],
      });

      const res = await incidentsApi.list({ status: 'OPEN', limit: 50 });
      expect(apiClient.get).toHaveBeenCalledWith('/incidents/', {
        params: { status: 'OPEN', limit: 50 },
      });
      expect(res).toHaveLength(1);
    });

    it('calls GET /incidents/{id}', async () => {
      vi.spyOn(apiClient, 'get').mockResolvedValue({
        data: { incident_id: 'inc-123', severity: 'HIGH' },
      });

      const res = await incidentsApi.get('inc-123');
      expect(apiClient.get).toHaveBeenCalledWith('/incidents/inc-123');
      expect(res.incident_id).toBe('inc-123');
    });
  });

  describe('metricsApi', () => {
    it('calls GET /metrics with window_type', async () => {
      vi.spyOn(apiClient, 'get').mockResolvedValue({
        data: [{ resource_id: 'VM-001', availability_pct: 99.98 }],
      });

      const res = await metricsApi.list({ window_type: 'DAILY' });
      expect(apiClient.get).toHaveBeenCalledWith('/metrics', {
        params: { window_type: 'DAILY' },
      });
      expect(res).toHaveLength(1);
    });

    it('calls GET /metrics/{resource_id}', async () => {
      vi.spyOn(apiClient, 'get').mockResolvedValue({
        data: { resource_id: 'VM-001', mttr_seconds: 5.2 },
      });

      const res = await metricsApi.getLatest('VM-001', 'WEEKLY');
      expect(apiClient.get).toHaveBeenCalledWith('/metrics/VM-001', {
        params: { window_type: 'WEEKLY' },
      });
      expect(res.mttr_seconds).toBe(5.2);
    });

    it('calls GET /metrics/overview', async () => {
      vi.spyOn(apiClient, 'get').mockResolvedValue({
        data: {
          incident_count: 5,
          recovery_success_rate_pct: 100.0,
          recovery_failure_rate_pct: 0.0,
          avg_recovery_time_seconds: 6.4,
          mttr_seconds: 8.2,
          avg_detection_time_seconds: 4.1,
          incident_frequency_per_hour: 1.25,
          incident_frequency_per_day: 30.0,
          mtbf_seconds: 2880,
          health_distribution: {
            total_resources: 4,
            healthy_count: 4,
            warning_count: 0,
            failed_count: 0,
            recovering_count: 0,
            healthy_pct: 100.0,
            by_state: { HEALTHY: 4 },
            by_status: { HEALTHY: 4 },
          },
        },
      });

      const res = await metricsApi.getOverview('DAILY');
      expect(apiClient.get).toHaveBeenCalledWith('/metrics/overview', {
        params: { window_type: 'DAILY' },
      });
      expect(res.incident_count).toBe(5);
      expect(res.health_distribution.healthy_pct).toBe(100.0);
    });
  });

  describe('simulateApi', () => {
    it('calls POST /simulate/failure with injected payload', async () => {
      vi.spyOn(apiClient, 'post').mockResolvedValue({
        data: {
          message: 'Failure injected',
          scenario_id: 'FS-01',
          resource: { resource_id: 'VM-001', current_state: 'FAILURE_DETECTED' },
        },
      });

      const res = await simulateApi.inject('VM-001', 'HIGH_CPU', 'HIGH');
      expect(apiClient.post).toHaveBeenCalledWith('/simulate/failure', {
        resource_id: 'VM-001',
        failure_type: 'HIGH_CPU',
        severity: 'HIGH',
      });
      expect(res.message).toBe('Failure injected');
    });

    it('calls POST /simulate/reset/{id}', async () => {
      vi.spyOn(apiClient, 'post').mockResolvedValue({
        data: { message: 'Reset successful' },
      });

      const res = await simulateApi.reset('VM-001');
      expect(apiClient.post).toHaveBeenCalledWith('/simulate/reset/VM-001');
      expect(res.message).toBe('Reset successful');
    });

    it('calls POST /simulate/recover with resource_id', async () => {
      vi.spyOn(apiClient, 'post').mockResolvedValue({
        data: { message: 'Recovered' },
      });

      const res = await simulateApi.recover('VM-001');
      expect(apiClient.post).toHaveBeenCalledWith('/simulate/recover', {
        resource_id: 'VM-001',
      });
      expect(res.message).toBe('Recovered');
    });
  });
});
