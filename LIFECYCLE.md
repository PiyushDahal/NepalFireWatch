# Nepal FireWatch event lifecycle

Lifecycle is separate from the evidence/confidence classification.

| State | Default rule |
|---|---|
| `NEW` | Recent event with limited independent repeat evidence |
| `ACTIVE` | Recent event with at least 2 independent overpasses, or at least 1 hour observed duration |
| `PERSISTENT` | Recent event with at least 3 independent overpasses, or at least 12 hours observed duration |
| `QUIET` | No new VIIRS detection for at least 8 hours |
| `CLOSED` | No new VIIRS detection for at least 24 hours |

`QUIET` and `CLOSED` mean no new satellite detection was observed during the
configured interval. They do not prove that a fire is extinguished on the ground.

Optional environment variables:

- `NFW_LIFECYCLE_QUIET_HOURS`
- `NFW_LIFECYCLE_CLOSED_HOURS`
- `NFW_LIFECYCLE_ACTIVE_OVERPASSES`
- `NFW_LIFECYCLE_PERSISTENT_OVERPASSES`
- `NFW_LIFECYCLE_ACTIVE_DURATION_HOURS`
- `NFW_LIFECYCLE_PERSISTENT_DURATION_HOURS`
