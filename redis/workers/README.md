# RideShield Telemetry Worker

This worker consumes telemetry batches from the Upstash Redis stream (`rideshield:telemetry`) and persists them to the PostgreSQL database.

## Running the Worker

To run the worker in production/long-polling mode, use:

```bash
python -m redis.workers.telemetry_worker
```

## Options

- `--run-once`: Run a single iteration of the consumer loop and exit (useful for tests or cron jobs).
- `--idle-threshold-ms`: Specify the idle threshold for reclaiming stale messages via XAUTOCLAIM (default is 30000ms).

Example:
```bash
python -m redis.workers.telemetry_worker --run-once --idle-threshold-ms 1000
```
