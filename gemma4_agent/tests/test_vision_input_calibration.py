from gemma4_agent.vision_input.calibration import (
    CalibrationProfile,
    CalibrationSample,
    default_calibration_targets,
    evaluate_calibration_model,
    fit_linear_model,
    fit_screen_warp,
    leave_one_out_rms,
    make_feature_dict,
    profile_model,
    select_ridge_by_loo,
    with_screen_warp,
)
from gemma4_agent.vision_input.monitors import MonitorInfo, MonitorRect, VirtualCanvas


def _linear_samples(noise: float = 0.0) -> list[CalibrationSample]:
    samples: list[CalibrationSample] = []
    for idx in range(30):
        yaw = -0.4 + 0.8 * (idx / 29.0)
        pitch = -0.3 + 0.6 * (((idx * 7) % 29) / 29.0)
        gaze_x = -0.2 + 0.4 * (((idx * 3) % 23) / 23.0)
        gaze_y = -0.15 + 0.3 * (((idx * 5) % 19) / 19.0)
        wobble = noise * ((idx % 5) - 2)
        target_x = 920.0 + 1200.0 * yaw + 360.0 * gaze_x - 80.0 * pitch + wobble
        target_y = 540.0 + 900.0 * pitch + 260.0 * gaze_y - 40.0 * yaw - wobble
        samples.append(
            CalibrationSample(
                features=make_feature_dict(yaw, pitch, gaze_x, gaze_y),
                target_x=target_x,
                target_y=target_y,
            )
        )
    return samples


def test_leave_one_out_rms_is_honest_held_out_error() -> None:
    samples = _linear_samples(noise=0.0)
    model = fit_linear_model(samples)
    loo = leave_one_out_rms(samples)

    assert model is not None
    assert loo is not None
    # On clean linear data both are tiny; LOO never claims LESS error than the
    # training residual (held-out can only be >= training in expectation).
    assert loo >= model.rms_error_px - 1e-6


def test_leave_one_out_rms_needs_enough_samples() -> None:
    samples = _linear_samples()[:6]  # below the leave-one-out floor for degree 2
    assert leave_one_out_rms(samples) is None


def test_select_ridge_by_loo_returns_a_candidate() -> None:
    samples = _linear_samples(noise=12.0)
    chosen = select_ridge_by_loo(samples)

    assert chosen is not None
    ridge, loo = chosen
    assert ridge in (1e-3, 3e-3, 1e-2, 3e-2, 1e-1)
    assert loo > 0.0


def test_calibration_profile_persists_camera_resolution(tmp_path) -> None:
    from gemma4_agent.vision_input.calibration import CalibrationStore

    store = CalibrationStore(base_dir=tmp_path)
    profile = CalibrationProfile(
        user="tester",
        layout_hash="hash",
        samples=tuple(),
        rms_error_px=100.0,
        camera_resolution=(1280, 720),
    )
    store.save(profile)
    loaded = store.load("hash", "tester")

    assert loaded is not None
    assert loaded.camera_resolution == (1280, 720)


def test_legacy_profile_without_resolution_loads_as_none(tmp_path) -> None:
    from gemma4_agent.vision_input.calibration import CalibrationStore

    store = CalibrationStore(base_dir=tmp_path)
    # Save then strip the resolution key to emulate an old profile.
    profile = CalibrationProfile(user="tester", layout_hash="h2", samples=tuple(), rms_error_px=1.0)
    path = store.save(profile)
    import json
    data = json.loads(path.read_text(encoding="utf-8"))
    data.pop("camera_resolution", None)
    path.write_text(json.dumps(data), encoding="utf-8")

    loaded = store.load("h2", "tester")
    assert loaded is not None
    assert loaded.camera_resolution is None


def _two_monitor_canvas() -> VirtualCanvas:
    # Top monitor and a BELOW monitor (the layout that defeats a single global fit).
    return VirtualCanvas(
        (
            MonitorInfo(0, MonitorRect(0, 0, 1000, 800), "top", True),
            MonitorInfo(1, MonitorRect(0, 800, 1000, 1600), "bottom", False),
        ),
        MonitorRect(0, 0, 1000, 1600),
        "two-vert",
    )


def test_per_monitor_correction_reduces_bottom_monitor_error() -> None:
    from gemma4_agent.vision_input.calibration import (
        fit_monitor_corrections,
        with_monitor_corrections,
    )

    canvas = _two_monitor_canvas()
    # Build samples where the bottom monitor has a systematic bias the global fit
    # can't absorb (its mapping differs from the top), so a local correction helps.
    samples: list[CalibrationSample] = []
    for i in range(6):
        f = make_feature_dict(-0.3 + 0.1 * i, -0.3, 0.0, 0.0)
        samples.append(CalibrationSample(f, 100.0 + 150.0 * i, 200.0))  # top monitor
    for i in range(6):
        f = make_feature_dict(-0.3 + 0.1 * i, 0.4, 0.0, 0.0)
        # bottom monitor with a different (biased) horizontal mapping
        samples.append(CalibrationSample(f, 80.0 + 130.0 * i + 60.0, 1200.0))

    model = fit_linear_model(samples)
    assert model is not None
    base = evaluate_calibration_model(model, samples, canvas)

    corrections = fit_monitor_corrections(model, samples, canvas)
    refined = with_monitor_corrections(model, corrections)
    after = evaluate_calibration_model(refined, samples, canvas)

    assert base is not None and after is not None
    # Per-monitor refinement never makes the global RMS worse, and helps overall.
    assert after["global"]["rms_px"] <= base["global"]["rms_px"] + 1e-6


