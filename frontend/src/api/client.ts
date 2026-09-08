/**
 * Axios HTTP client configured with the API base URL.
 *
 * VITE_API_BASE_URL is injected at build time from .env.local.
 * In production, this is the API Gateway URL output from sam deploy.
 */
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL as string;

if (!API_BASE_URL) {
  console.error(
    '[CloudPulse] VITE_API_BASE_URL is not set. ' +
    'Copy .env.example to .env.local and set the value.'
  );
}

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 10_000,
});

// Log errors in development
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('[API Error]', error.response?.data ?? error.message);
    return Promise.reject(error);
  }
);
