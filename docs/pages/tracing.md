# Tracing & OpenTelemetry

BorgBoi has built-in [OpenTelemetry](https://opentelemetry.io/) support for distributed tracing and log export. When enabled, every CLI command and TUI session is wrapped in an OTLP span, letting you correlate backup operations with your existing observability stack (Tempo, Jaeger, Grafana, etc.).

Telemetry is **opt-in** and **fail-safe** — any exporter or instrumentation failure degrades gracefully to a no-op session rather than aborting the backup.

## Quick Start

1. Point BorgBoi at your OTLP collector and enable tracing in `~/.borgboi/config.yaml`:

    ```yaml
    telemetry:
      enabled: true
      trace_endpoint: http://localhost:4318/v1/traces
    ```

2. Run any command:

    ```sh
    bb backup run my-repo
    ```

3. At the end of each command, BorgBoi prints a trace ID so you can look it up immediately:

    ```
    Trace ID: 4bf92f3577b34da6a3ce929d0e0e4736
    Traces sent to http://localhost:4318/v1/traces
    ```

## Configuration

All telemetry settings live under the `telemetry` key in `~/.borgboi/config.yaml`.

```yaml
telemetry:
  enabled: false             # set to true to enable
  service_name: borgboi      # OTel service.name resource attribute
  trace_endpoint: null       # OTLP/HTTP traces endpoint override
  export_logs: false         # also ship log records over OTLP
  logs_endpoint: null        # separate OTLP endpoint for logs (e.g. Loki)
  capture_tui: true          # trace TUI sessions when telemetry is enabled
```

### Configuration Fields

| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `telemetry.enabled` | boolean | `false` | Enables OpenTelemetry tracing for all CLI commands and TUI sessions. |
| `telemetry.service_name` | string | `borgboi` | The `service.name` resource attribute. Overridden at runtime by `OTEL_SERVICE_NAME`. |
| `telemetry.trace_endpoint` | string or `null` | `null` | OTLP/HTTP endpoint for span export. Falls back to standard OTEL env vars when `null`. |
| `telemetry.export_logs` | boolean | `false` | Enables a second OTLP pipeline that ships JSON log records alongside traces. |
| `telemetry.logs_endpoint` | string or `null` | `null` | Dedicated OTLP/HTTP endpoint for log export. Useful when traces go to Tempo but logs go to Loki. |
| `telemetry.capture_tui` | boolean | `true` | When `true`, the TUI session and its background data-loading workers are traced under a `tui.session` root span. |

### Environment Variable Overrides

All `telemetry.*` fields can be overridden at runtime with `BORGBOI_TELEMETRY__*` variables:

| Environment Variable | Config Field |
| --- | --- |
| `BORGBOI_TELEMETRY__ENABLED` | `telemetry.enabled` |
| `BORGBOI_TELEMETRY__SERVICE_NAME` | `telemetry.service_name` |
| `BORGBOI_TELEMETRY__TRACE_ENDPOINT` | `telemetry.trace_endpoint` |
| `BORGBOI_TELEMETRY__EXPORT_LOGS` | `telemetry.export_logs` |
| `BORGBOI_TELEMETRY__LOGS_ENDPOINT` | `telemetry.logs_endpoint` |
| `BORGBOI_TELEMETRY__CAPTURE_TUI` | `telemetry.capture_tui` |

BorgBoi also respects the standard OpenTelemetry SDK environment variables for endpoint resolution:

| Variable | Purpose |
| --- | --- |
| `OTEL_SERVICE_NAME` | Overrides `telemetry.service_name` |
| `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` | Fallback trace endpoint when `telemetry.trace_endpoint` is not set |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Generic OTLP base URL; used when neither the config nor the traces-specific env var is set |

Endpoint resolution priority for traces:

```
telemetry.trace_endpoint (config/env)
    ↓
OTEL_EXPORTER_OTLP_TRACES_ENDPOINT
    ↓
OTEL_EXPORTER_OTLP_ENDPOINT
    ↓
SDK default (http://localhost:4318)
```

## Resource Attributes

Every span is stamped with a set of resource attributes that identify the process:

| Attribute | Value |
| --- | --- |
| `service.name` | `telemetry.service_name` (or `OTEL_SERVICE_NAME`) |
| `service.version` | Installed `borgboi` package version |
| `service.instance.id` | Hostname of the machine running borgboi |
| `borgboi.mode.offline` | `true` when running in offline mode |

## Span Inventory

### CLI Spans

Each CLI invocation creates a root span named `cli.<command-name>` (e.g. `cli.daily-backup`, `cli.list-repos`). The following span attributes are set on every CLI root span:

| Attribute | Description |
| --- | --- |
| `borgboi.command.name` | The Python function name of the invoked command |
| `borgboi.command.tokens` | Sanitized CLI tokens (sensitive values are redacted) |
| `borgboi.mode.offline` | Whether offline mode was active |
| `borgboi.mode.debug` | Whether debug mode was active |

### Orchestrator Spans

The orchestrator creates child spans for every major operation. Common span attributes include `borgboi.repo.name`, `borgboi.repo.path`, and operation-specific fields:

| Span Name | Key Attributes |
| --- | --- |
| `orchestrator.create_repo` | `borgboi.repo.name`, `borgboi.repo.path`, `borgboi.repo.backup_target` |
| `orchestrator.import_repo` | `borgboi.repo.name`, `borgboi.repo.path` |
| `orchestrator.get_repo` | `borgboi.repo.name`, `borgboi.repo.path`, `borgboi.repo.hostname` |
| `orchestrator.list_repos` | `borgboi.repo.count`, `borgboi.storage.backend` |
| `orchestrator.backup` | `borgboi.repo.name`, `borgboi.archive.name`, `borgboi.repo.backup_target` |
| `orchestrator.daily_backup` | `borgboi.repo.name`, `borgboi.sync.to_s3` |
| `orchestrator.delete_repo` | `borgboi.repo.name`, `borgboi.delete.dry_run` |
| `orchestrator.get_repo_info` | `borgboi.repo.name`, `borgboi.repo.path` |

### Borg Client Spans

Every Borg subprocess call is wrapped in a `SpanKind.CLIENT` span:

| Span Name | Key Attributes |
| --- | --- |
| `borg.command` | `borgboi.borg.subcommand`, `process.command.name`, `process.exit_code` |
| `borg.command.stream` | `borgboi.borg.subcommand`, `borgboi.stream_output` |

### TUI Spans

When `telemetry.capture_tui` is `true`, the TUI session is wrapped in a `tui.session` root span. Individual screen operations are traced using the `@capture_span` decorator:

| Span Name | Description |
| --- | --- |
| `tui.session` | The full interactive TUI session |
| `tui.app.mount` | Initial widget mount and column setup |
| `tui.load_repos` | Background repo list load for the home screen table |
| `tui.load_sparkline` | Background archive activity data load |

### AWS Auto-Instrumentation

BorgBoi automatically instruments `botocore` via `opentelemetry-instrumentation-botocore`. All S3 and DynamoDB calls made during a CLI command or TUI session appear as child spans under the enclosing orchestrator span, with no extra configuration required.

## Log Export

When `export_logs: true`, BorgBoi adds a second OTLP pipeline that ships structured JSON log records to your observability backend. Each log record carries the active `trace_id` and `span_id`, so logs and traces are automatically correlated in tools like Grafana.

```yaml
telemetry:
  enabled: true
  trace_endpoint: http://tempo:4318/v1/traces
  export_logs: true
  logs_endpoint: http://loki:3100/otlp/v1/logs
```

If `logs_endpoint` is not set, log records are sent using the same endpoint resolution chain as traces.

!!! tip "Log correlation"
    Even without `export_logs`, BorgBoi binds `trace_id`, `span_id`, and `trace_flags` into every structured log entry when a span is active. This means local log files written via `logging.enabled: true` already contain trace context for manual correlation.

## Exit Summary

After every command, BorgBoi prints a short exit summary to stdout. When telemetry is enabled, the summary includes the trace ID and whether spans were flushed successfully:

```
Trace ID: 4bf92f3577b34da6a3ce929d0e0e4736
Traces sent to http://localhost:4318/v1/traces
```

If the flush to the OTLP collector timed out, the message changes to:

```
Traces queued for http://localhost:4318/v1/traces
```

This indicates spans are still in the in-process batch queue and may not have been delivered.

## Failure Behavior

BorgBoi is designed so that telemetry failures never break backups:

- If the trace provider cannot be initialized, BorgBoi prints a warning to stderr and continues with telemetry disabled for that run.
- If `botocore` instrumentation fails, BorgBoi warns and continues — AWS spans will simply be absent.
- If the log exporter cannot be initialized, log export is skipped for the run but traces are unaffected.
- Flush timeouts at exit print a warning but do not cause a non-zero exit code.

## Example: Grafana + Tempo

A minimal `docker-compose.yml` for local development with Tempo as the OTLP backend:

```yaml
services:
  tempo:
    image: grafana/tempo:latest
    command: ["-config.file=/etc/tempo.yaml"]
    volumes:
      - ./tempo.yaml:/etc/tempo.yaml
    ports:
      - "4318:4318"   # OTLP/HTTP
      - "3200:3200"   # Tempo query API

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_AUTH_ANONYMOUS_ENABLED=true
      - GF_AUTH_ANONYMOUS_ORG_ROLE=Admin
```

Then enable tracing in `~/.borgboi/config.yaml`:

```yaml
telemetry:
  enabled: true
  trace_endpoint: http://localhost:4318/v1/traces
```

Run a daily backup and search for `service.name = "borgboi"` in the Grafana Explore view to see the full trace.
