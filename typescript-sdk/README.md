# OpenClaw TypeScript Worker SDK

TypeScript SDK for building OpenClaw Workers.

## Installation

```bash
npm install @openclaw/worker-sdk
```

## Quick Start

```typescript
import { startWorker, TaskPayload, TaskResult } from '@openclaw/worker-sdk';

async function myTaskHandler(task: TaskPayload): Promise<TaskResult> {
  // Process the task
  return {
    task_id: task.task_id,
    success: true,
    output: 'Task completed!',
    execution_time_ms: 100,
  };
}

await startWorker({
  workerId: 'my-worker',
  capabilities: { model: 'gpt-4', toolset: 'default' },
  controlPlaneUrl: 'http://localhost:8080',
}, myTaskHandler);
```

## Configuration

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `controlPlaneUrl` | string | `http://localhost:8080` | Control plane URL |
| `workerId` | string | Auto-generated | Unique worker ID |
| `capabilities` | Record<string, string> | `{}` | Worker capabilities |
| `maxConcurrentTasks` | number | 3 | Max concurrent tasks |
| `taskTimeoutSeconds` | number | 300 | Task timeout |
| `heartbeatIntervalSeconds` | number | 30 | Heartbeat interval |

## API Reference

### Worker

Main worker class for handling tasks from the control plane.

#### Methods

- `start()` - Start the worker
- `stop()` - Stop the worker
- `getStatus()` - Get current worker status
- `getWorkerId()` - Get worker ID
- `updateCapabilities()` - Update worker capabilities

#### Events

- `started` - Worker started
- `stopped` - Worker stopped
- `taskReceived` - Task received
- `taskCompleted` - Task completed
- `heartbeat` - Heartbeat response
- `error` - Error occurred

### createWorker()

Create a new Worker instance with custom configuration.

### startWorker()

Convenience function to create and start a worker with a task handler.

## Development

```bash
# Install dependencies
npm install

# Build
npm run build

# Run example
npx ts-node examples/basic.ts
```

## License

MIT