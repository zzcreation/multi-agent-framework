/**
 * OpenClaw TypeScript Worker SDK
 * 
 * A TypeScript SDK for building OpenClaw Workers
 * 
 * @example
 * ```typescript
 * import { startWorker, TaskPayload, TaskResult } from '@openclaw/worker-sdk';
 * 
 * async function myTaskHandler(task: TaskPayload): Promise<TaskResult> {
 *   console.log('Processing task:', task.task);
 *   
 *   return {
 *     task_id: task.task_id,
 *     success: true,
 *     output: 'Task completed!',
 *     execution_time_ms: 100,
 *   };
 * }
 * 
 * await startWorker({
 *   workerId: 'my-worker',
 *   capabilities: { model: 'gpt-4', toolset: 'default' },
 *   controlPlaneUrl: 'http://localhost:8080',
 * }, myTaskHandler);
 * ```
 */

export {
  Worker,
  createWorker,
  startWorker,
} from './worker';

export {
  HttpClient,
  createHttpClient,
} from './http-client';

export {
  WorkerConfig,
  TaskPayload,
  TaskResult,
  HeartbeatRequest,
  HeartbeatResponse,
  ExecuteRequest,
  ExecuteResponse,
  SDKOptions,
  WorkerStatus,
} from './types';