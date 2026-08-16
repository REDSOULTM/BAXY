# 04.02 — Voice turn end-to-end

> Cuándo: el usuario dice "gemma, abre Spotify y poné Hades".
> **Fuente:** `voice/controller.py` + `voice_runner.py` + `agent.py:run_content` (~892 LOC).
> Asume: wake activo, modelos cargados, llama-server warmed up.
> **Threads tocados:** AudioCapture+pump, Wake, STT, TTS, AudioDucker COM, AgentRunner, NLI async, grounding async, experience write, log recorder sync, BUS publish.

## Fig 4.02 — Turn de voz completo

```mermaid
sequenceDiagram
    autonumber
    participant U as Usuario
    participant Mic as AudioCapture<br/>PortAudio callback + pump thread
    participant WD as WakeDetector (Vosk)
    participant VC as VoiceController
    participant Duck as _AudioDucker (COM thread)
    participant STT as StreamingSTT (Whisper+VAD)
    participant VR as VoiceRunner
    participant BUS as EventBus
    participant AR as AgentRunner
    participant AG as Gemma4Agent.run_content
    participant Plan as planner.plan_mission
    participant Sel as planner.select_tool_names
    participant SemR as semantic_router (lazy)
    participant Cap as capability_classifier (async)
    participant NLI as nli_service singleton
    participant MG as MissionGoal
    participant LLC as LLMClient
    participant LP as llama-server
    participant TR as ToolRegistry.execute
    participant V as verify_core.verify
    participant MO as compute_mission_outcome
    participant Guards as 6× _guard_*
    participant TTS as StreamingTTS (Piper)
    participant Exp as ExperienceMemory
    participant GG as grounding_gate (async)

    U->>Mic: speech (audio chunks 512 samples @ 16kHz)
    Mic->>VC: _on_audio_chunk(chunk)
    VC->>WD: feed(chunk)
    WD->>WD: Vosk reconoce "gemma", confidence >0.85
    WD->>VC: on_wake(phrase, ts, tail_s)
    VC->>BUS: pub state=WAKE_DETECTED
    VC->>Duck: duck() (encola intent)
    Duck->>Duck: COM thread baja volumen sistema a 15%
    VC->>VC: 200ms grace
    VC->>BUS: pub state=LISTENING
    VC->>STT: start_stt_thread()
    STT->>STT: prefix_audio (tail post-wake) + chunks
    STT->>VC: STTEvent(partial, "abre")
    STT->>VC: STTEvent(partial, "abre Spotify")
    STT->>VC: STTEvent(final, "abre Spotify y poné Hades")
    VC->>BUS: pub state=TRANSCRIBING
    VC->>VR: _handle_final("abre Spotify y poné Hades")
    VR->>BUS: activity YOU
    VR->>AR: submit(text)
    AR->>BUS: pub activity SYSTEM "turn enqueued"

    Note over AG: run_content empieza
    AR->>AG: run_text(text)
    AG->>AG: turn_counter += 1
    AG->>AG: mode = choose_mode(text)
    AG->>Plan: plan_mission(text) → MissionPlan
    AG->>AG: turn_id = trace.new_turn_id()

    AG->>AG: chequear phrase-triggers (early)
    Note over AG: si matchea routine on_phrase guardada,<br/>la ejecuta SIN LLM y guarda resultados

    AG->>AG: experience.recall (top-K turns similares)
    AG->>Exp: recall(text, embed_fn, k=3)
    Exp-->>AG: list[dict] con outcome+args_signature

    AG->>AG: explicit_plan (OPT-IN, default OFF)

    AG->>BUS: progress(start, mode, steps)
    AG->>AG: last_assistant_text (continuation hint)
    AG->>Sel: select_tool_names(text, plan, last_assistant=...)

    par paralelo: capability classifier
        AG->>Cap: classify_capability_async(text)
        Cap->>NLI: classify_async(text, CAPABILITY_LABELS, callback)
        NLI->>NLI: BG thread carga mDeBERTa si no está (~14s primera vez)
    end

    alt subset vacío + word_count>3 + no casual
        Sel->>SemR: suggest_tools_semantic(text, k=12)
        SemR->>SemR: encode + topK cosine
    end
    Sel-->>AG: ["app", "media", "session", ...] capped MAX=16

    AG->>MG: MissionGoal.from_user_text(text)
    Note over MG: extrae ExpectedOutcome[open_target=Spotify, open_target=Hades]

    AG->>AG: _system_message(mode, plan, subset, text)
    Note over AG: prompt = CORE + tool_schemas_hint(subset)<br/>+ persona + microagents + skills critical+menu<br/>+ recall + project_context + intent_hint

    AG->>AG: turn loop empieza
    loop hasta max_agent_turns o reply natural
        AG->>LLC: chat(messages, tools=schemas, parallel?)
        LLC->>LP: POST /v1/chat/completions
        LP-->>LLC: response con tool_calls O text
        alt tool_calls
            opt parallel
                AG->>TR: execute_calls_parallel
            else sequential
                AG->>TR: execute_calls_sequential
            end
            loop por cada tool_call
                AG->>TR: execute(name, args)
                TR->>TR: strip _internal_safe<br/>+ coerce_and_validate<br/>+ _PRE_VALIDATORS[name]<br/>+ classify_tool_call (safety)<br/>+ maybe create_confirmation
                TR->>TR: impl(args)
                TR-->>AG: ToolResult normalizado
                AG->>V: verify(name, args, result) → VerifierOutcome
                AG->>MG: update_with_tool(name, args, ok)
                AG->>BUS: progress(tool_end, name, ok, status)
            end
            AG->>AG: append tool messages to history
            opt context budget exceeded
                AG->>AG: _compact_active_history_for_retry()
            end
        else assistant text
            Note over AG: aplicar 6 guards
            AG->>Guards: _guard_promise_without_action
            AG->>Guards: _guard_grounded_action_claim
            AG->>Guards: _guard_phrase_confirm
            AG->>Guards: _guard_unverified_final
            AG->>Guards: _guard_plan_status
            AG->>MO: compute_mission_outcome(MG, tool_records, reply)
            Note over MO: MissionOutcome.status ∈ {COMPLETED, PARTIAL, FAILED, UNVERIFIED, NEEDS_USER, ...}
            AG->>AG: append summarize_verifiers footer
        end
    end

    par async post-reply
        AG->>GG: schedule_grounding_check(reply, tool_events, turn_id)
        GG->>NLI: classify_async (background, ~1200ms)
        GG-->>Exp: flag_grounding_by_turn(turn_id) si NLI dice hallucinated
    and
        opt _fact_extraction_enabled
            AG->>LLC: chat para extraer facts (LLM extra)
            LLC-->>AG: facts JSON
            AG->>AG: memory.save(...)
        end
    and
        opt _summarization_enabled
            AG->>LLC: chat para summarizar history block (LLM extra)
            LLC-->>AG: summary
            AG->>AG: replace history block
        end
    and
        AG->>Exp: record(turn_id, user_input, tools, outcome, embed_fn)
        Exp->>Exp: INSERT experiences + experience_vec
    end

    AG->>BUS: progress(final)
    AG-->>AR: AgentReply(content, tool_events, mission)
    AR->>BUS: pub activity GEMMA reply
    AR->>VR: reply via BUS

    VR->>VC: begin_tts() + feed_tts_chunk(reply) + end_tts()
    VC->>BUS: pub state=SPEAKING
    VC->>TTS: feed_text(reply chunks)
    TTS->>TTS: regex split sentences → Piper → sounddevice
    TTS->>U: audio

    VC->>BUS: pub state=FOLLOWUP (5s window)
    Duck->>Duck: restore() encola intent
    Duck->>Duck: COM thread restaura volumen original

    alt user habla en window
        Mic->>VC: nuevo chunk → STT → loop
    else timeout o close phrase
        VC->>BUS: pub state=IDLE_LISTENING
    end
```

