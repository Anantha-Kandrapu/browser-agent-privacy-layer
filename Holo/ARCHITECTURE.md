# PLVA architecture

```mermaid
flowchart TB
    subgraph Client["hai-agent-runtime (closed CUA runtime)"]
        SCR[Screenshot 1920x1243 JPEG]
    end

    SCR -->|POST base_url| PROXY

    subgraph PROXY["plva_proxy (loopback proxy, sole egress)"]
        HOOK_REQ[Request hook: rewrite body + inject upstream key]
        REDACT
        HOOK_RES[Response hook: buffer/reconstruct SSE, mutate JSON]
    end

    subgraph REDACT["Redaction engines (pick one via --redact-engine)"]
        direction TB
        ACCEL["accelerated (default)\nredactor-worker (Node)\n- Visual model: WebGPU (ONNX)\n- OCR: WASM runtime, parallel\n- Warm pool, 60s idle release\n- Bounded redacted-output cache"]
        VISION["vision\ncoreml-redactor (Python + Swift)\n- Visual: Core ML ANE session (fixed-shape ONNX->CoreML)\n- OCR: native Apple Vision (Swift worker) + RapidOCR Core ML fallback\n- Semantics: Core ML 'Rampart' classifier + rule engine\n- Fusion: hybrid.py merges visual+OCR+semantic findings"]
        BASELINE["baseline\nplva-v2-baseline (frozen oracle, dev-only, AGPL, not vaulted)"]
    end

    SCR --> HOOK_REQ --> REDACT --> HOOK_RES

    HOOK_RES -->|redacted request| PROVIDER

    subgraph PROVIDER["Upstream LLM provider (providers.py presets)"]
        OVERSHOOT["Overshoot\nmodel: Hcompany/Holo3-35B-A3B\nJSON + SSE contract"]
        HCOMPANY["H Company\nHAI_API_KEY, PLVA_PROVIDER=hcompany"]
    end

    PROVIDER -->|completion / SSE stream| HOOK_RES
    HOOK_RES -->|relayed response| Client

    REDACT -.->|memory-only| VIEWER["/viewer, /viewer/findings\n(no disk persistence)"]
```

## Model inventory

| Stage | Engine | Model / runtime |
|---|---|---|
| Visual PII detection (default) | `redactor-worker` | ONNX visual model on WebGPU |
| OCR (default) | `redactor-worker` | WASM OCR runtime, runs concurrently with visual |
| Visual PII detection (opt-in) | `coreml-redactor` | Fixed-shape ONNX→Core ML model on ANE (`visual_ane.py`) |
| OCR (opt-in) | `coreml-redactor` | Native Apple Vision (Swift, `vision_ocr_worker.swift`) + RapidOCR Core ML fallback |
| Semantic classification (opt-in engine only) | `coreml-redactor` | Rule engine + Core ML "Rampart" classifier (`semantics.py`) |
| Redaction oracle (dev-only) | `plva-v2-baseline` | Frozen v2 detector, gitignored, AGPL |
| Upstream completion | `plva_proxy/providers.py` | Overshoot: `Hcompany/Holo3-35B-A3B`; or H Company endpoint |

Not built yet: placeholder-ID substitution, vault, resolution, history scrubbing.