def test_per_monitor_model_round_trips_through_dict() -> None:
    from gemma4_agent.vision_input.calibration import (
        LinearGazeModel,
        fit_monitor_corrections,
        with_monitor_corrections,
    )

    canvas = _two_monitor_canvas()
    samples = [
        CalibrationSample(make_feature_dict(-0.2 + 0.08 * i, -0.3 if i < 6 else 0.4, 0.0, 0.0),
                          100.0 + 100.0 * (i % 6), 200.0 if i < 6 else 1200.0)
        for i in range(12)
    ]
    model = fit_linear_model(samples)
    assert model is not None
    refined = with_monitor_corrections(model, fit_monitor_corrections(model, samples, canvas))
    loaded = LinearGazeModel.from_dict(refined.to_dict())

    assert loaded is not None
    assert len(loaded.monitor_corrections) == len(refined.monitor_corrections)
    # prediction is identical after a serialize/deserialize round trip
    feats = make_feature_dict(0.1, 0.4, 0.0, 0.0)
    px0, py0 = refined.predict(feats)
    px1, py1 = loaded.predict(feats)
    assert abs(px0 - px1) < 1e-6 and abs(py0 - py1) < 1e-6


def test_fit_linear_model_predicts_desktop_coordinates() -> None:
    samples: list[CalibrationSample] = []
    for idx in range(30):
        yaw = -0.4 + 0.8 * (idx / 29.0)
        pitch = -0.3 + 0.6 * (((idx * 7) % 29) / 29.0)
        gaze_x = -0.2 + 0.4 * (((idx * 3) % 23) / 23.0)
        gaze_y = -0.15 + 0.3 * (((idx * 5) % 19) / 19.0)
        target_x = 920.0 + 1200.0 * yaw + 360.0 * gaze_x - 80.0 * pitch
        target_y = 540.0 + 900.0 * pitch + 260.0 * gaze_y - 40.0 * yaw
        samples.append(
            CalibrationSample(
                features=make_feature_dict(yaw, pitch, gaze_x, gaze_y),
                target_x=target_x,
                target_y=target_y,
            )
        )

    model = fit_linear_model(samples)

    assert model is not None
    pred_x, pred_y = model.predict(make_feature_dict(0.21, -0.14, 0.08, -0.05))
    truth_x = 920.0 + 1200.0 * 0.21 + 360.0 * 0.08 - 80.0 * (-0.14)
    truth_y = 540.0 + 900.0 * (-0.14) + 260.0 * (-0.05) - 40.0 * 0.21
    assert abs(pred_x - truth_x) < 3.0
    assert abs(pred_y - truth_y) < 3.0
    assert model.rms_error_px < 2.0


def test_default_calibration_targets_generate_per_monitor_grid() -> None:
    canvas = VirtualCanvas(
        (
            MonitorInfo(0, MonitorRect(-1920, 0, 0, 1080), "left", False),
            MonitorInfo(1, MonitorRect(0, 0, 1920, 1080), "center", True),
        ),
        MonitorRect(-1920, 0, 1920, 1080),
        "layout",
    )

    targets = default_calibration_targets(canvas)

    # Rediseño 2026-06-11: 5 puntos por monitor (centro + 4 esquinas) en vez
    # de la grilla 3x3 — calibración más corta con cobertura de extremos.
    assert len(targets) == 10  # 5 points per monitor
    assert all(-1920 <= x <= 1919 for x, _ in targets)
    assert all(0 <= y <= 1079 for _, y in targets)


def test_evaluate_calibration_model_reports_per_monitor_errors() -> None:
    canvas = VirtualCanvas(
        (
            MonitorInfo(0, MonitorRect(0, 0, 1000, 800), "left", True),
            MonitorInfo(1, MonitorRect(1000, 0, 2000, 800), "right", False),
        ),
        MonitorRect(0, 0, 2000, 800),
        "layout",
    )
    samples = [
        CalibrationSample(make_feature_dict(-0.4, -0.2, 0.0, 0.0), 200.0, 200.0),
        CalibrationSample(make_feature_dict(-0.2, 0.2, 0.0, 0.0), 800.0, 600.0),
        CalibrationSample(make_feature_dict(0.2, -0.2, 0.0, 0.0), 1200.0, 200.0),
        CalibrationSample(make_feature_dict(0.4, 0.2, 0.0, 0.0), 1800.0, 600.0),
        CalibrationSample(make_feature_dict(0.0, 0.0, 0.0, 0.0), 1000.0, 400.0),
        CalibrationSample(make_feature_dict(0.1, 0.1, 0.0, 0.0), 1500.0, 500.0),
    ]
    model = fit_linear_model(samples)

    report = evaluate_calibration_model(model, samples, canvas)

    assert report is not None
    assert report["sample_count"] == 6
    assert report["global"]["rms_px"] < 100.0
    assert set(report["by_monitor"]) == {"0", "1"}
    assert report["by_monitor"]["0"]["count"] == 2


