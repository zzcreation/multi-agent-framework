/**
 * OpenClaw Worker SDK - Basic Usage Example
 * 
 * This example demonstrates how to create a simple worker
 * that connects to the OpenClaw control plane.
 */

import { startWorker, TaskPayload, TaskResult } from './src/index';

/**
 * Example task handler
 * Replace this with your actual task processing logic
 */
async function handleTask(task: TaskPayload): Promise<TaskResult> {
  console.log(`[Worker] Received task: ${task.task_id}`);
  console.log(`[Worker] Task content: ${task.task}`);
  console.log(`[Worker] Priority: ${task.priority}`);
  
  // Simulate task processing
  const startTime = Date.now();
  
  // Your task processing logic here
  // For example, call an LLM API, run a function, etc.
  
  // Simulate some work
  await new Promise(resolve => setTimeout(resolve, 100));
  
  const executionTime = Date.now() - startTime;
  
  return {
    task_id: task.task_id,
    success: true,
    output: `Processed: ${task.task}`,
    execution_time_ms: executionTime,
    metadata: {
      worker: 'example-worker',
      processed_at: new Date().toISOString(),
    },
  };
}

/**
 * Main function to start the worker
 */
async function main() {
  const worker = await startWorker(
    {
      // Control plane URL (can also use CONTROL_PLANE_URL env var)
      controlPlaneUrl: process.env.CONTROL_PLANE_URL || 'http://localhost:8080',
      
      // Unique worker ID (auto-generated if not provided)
      workerId: process.env.WORKER_ID || 'example-worker-' + Date.now(),
      
      // Worker capabilities
      capabilities: {
        model: 'gpt-4',
        toolset: 'default',
        max_tokens: '4096',
      },
      
      // Optional configuration
      maxConcurrentTasks: 3,
      taskTimeoutSeconds: 300,
      heartbeatIntervalSeconds: 30,
      
      // Error handler
      onError: (error) => {
        console.error('[Worker] Error:', error.message);
      },
    },
    handleTask
  );
  
  console.log(`[Worker] Started with ID: ${worker.getWorkerId()}`);
  
  // Handle graceful shutdown
  process.on('SIGINT', async () => {
    console.log('[Worker] Shutting down...');
    await worker.stop();
    process.exit(0);
  });
  
  process.on('SIGTERM', async () => {
    console.log('[Worker] Shutting down...');
    await worker.stop();
    process.exit(0);
  });
}

// Run the example
main().catch(console.error);