# Kernel Design: DataSpider

## 1. Scope

DataSpider discovers and gathers candidate data assets from configured sources.

## 2. Responsibilities

- discover candidates from local/remote sources
- standardize crawl outputs into ingest-ready artifacts
- preserve source references for provenance handoff

## 3. Contracts

Inputs:
- to be defined

Outputs:
- to be defined

## 4. Invariants

- discovery metadata must be reproducible from config + run record
- DataSpider does not assign final sample identity (DataLoader does)

## 5. Open Questions

- scheduler policy for periodic crawling
- dedup strategy before ingestion
