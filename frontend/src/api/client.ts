/**
 * Axios HTTP client configured with API base URL, timeout, error normalization,
 * and safe retry logic for idempotent GET operations.
 */
import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string) || 'http://localhost:8000';

interface CustomRequestConfig extends InternalAxiosRequestConfig {
  _retryCount?: number;
}

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 10_000,
});

const MAX_RETRIES = 2;
const RETRY_DELAY_BASE_MS = 1000;

// Retry interceptor: ONLY retries safe/idempotent GET and HEAD requests on transient failures
apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const config = error.config as CustomRequestConfig | undefined;

    // Normalize error message for callers
    const errorData = error.response?.data as any;
    const normalizedMessage =
      errorData?.detail ||
      errorData?.message ||
      error.message ||
      'An unexpected network error occurred';

    // Enhance error object
    (error as any).normalizedMessage = normalizedMessage;

    if (!config) {
      return Promise.reject(error);
    }

    const method = (config.method || 'GET').toUpperCase();
    const isIdempotent = method === 'GET' || method === 'HEAD';

    // Transient status codes: 502 Bad Gateway, 503 Service Unavailable, 504 Gateway Timeout
    const isTransientError =
      !error.response ||
      error.response.status === 502 ||
      error.response.status === 503 ||
      error.response.status === 504 ||
      error.code === 'ECONNABORTED' ||
      error.code === 'ERR_NETWORK';

    // Only retry safe GET requests on transient network/server errors
    if (isIdempotent && isTransientError) {
      config._retryCount = config._retryCount || 0;

      if (config._retryCount < MAX_RETRIES) {
        config._retryCount += 1;
        const delay = RETRY_DELAY_BASE_MS * Math.pow(2, config._retryCount - 1);

        console.warn(
          `[CloudPulse API] Retrying idempotent request (${config._retryCount}/${MAX_RETRIES}) ` +
          `to ${config.url} after ${delay}ms...`
        );

        await new Promise((resolve) => setTimeout(resolve, delay));
        return apiClient(config);
      }
    }

    console.error(`[API Error] ${method} ${config.url}:`, normalizedMessage);
    return Promise.reject(error);
  }
);
