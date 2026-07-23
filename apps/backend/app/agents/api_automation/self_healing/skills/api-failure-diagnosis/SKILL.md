---
name: api-failure-diagnosis
description: Diagnose pytest requests failures using runtime evidence and explicit contracts.
---

# API Failure Diagnosis

- Inspect the actual pytest report, request, response, assertion, and traceback before inferring.
- Group failures that share one root cause.
- Distinguish test code, test data, environment, interface defect, contract ambiguity, and unknown.
- State confidence and evidence for every issue.
- Never recommend weakening or deleting tests merely to make the suite pass.
