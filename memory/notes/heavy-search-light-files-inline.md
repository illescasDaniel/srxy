---
name: heavy-search-light-files-inline
description: (1) Classify paths with ocr_candidate_path / transcribe_candidate_path (TextExtractorPort) plus existing is_image_path. (2) When _use_threads, score light…
type: decision
date: 2026-08-30
status: current
supersedes: 
superseded_by: 
source:
---
- **Context:** With OCR (or transcribe/CLIP) on, every discovered file — including plain `.txt` — went into the same `ThreadPoolExecutor`. FIFO queueing meant text scoring sat behind in-flight OCR workers, so progress looked frozen on the image being OCRed even though fast files were waiting.
- **Decision:** (1) Classify paths with `ocr_candidate_path` / `transcribe_candidate_path` (TextExtractorPort) plus existing `is_image_path`. (2) When `_use_threads`, score light files synchronously on the walking thread; submit only heavy candidates to the pool. (3) Non-blocking drain of completed heavy futures between light files; blocking drain at `pending_limit` and after listing. Documents stay inline even with OCR (embedded text is usually cheap; scanned-page OCR is a known follow-up).
- **Rationale:** Keeps streaming results/progress for text while heavy media runs in parallel; avoids GIL thrashing from putting pure-text matching on the same thread pool as OCR.
