# route-planner

Builds multi-stop routes for the TMS, prices each leg through carrier rate APIs, and estimates the ETA at each stop.

## Layout
- `RoutePlanner`: entry point; enforces the plan deadline and returns partial results with an error code when it runs out of time.
- `CarrierClient`: rate API calls, wrapped in `RetryPolicy`.
- `RetryPolicy`: exponential backoff with full jitter (decision 2026-08-14).
- `EtaEstimator`: transit time plus stop and rest-stop time.
- `ErrorCode`: codes returned to the TMS.

## Configuration (`config/application.yaml`)
| Key | Default | Meaning |
| --- | --- | --- |
| `route.plan-deadline-ms` | 4000 | Whole-request deadline |
| `route.retry.max-attempts` | 3 | Attempts per carrier call, including the first |
| `route.retry.base-delay-ms` | 200 | Backoff base |
| `route.retry.max-delay-ms` | 2000 | Backoff cap |
| `carrier.timeout-ms` | 1500 | Per-call timeout; must stay well under the plan deadline |
| `route.eta.model-v2` | false | Rest stops in ETA |

## Build
`mvn test`