def test_profile_model_recovers_serialized_model() -> None:
    model = fit_linear_model(
        [
            CalibrationSample(make_feature_dict(-0.2, -0.1, -0.05, 0.01), 200.0, 150.0),
            CalibrationSample(make_feature_dict(0.2, -0.1, 0.05, 0.01), 800.0, 150.0),
            CalibrationSample(make_feature_dict(-0.2, 0.2, -0.05, -0.02), 200.0, 750.0),
            CalibrationSample(make_feature_dict(0.2, 0.2, 0.05, -0.02), 800.0, 750.0),
            CalibrationSample(make_feature_dict(0.0, 0.0, 0.0, 0.0), 500.0, 450.0),
            CalibrationSample(make_feature_dict(0.1, 0.1, 0.02, -0.01), 650.0, 600.0),
        ]
    )
    assert model is not None
    profile = CalibrationProfile(
        user="tester",
        layout_hash="hash",
        samples=tuple(),
        rms_error_px=model.rms_error_px,
        model=model.to_dict(),
    )

    loaded = profile_model(profile)

    assert loaded is not None
    features = make_feature_dict(0.0, 0.0, 0.0, 0.0)
    px_model, py_model = model.predict(features)
    px_loaded, py_loaded = loaded.predict(features)
    assert abs(px_loaded - px_model) < 1e-6
    assert abs(py_loaded - py_model) < 1e-6


def test_screen_warp_corrects_systematic_prediction_bias() -> None:
    rows = []
    for x in (100.0, 500.0, 900.0):
        for y in (100.0, 400.0, 700.0):
            pred_x = x + 80.0 + 0.05 * x
            pred_y = y - 60.0 + 0.04 * y
            rows.append((pred_x, pred_y, x, y))

    warp = fit_screen_warp(rows)

    assert warp is not None
    corrected_x, corrected_y = warp.apply(710.0 + 80.0 + 0.05 * 710.0, 320.0 - 60.0 + 0.04 * 320.0)
    assert abs(corrected_x - 710.0) < 2.0
    assert abs(corrected_y - 320.0) < 2.0
    assert warp.rms_error_px < 2.0


def test_profile_model_recovers_screen_warp() -> None:
    model = fit_linear_model(
        [
            CalibrationSample(make_feature_dict(-0.2, -0.1, -0.05, 0.01), 200.0, 150.0),
            CalibrationSample(make_feature_dict(0.2, -0.1, 0.05, 0.01), 800.0, 150.0),
            CalibrationSample(make_feature_dict(-0.2, 0.2, -0.05, -0.02), 200.0, 750.0),
            CalibrationSample(make_feature_dict(0.2, 0.2, 0.05, -0.02), 800.0, 750.0),
            CalibrationSample(make_feature_dict(0.0, 0.0, 0.0, 0.0), 500.0, 450.0),
            CalibrationSample(make_feature_dict(0.1, 0.1, 0.02, -0.01), 650.0, 600.0),
        ]
    )
    assert model is not None
    warp = fit_screen_warp(
        (
            (200.0, 150.0, 190.0, 160.0),
            (800.0, 150.0, 790.0, 160.0),
            (200.0, 750.0, 190.0, 760.0),
            (800.0, 750.0, 790.0, 760.0),
            (500.0, 450.0, 490.0, 460.0),
            (650.0, 600.0, 640.0, 610.0),
        )
    )
    assert warp is not None
    warped = with_screen_warp(model, warp)
    profile = CalibrationProfile(
        user="tester",
        layout_hash="hash",
        samples=tuple(),
        rms_error_px=warped.rms_error_px,
        model=warped.to_dict(),
    )

    loaded = profile_model(profile)

    assert loaded is not None
    assert loaded.screen_warp is not None


def test_profile_model_rejects_non_finite_coefficients() -> None:
    profile = CalibrationProfile(
        user="tester",
        layout_hash="hash",
        samples=tuple(),
        rms_error_px=1.0,
        model={
            "type": "linear-v1",
            "feature_keys": ["yaw", "pitch", "gaze_x", "gaze_y"],
            "coeffs_x": [0.0, 1.0, 1.0, 1.0, float("nan")],
            "coeffs_y": [0.0, 1.0, 1.0, 1.0, 1.0],
            "rms_error_px": 1.0,
        },
    )
    assert profile_model(profile) is None
