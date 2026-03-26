/**
 * OpenClaw Worker - Main Worker Implementation
 */

import { EventEmitter } from 'events';
import {
  WorkerConfig,
  TaskPayload,
  TaskResult,
  SDKOptions,
  WorkerStatus,
} from './types';
import { HttpClient, createHttpClient } from './http-client';

const DEFAULT_MAX_CONCURRENT_TASKS = 3;
const DEFAULT_TASK_TIMEOUT_SECONDS = 300;
const DEFAULT_HEARTBEAT_INTERVAL_SECONDS = 30;

export class Worker extends EventEmitter {
  private config: WorkerConfig;
  private httpClient: HttpClient;
  private status: WorkerStatus = 'idle';
  private running = false;
  private heartbeatTimer?: NodeJS.Timeout;
  private taskQueue: TaskPayload[] = [];
  private currentTasks: Map<string, TaskPayload> = new Map();
  
  // Callbacks
  private onTaskReceived?: (task: TaskPayload) => Promise<TaskResult>;
  private onError?: (error: Error) => void;

  constructor(options: SDKOptions) {
    super();
    
    this.config = {
      workerId: options.workerId || `worker-${Date.now()}`,
      capabilities: options.capabilities || {},
      maxConcurrentTasks: options.maxConcurrentTasks || DEFAULT_MAX_CONCURRENT_TASKS,
      taskTimeoutSeconds: options.taskTimeoutSeconds || DEFAULT_TASK_TIMEOUT_SECONDS,
      heartbeatIntervalSeconds: options.heartbeatIntervalSeconds || DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
      controlPlaneUrl: options.controlPlaneUrl || 'http://localhost:8080',
    };
    
    this.httpClient = createHttpClient(this.config.controlPlaneUrl!);
    this.onTaskReceived = options.onTaskReceived;
    this.onError = options.onError;
  }

  /**
   * Start the worker
   */
  async start(): Promise<void> {
    if (this.running) {
      throw new Error('Worker is already running');
    }

    this.running = true;
    this.status = 'running';
    
    try {
      // Register worker
      await this.httpClient.registerWorker(
        this.config.workerId!,
        this.config.capabilities!
      );
      
      this.emit('started');
      
      // Start heartbeat
      this.startHeartbeat();
      
      // Start processing tasks
      this.startTaskProcessor();
      
    } catch (error) {
      this.running = false;
      this.status = 'error';
      const err = error instanceof Error ? error : new Error('Failed to start worker');
      this.handleError(err);
      throw err;
    }
  }

  /**
   * Stop the worker
   */
  async stop(): Promise<void> {
    if (!this.running) {
      return;
    }

    this.running = false;
    this.status = 'stopped';
    
    // Stop heartbeat
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = undefined;
    }
    
    this.emit('stopped');
  }

  /**
   * Get current worker status
   */
  getStatus(): WorkerStatus {
    return this.status;
  }

  /**
   * Get worker ID
   */
  getWorkerId(): string {
    return this.config.workerId!;
  }

  /**
   * Update worker capabilities
   */
  async updateCapabilities(capabilities: Record<string, string>): Promise<void> {
    this.config.capabilities = capabilities;
    
    if (this.running) {
      await this.sendHeartbeat();
    }
  }

  /**
   * Manually trigger heartbeat
   */
  async sendHeartbeat(): Promise<void> {
    try {
      const response = await this.httpClient.sendHeartbeat({
        worker_id: this.config.workerId!,
        capabilities: this.config.capabilities!,
        cpu_usage: this.getCpuUsage(),
        memory_usage: this.getMemoryUsage(),
        queue_depth: this.taskQueue.length,
        model_available: true,
      });
      
      this.emit('heartbeat', response);
    } catch (error) {
      this.handleError(error instanceof Error ? error : new Error('Heartbeat failed'));
    }
  }

  /**
   * Submit a task result to control plane
   */
  async submitTaskResult(taskId: string, result: TaskResult): Promise<void> {
    try {
      await this.httpClient.reportTaskResult(
        this.config.workerId!,
        taskId,
        result
      );
      this.currentTasks.delete(taskId);
      this.emit('taskCompleted', taskId, result);
    } catch (error) {
      this.handleError(error instanceof Error ? error : new Error('Failed to submit result'));
    }
  }

  /**
   * Register a task handler
   */
  onTask(handler: (task: TaskPayload) => Promise<TaskResult>): void {
    this.onTaskReceived = handler;
  }

  // Private methods

  private startHeartbeat(): void {
    const intervalMs = (this.config.heartbeatIntervalSeconds || DEFAULT_HEARTBEAT_INTERVAL_SECONDS) * 1000;
    
    this.heartbeatTimer = setInterval(() => {
      this.sendHeartbeat();
    }, intervalMs);
    
    // Send initial heartbeat
    this.sendHeartbeat();
  }

  private startTaskProcessor(): void {
    const processLoop = async () => {
      while (this.running) {
        try {
          // Check if we can accept more tasks
          if (this.currentTasks.size >= (this.config.maxConcurrentTasks || DEFAULT_MAX_CONCURRENT_TASKS)) {
            await this.sleep(1000);
            continue;
          }
          
          // Try to get a task
          const task = await this.httpClient.requestTask(this.config.workerId!);
          
          if (task) {
            await this.processTask(task);
          } else {
            await this.sleep(2000); // Wait before next poll
          }
        } catch (error) {
          this.handleError(error instanceof Error ? error : new Error('Task processing error'));
          await this.sleep(5000); // Wait longer on error
        }
      }
    };
    
    processLoop();
  }

  private async processTask(task: TaskPayload): Promise<void> {
    this.currentTasks.set(task.task_id, task);
    this.emit('taskReceived', task);
    
    const startTime = Date.now();
    
    try {
      let result: TaskResult;
      
      if (this.onTaskReceived) {
        result = await this.onTaskReceived(task);
      } else {
        // Default no-op handler
        result = {
          task_id: task.task_id,
          success: true,
          output: 'Task processed (no handler registered)',
          execution_time_ms: Date.now() - startTime,
        };
      }
      
      // Submit result
      await this.submitTaskResult(task.task_id, result);
      
    } catch (error) {
      // Submit error result
      const errorResult: TaskResult = {
        task_id: task.task_id,
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
        execution_time_ms: Date.now() - startTime,
      };
      
      await this.submitTaskResult(task.task_id, errorResult);
    }
  }

  private getCpuUsage(): number {
    // In browser/Node.js, we'd use process.cpuUsage()
    // For now, return placeholder
    return 0;
  }

  private getMemoryUsage(): number {
    // In browser/Node.js, we'd use process.memoryUsage()
    // For now, return placeholder
    return 0;
  }

  private handleError(error: Error): void {
    this.emit('error', error);
    if (this.onError) {
      this.onError(error);
    }
  }

  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

/**
 * Create a new Worker instance
 */
export function createWorker(options: SDKOptions): Worker {
  return new Worker(options);
}

/**
 * Convenience function to start a worker with a task handler
 */
export async function startWorker(
  options: SDKOptions,
  taskHandler: (task: TaskPayload) => Promise<TaskResult>
): Promise<Worker> {
  const worker = new Worker({
    ...options,
    onTaskReceived: taskHandler,
  });
  
  await worker.start();
  return worker;
}