---
title: "Runbook: upstream connect error"
created: 2025-11-02
type: runbook
tags: [platform, runbook, networking, mesh]
---
# Runbook: upstream connect error

Error returned to callers: `upstream connect error or disconnect/reset before headers. reset reason: connection failure`.

Meaning: the mesh sidecar could not open a connection to the target service, or the target reset it before replying. Usually the target has no ready pods.

## Check
1. `kubectl get pods -n <namespace> -l app=<service>`: are the pods Ready? CrashLoopBackOff points at the service, not the network.
2. Readiness probe failing after a deploy? Check the probe path and its timeout.
3. Only one caller affected? Check that caller's egress policy.

## Act
- No ready pods: roll back the last deploy.
- Pods ready but resets continue: restart the sidecars by rolling the deployment.
- Node pressure (evictions in the events): cordon the node and page platform.
