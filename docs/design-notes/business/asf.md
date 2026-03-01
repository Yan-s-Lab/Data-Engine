# Business Design: ASF

## 1. Scope

ASF (Annotation Similarity Filter) detects annotation-semantic mismatch and suspicious label distributions.

## 2. Responsibilities

- compute annotation consistency metrics
- identify label-density/class-count anomalies
- emit policy-driven filtering decisions with evidence

## 3. Contracts

Inputs:
- to be defined

Outputs:
- to be defined

## 4. Invariants

- ASF policy is independently versioned from pipeline code
- decision evidence is retained for audit and HITL review

## 5. Open Questions

- robust thresholds across domains and class imbalance
- interaction rule with PCS in joint filtering
