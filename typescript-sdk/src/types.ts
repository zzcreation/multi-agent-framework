/**
 * OpenClaw Worker SDK - Type Definitions
 */

/**
 * Worker configuration
 */
export interface WorkerConfig {
  workerId: string;
  capabilities: Record<string, string>;
  maxConcurrentTasks?: number;
  taskTimeoutSeconds?: number;
  heartbeatIntervalSeconds?: number;
  controlPlaneUrl?: string;
}

/**
 * Task payload from control plane
 */
export interface TaskPayload {
  task_id: string;
  task: string;
  priority?: number;
  deadline?: string;
  payload: Record<string, unknown>;
  required_review?: boolean;
  required_sandbox?: boolean;
  required_toolset?: string;
  tenant_id?: string;
}

/**
 * Task execution result
 */
export interface TaskResult {
  task_id: string;
  success: boolean;
  output?: string;
  error?: string;
  execution_time_ms?: number;
  metadata?: Record<string, unknown>;
}

/**
 * Worker heartbeat request
 */
export interface HeartbeatRequest {
  worker_id: string;
  capabilities: Record<string, string>;
  cpu_usage: number;
  memory_usage: number;
  queue_depth: number;
  model_available: boolean;
}

/**
 * Worker heartbeat response
 */
export interface HeartbeatResponse {
  worker_id: string;
  status: 'alive';
  capabilities: Record<string, string>;
  health_status?: string;
  health_score?: number;
}

/**
 * Task execution request from control plane
 */
export interface ExecuteRequest {
  worker_id: string;
  task: TaskPayload;
  agent_type: string;
}

/**
 * Task execution response
 */
export interface ExecuteResponse {
  result: TaskResult;
  preempted: boolean;
  compensation?: Record<string, unknown>;
}

/**
 * SDK initialization options
 */
export interface SDKOptions {
  controlPlaneUrl?: string;
  workerId?: string;
  capabilities?: Record<string, string>;
  maxConcurrentTasks?: number;
  taskTimeoutSeconds?: number;
  heartbeatIntervalSeconds?: number;
  onTaskReceived?: (task: TaskPayload) => Promise<TaskResult>;
  onError?: (error: Error) => void;
}

/**
 * Worker runtime status
 */
export type WorkerStatus = 'idle' | 'running' | 'stopped' | 'error';