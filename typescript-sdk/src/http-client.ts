/**
 * HTTP Client for OpenClaw Control Plane
 */

import axios, { AxiosInstance, AxiosError } from 'axios';
import {
  HeartbeatRequest,
  HeartbeatResponse,
  ExecuteRequest,
  ExecuteResponse,
  TaskPayload,
  TaskResult,
} from './types';

export class HttpClient {
  private client: AxiosInstance;

  constructor(baseURL: string) {
    this.client = axios.create({
      baseURL,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    });
  }

  /**
   * Send worker heartbeat
   */
  async sendHeartbeat(request: HeartbeatRequest): Promise<HeartbeatResponse> {
    try {
      const response = await this.client.post<HeartbeatResponse>(
        '/api/v1/worker/heartbeat',
        request
      );
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  /**
   * Register a new worker
   */
  async registerWorker(
    workerId: string,
    capabilities: Record<string, string>
  ): Promise<{ worker_id: string; status: string }> {
    try {
      const response = await this.client.post('/api/v1/worker/register', {
        worker_id: workerId,
        capabilities,
      });
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  /**
   * Report task result
   */
  async reportTaskResult(
    workerId: string,
    taskId: string,
    result: TaskResult
  ): Promise<{ acknowledged: boolean }> {
    try {
      const response = await this.client.post('/api/v1/task/result', {
        worker_id: workerId,
        task_id: taskId,
        result,
      });
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  /**
   * Request next task from queue
   */
  async requestTask(workerId: string): Promise<TaskPayload | null> {
    try {
      const response = await this.client.get<{ task: TaskPayload | null }>(
        '/api/v1/worker/task',
        {
          params: { worker_id: workerId },
        }
      );
      return response.data.task;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  private handleError(error: unknown): Error {
    if (error instanceof AxiosError) {
      const message = error.response?.data?.message || error.message;
      return new Error(`ControlPlane Error: ${message}`);
    }
    return error instanceof Error ? error : new Error('Unknown error');
  }
}

/**
 * Create HTTP client from base URL
 */
export function createHttpClient(baseURL: string): HttpClient {
  return new HttpClient(baseURL);
}