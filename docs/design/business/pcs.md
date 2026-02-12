# Business Design: PCS

## 1. Scope

PCS (Perturbation CLIP Similarity) evaluates sample quality/stability under controlled perturbations.

## 2. Responsibilities

- define perturbation set and embedding comparison logic
- produce accept/reject/uncertain decisions with scores
- expose policy parameters for feedback-driven updates

## 3. Contracts

Inputs:
- to be defined

Outputs:
- to be defined

## 4. Invariants

- decisions are versioned by policy and perturbation setup
- PCS runs through DataFilter Bridge contracts only

## 5. Open Questions

- perturbation family selection by failure slice
- score calibration against real validation performance
