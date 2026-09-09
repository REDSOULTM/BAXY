"""Diagnostic-only copy of capture242, separating speech confirmation and ASR audio."""
def _capture_loop(
    self,
    session_epoch: int | None = None,
    stop_event: threading.Event | None = None,
    decode_queue: queue.Queue[object] | None = None,
    streaming_queue: queue.Queue[object] | None = None,
    wake_queue: queue.Queue[object] | None = None,
    wake_hits: queue.Queue[tuple[int, WakeWordDetection]] | None = None,
    capture_ready_event: threading.Event | None = None,
) -> None:
    event = stop_event or self._stop_event
    decode_owner = decode_queue or self._decode_queue
    streaming_owner = streaming_queue or self._streaming_queue
    wake_owner = wake_queue or self._acoustic_wake_queue
    hit_owner = wake_hits or self._acoustic_wake_hits
    ready_event = capture_ready_event or self._capture_ready_event
    vad = self._vad
    confirmation_vad = self._confirmation_vad
    utterance: list[np.ndarray] = []
    canceller: EchoCanceller | None = None
    reference_cursor: int | None = None
    vad_pre_roll: deque[np.ndarray] = deque(
        maxlen=_wake_frame_count(PRE_ROLL_S)
    )
    acoustic_pre_roll_seconds = (
        self._wake_verifier.config.stage1_pre_roll_seconds
        if self._wake_verifier is not None
        else _ACOUSTIC_WAKE_PRE_ROLL_S
    )
    acoustic_pre_roll: deque[np.ndarray] = deque(
        maxlen=_wake_frame_count(acoustic_pre_roll_seconds)
    )
    acoustic_activity: deque[float] = deque(maxlen=acoustic_pre_roll.maxlen)
    silence_frames = 0
    speech_started = False
    speech_started_at = 0.0
    barge_frames = 0
    barge_pending = False
    noise_floor = 0.002
    live_stream_id: int | None = None
    active_origin = "direct"
    active_wake_confidence: float | None = None
    active_wake_verification_start_sample = 0
    active_wake_detection: WakeWordDetection | None = None
    endpoint_wake_enabled = self._endpoint_wake_available()
    frames_per_silence = _wake_frame_count(TRAILING_SILENCE_S)
    max_frames = max(1, int(MAX_UTTERANCE_S * SAMPLE_RATE / VAD_WINDOW_SAMPLES))

    def wake_state() -> tuple[str, bool, str]:
        now = time.monotonic()
        with self._lock:
            if self._armed_until and self._armed_until < now:
                self._armed_until = 0.0
            return self._mode, self._armed_until >= now, self._wake_backend

    def admit_utterance(cached_audio: tuple[np.ndarray, ...]) -> None:
        nonlocal live_stream_id
        self._ducker.duck()
        self._streaming_session += 1
        candidate_stream_id = self._streaming_session
        if self._enqueue_streaming(
            ("start", candidate_stream_id, cached_audio, speech_started_at),
            streaming_queue=streaming_owner,
            session_epoch=session_epoch,
            stop_event=event,
        ):
            live_stream_id = candidate_stream_id
        else:
            live_stream_id = None

    def begin_utterance(
        origin: str,
        cached: tuple[np.ndarray, ...],
        wake_detection: WakeWordDetection | None = None,
        wake_verification_start_sample: int = 0,
        *,
        authorized: bool = True,
        barge_candidate: bool = False,
        retain_acoustic_history: bool = False,
    ) -> None:
        nonlocal speech_started, speech_started_at, silence_frames
        nonlocal live_stream_id, active_origin, active_wake_confidence
        nonlocal active_wake_verification_start_sample
        nonlocal active_wake_detection
        nonlocal barge_pending
        if speech_started:
            return
        barge_pending = barge_candidate
        speech_started = True
        active_origin = origin
        active_wake_confidence = (
            wake_detection.confidence if wake_detection is not None else None
        )
        active_wake_verification_start_sample = wake_verification_start_sample
        silence_frames = 0
        speech_started_at = time.monotonic()
        cached_audio = cached
        active_wake_detection = wake_detection
        if authorized:
            admit_utterance(cached_audio)
        else:
            live_stream_id = None
        utterance.extend(cached)
        vad_pre_roll.clear()
        if not retain_acoustic_history:
            acoustic_pre_roll.clear()
            acoustic_activity.clear()

    def authorize_provisional_wake(
        wake_detection: WakeWordDetection,
        wake_verification_start_sample: int,
    ) -> bool:
        nonlocal live_stream_id, active_origin, active_wake_confidence
        nonlocal active_wake_verification_start_sample
        nonlocal active_wake_detection
        if not speech_started or active_origin != "endpoint_wake_candidate":
            return False
        active_origin = "acoustic_wake"
        active_wake_confidence = wake_detection.confidence
        active_wake_verification_start_sample = wake_verification_start_sample
        active_wake_detection = wake_detection
        admit_utterance(tuple(utterance))
        acoustic_pre_roll.clear()
        acoustic_activity.clear()
        return True

    def finish_utterance() -> None:
        nonlocal utterance, silence_frames, speech_started
        nonlocal speech_started_at, barge_frames, live_stream_id, active_origin
        nonlocal active_wake_confidence
        nonlocal active_wake_verification_start_sample
        nonlocal active_wake_detection
        nonlocal barge_pending
        audio = np.concatenate(utterance) if utterance else np.empty(0, np.float32)
        unconfirmed_barge = barge_pending
        origin = active_origin
        wake_confidence = active_wake_confidence
        wake_verification_start_sample = active_wake_verification_start_sample
        wake_detection = active_wake_detection
        utterance = []
        vad_pre_roll.clear()
        acoustic_pre_roll.clear()
        silence_frames = 0
        speech_started = False
        speech_started_at = 0.0
        barge_frames = 0
        barge_pending = False
        active_origin = "direct"
        active_wake_confidence = None
        active_wake_verification_start_sample = 0
        active_wake_detection = None
        if live_stream_id is not None:
            self._enqueue_streaming(
                ("finish", live_stream_id),
                streaming_queue=streaming_owner,
                session_epoch=session_epoch,
                stop_event=event,
            )
        live_stream_id = None
        vad.reset()
        confirmation_vad.reset()
        if origin in {"acoustic_wake", "endpoint_wake_candidate"}:
            self._reset_acoustic_wake(session_epoch=session_epoch)
        if unconfirmed_barge or audio.size < MIN_UTTERANCE_S * SAMPLE_RATE:
            self._ducker.restore()
            return
        try:
            if event.is_set() or not self._session_is_current(session_epoch):
                self._ducker.restore()
                return
            decode_owner.put_nowait(
                _DecodeRequest(
                    audio,
                    canceller is not None,
                    origin,
                    session_epoch,
                    wake_confidence,
                    wake_verification_start_sample,
                    wake_detection.method if wake_detection is not None else None,
                    (
                        wake_detection.verifier_score
                        if wake_detection is not None
                        else None
                    ),
                    bool(
                        wake_detection is not None
                        and wake_detection.lexical_rescue_required
                    ),
                )
            )
        except queue.Full:
            self.last_error = "decode_queue_full"
            self._emit("error", code=self.last_error)
            self._ducker.restore()

    try:
        import sounddevice as sd

        if vad is None:
            raise RuntimeError("voice_vad_unavailable")
        inbox = self._pcm_inbox
        if (
            inbox is None and self._loopback.active
            and resolve_echo_canceller_directory() is not None
        ):
            canceller = EchoCanceller()
            if self._session_is_current(session_epoch):
                self._aec_active = True
                self._aec_sha256 = canceller.sha256
        stream_context = (
            _PcmCaptureStream(inbox, event)
            if inbox is not None
            else WasapiCaptureStream(event)
        )
        with stream_context as stream:
            try:
                if inbox is not None:
                    self._input_device_name = "pcm-source"
                else:
                    device = sd.query_devices(stream.device, kind="input")
                    self._input_device_name = str(device["name"])[:120]
            except Exception:  # noqa: BLE001
                self._input_device_name = (
                    "pcm-source" if inbox is not None else "predeterminado"
                )
            if event.is_set() or not self._session_is_current(session_epoch):
                return
            with self._lock:
                if (
                    session_epoch is not None
                    and self._session_epoch == session_epoch
                    and not event.is_set()
                ):
                    self._lifecycle_state = "ready"
            self._emit("ready", **self.status())
            self._emit(
                "state",
                mode=self.mode,
                listening=True,
                speaking=self.speaking,
            )
            ready_event.set()
            while not event.is_set() and self._session_is_current(session_epoch):
                frame, overflowed = stream.read(VAD_WINDOW_SAMPLES)
                if event.is_set():
                    break
                if overflowed:
                    raise RuntimeError("input_overflow")
                mono = frame.reshape(-1).astype(np.float32)
                if canceller is not None:
                    if reference_cursor is None:
                        reference_cursor = self._loopback.sample_index(
                            stream.adc_time, event
                        )
                    reference_cursor += VAD_WINDOW_SAMPLES
                    history = self._loopback.window_at(
                        reference_cursor, REFERENCE_SAMPLES, event
                    )
                    mono, echo_microphone, echo_reference = canceller.process(
                        mono, history
                    )
                else:
                    history = (
                        self._loopback.latest(REFERENCE_SAMPLES)
                        if inbox is None else np.zeros(REFERENCE_SAMPLES, np.int16)
                    )
                    echo_microphone, echo_reference = mono * 32768.0, history
                probability = vad.process(mono)
                confirmation_probability = confirmation_vad.process(self._confirmation_frame())
                energy = _rms(self._confirmation_frame())
                if confirmation_probability < SPEECH_THRESHOLD:
                    noise_floor = 0.98 * noise_floor + 0.02 * energy
                confirmed = confirmation_probability >= SPEECH_THRESHOLD
                speech = probability >= SPEECH_THRESHOLD or confirmed
                if speech and self.speaking:
                    echo = _looks_like_echo(echo_microphone, echo_reference)
                    if echo:
                        speech = False
                        confirmed = False
                        barge_frames = 0
                    elif confirmed and energy >= max(0.004, noise_floor * 1.8):
                        barge_frames += 1
                        if barge_frames == 3:
                            self.cancel_speech()
                            self._emit("barge_in")
                    else:
                        barge_frames = 0
                else:
                    barge_frames = 0
                admitted = barge_frames >= 3 if self.speaking else confirmed
                if barge_pending and speech and admitted:
                    barge_pending = False
                    admit_utterance(tuple(utterance))

                mode, armed, backend = wake_state()
                acoustic_monitoring = (
                    mode == "wake"
                    and backend == "acoustic"
                    and not armed
                    and (
                        not speech_started
                        or active_origin == "endpoint_wake_candidate"
                    )
                )
                frame_already_captured = False
                if acoustic_monitoring:
                    # Never let BAXY's own speaker output become a wake
                    # sample. Barge-in is handled by VAD above; KWS resumes
                    # after output actually stops.
                    if self.speaking:
                        acoustic_pre_roll.clear()
                        acoustic_activity.clear()
                        self._reset_acoustic_wake(session_epoch=session_epoch)
                    else:
                        acoustic_pre_roll.append(mono)
                        acoustic_activity.append(probability)
                        self._enqueue_acoustic_wake(
                            mono,
                            wake_queue=wake_owner,
                            session_epoch=session_epoch,
                            stop_event=event,
                        )
                        hit = self._take_acoustic_wake_hit(
                            hit_queue=hit_owner,
                            session_epoch=session_epoch,
                        )
                        if hit is not None:
                            verifier_config = (
                                self._wake_verifier.config
                                if self._wake_verifier is not None
                                else None
                            )
                            verification_start = (
                                _wake_activity_onset_sample(
                                    acoustic_activity,
                                    threshold=(
                                        verifier_config.activity_vad_threshold
                                    ),
                                    alignment_samples=(
                                        verifier_config.activity_alignment_samples
                                    ),
                                    default_start_sample=(
                                        verifier_config.primary_view_start_samples
                                    ),
                                )
                                if verifier_config is not None
                                else 0
                            )
                            upgraded = authorize_provisional_wake(
                                hit,
                                verification_start,
                            )
                            if not upgraded:
                                begin_utterance(
                                    "acoustic_wake",
                                    tuple(acoustic_pre_roll),
                                    hit,
                                    verification_start,
                                )
                                frame_already_captured = True
                            self._reset_acoustic_wake(session_epoch=session_epoch)
                            self._emit(
                                "wake_proposed"
                                if (
                                    self._wake_verifier is not None
                                    or hit.lexical_rescue_required
                                )
                                else "wake_detected",
                                backend="acoustic",
                                model=hit.model_name,
                                confidence=round(hit.confidence, 3),
                            )
                elif not speech_started and not speech:
                    vad_pre_roll.append(mono)

                can_segment = (
                    mode == "direct"
                    or mode == "wake"
                    and (armed or backend == "lexical_fallback")
                    or mode == "wake"
                    and backend == "acoustic"
                    and not armed
                    and endpoint_wake_enabled
                    or speech_started
                )
                if speech and can_segment:
                    if not speech_started:
                        origin = (
                            "direct"
                            if mode == "direct"
                            else "acoustic_wake"
                            if armed
                            else "lexical_fallback"
                            if backend == "lexical_fallback"
                            else "endpoint_wake_candidate"
                        )
                        if origin == "endpoint_wake_candidate":
                            cached = tuple(acoustic_pre_roll)[
                                -vad_pre_roll.maxlen :
                            ]
                            begin_utterance(
                                origin,
                                cached,
                                authorized=False,
                                retain_acoustic_history=True,
                            )
                            frame_already_captured = bool(cached)
                        else:
                            # Keep the full onset in the existing utterance
                            # buffer; publish only after interruption is valid.
                            pending = not admitted
                            begin_utterance(
                                origin, tuple(vad_pre_roll),
                                authorized=not pending, barge_candidate=pending,
                            )
                    silence_frames = 0
                    if not frame_already_captured:
                        utterance.append(mono)
                        if (
                            live_stream_id is not None
                            and not self._enqueue_streaming(
                                ("audio", live_stream_id, mono),
                                streaming_queue=streaming_owner,
                                session_epoch=session_epoch,
                                stop_event=event,
                            )
                        ):
                            live_stream_id = None
                elif speech_started:
                    if not frame_already_captured:
                        utterance.append(mono)
                        if (
                            live_stream_id is not None
                            and not self._enqueue_streaming(
                                ("audio", live_stream_id, mono),
                                streaming_queue=streaming_owner,
                                session_epoch=session_epoch,
                                stop_event=event,
                            )
                        ):
                            live_stream_id = None
                    silence_frames += 1
                    if silence_frames >= frames_per_silence:
                        finish_utterance()
                if len(utterance) >= max_frames:
                    finish_utterance()
    except Exception as error:  # noqa: BLE001 - voz nunca tumba la mente
        cancelled = isinstance(error, InterruptedError) and event.is_set()
        if not cancelled and self._session_is_current(session_epoch):
            error_code = f"capture_failed:{type(error).__name__}"
            self._fail_capture_session(
                error_code,
                self._session_epoch if session_epoch is None else session_epoch,
            )
            logger.error("captura de voz interrumpida: %s", type(error).__name__)
    finally:
        try:
            if canceller is not None:
                canceller.close()
        finally:
            if self._session_is_current(session_epoch):
                self._aec_active = False
            if speech_started:
                finish_utterance()
            if self._session_is_current(session_epoch):
                self._ducker.restore()
            ready_event.set()