## Threads simultáneos en el peor momento

| Thread | Quién lo creó | Vida |
|---|---|---|
| Main (Qt o uvicorn) | Process | Process |
| AgentRunner._run worker | `AgentRunner.start()` | Process (daemon) |
| AudioCapture._pump_loop | `AudioCapture.start()` | Mientras voice activo |
| PortAudio callback (interno) | sounddevice | Mientras voice activo |
| WakeDetector (síncrono, en pump thread) | — | — |
| StreamingSTT _stt_thread | `VoiceController._start_stt_thread` | Por utterance |
| StreamingTTS _run_worker | `StreamingTTS.start()` | Mientras voice activo |
| _AudioDucker COM worker | lazy on first duck() | Process (daemon) |
| LlamaLogTail (boot only) | `_autostart_llama_server` | Hasta STAGE_LISTENING |
| Semantic router warmup BG | `_bg_warmup_router` | One-shot ~6-8s |
| NLI worker | `nli_service._workers` | Per request (daemon) |
| Grounding async worker | `schedule_grounding_check` | Per turn post-reply (daemon) |
| Health polling | `agent_thread._health_loop` (PyQt only) | Process (daemon) |
| ProfileWatcher daemon | opt-in `_run` | Si está enabled |
| Log recorder (sync inline, no thread propio) | — | — |
| Telemetry (sync inline, no thread propio) | — | — |

**Hasta 13 threads activos** durante un voice turn en producción.

## Hallazgos a `_findings_seed.md`

- **`run_content` corre potencialmente 3 LLM calls** (turn principal + extract_facts + summarize_history) — ya en findings (HIGH). Reafirmar.
- **6 guards inline + grounding async + capability async** = 8 mecanismos de validación corriendo simultáneo. Ya cubierto.
- **`_phrase_fires` check ANTES del LLM** — si una phrase-trigger routine ejecuta tools sin LLM, el LLM solo confirma. Patrón interesante. Verificar Fase 7 si las routines on_phrase guardadas se usan en la práctica.
- **`_AudioDucker` con COM thread propio + queue + lazy init** — 215 LOC para "bajar y subir el volumen al hablar con gemma". Funcional, pero overhead. Si pycaw no está disponible, no-op (gracefully).
