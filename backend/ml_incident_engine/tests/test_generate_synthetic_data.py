import numpy as np
import pytest

from ml_incident_engine import config as cfg
from ml_incident_engine.generate_synthetic_data import (
    augment_event,
    apply_random_rotation,
    apply_sensor_drift,
    apply_time_jitter,
    add_sensor_noise,
    generate_dataset,
    generate_event,
)


@pytest.mark.parametrize("class_label", cfg.EVENT_CLASSES)
def test_generate_event_produces_correctly_shaped_window(class_label):
    rng = np.random.default_rng(1)
    w = generate_event(class_label, rng, rider_id="r1", shift_id="s1")

    assert len(w.accel_x) == cfg.ACCEL_GYRO_SAMPLES_PER_WINDOW
    assert len(w.accel_y) == cfg.ACCEL_GYRO_SAMPLES_PER_WINDOW
    assert len(w.accel_z) == cfg.ACCEL_GYRO_SAMPLES_PER_WINDOW
    assert len(w.gyro_x) == cfg.ACCEL_GYRO_SAMPLES_PER_WINDOW
    assert len(w.gyro_y) == cfg.ACCEL_GYRO_SAMPLES_PER_WINDOW
    assert len(w.gyro_z) == cfg.ACCEL_GYRO_SAMPLES_PER_WINDOW
    assert len(w.accel_t_ms) == cfg.ACCEL_GYRO_SAMPLES_PER_WINDOW
    assert len(w.gyro_t_ms) == cfg.ACCEL_GYRO_SAMPLES_PER_WINDOW

    assert len(w.gps_speed_kmh) == cfg.GPS_SAMPLES_PER_WINDOW
    assert len(w.gps_lat) == cfg.GPS_SAMPLES_PER_WINDOW
    assert len(w.gps_lng) == cfg.GPS_SAMPLES_PER_WINDOW
    assert len(w.gps_altitude) == cfg.GPS_SAMPLES_PER_WINDOW
    assert len(w.gps_accuracy) == cfg.GPS_SAMPLES_PER_WINDOW

    assert w.class_label == class_label
    assert w.is_augmented is False
    assert w.source_event_id == w.event_id


@pytest.mark.parametrize("class_label", cfg.EVENT_CLASSES)
def test_generate_event_has_no_nan_or_inf(class_label):
    rng = np.random.default_rng(2)
    w = generate_event(class_label, rng, rider_id="r1", shift_id="s1")

    for arr in (w.accel_x, w.accel_y, w.accel_z, w.gyro_x, w.gyro_y, w.gyro_z,
                w.gps_speed_kmh, w.gps_lat, w.gps_lng, w.gps_altitude, w.gps_accuracy):
        assert np.all(np.isfinite(arr))


def test_generation_is_reproducible_with_same_seed():
    rng1 = np.random.default_rng(42)
    rng2 = np.random.default_rng(42)
    w1 = generate_event("crash", rng1, rider_id="r1", shift_id="s1", event_id="fixed-id")
    w2 = generate_event("crash", rng2, rider_id="r1", shift_id="s1", event_id="fixed-id")

    np.testing.assert_array_equal(w1.accel_x, w2.accel_x)
    np.testing.assert_array_equal(w1.gyro_z, w2.gyro_z)
    np.testing.assert_array_equal(w1.gps_speed_kmh, w2.gps_speed_kmh)


def test_generation_differs_with_different_seed():
    rng1 = np.random.default_rng(1)
    rng2 = np.random.default_rng(2)
    w1 = generate_event("crash", rng1, rider_id="r1", shift_id="s1")
    w2 = generate_event("crash", rng2, rider_id="r1", shift_id="s1")

    assert not np.array_equal(w1.accel_x, w2.accel_x)


def test_timestamps_are_non_decreasing():
    rng = np.random.default_rng(3)
    w = generate_event("crash", rng, rider_id="r1", shift_id="s1")
    assert np.all(np.diff(w.accel_t_ms) > 0)
    assert np.all(np.diff(w.gps_t_ms) > 0)


class TestAugmentation:
    def test_augmented_sibling_tagging(self):
        rng = np.random.default_rng(4)
        base = generate_event("crash", rng, rider_id="r1", shift_id="s1")
        variants = augment_event(base, rng, n_variants=5)

        assert len(variants) == 5
        for v in variants:
            assert v.is_augmented is True
            assert v.source_event_id == base.event_id
            assert v.event_id != base.event_id
            assert v.class_label == base.class_label
            assert v.rider_id == base.rider_id
            assert v.shift_id == base.shift_id

        # Augmented variants should actually differ from the base (some op applied).
        assert not all(np.array_equal(v.accel_x, base.accel_x) for v in variants)

    def test_augmented_event_ids_are_unique(self):
        rng = np.random.default_rng(5)
        base = generate_event("crash", rng, rider_id="r1", shift_id="s1")
        variants = augment_event(base, rng, n_variants=10)
        ids = [v.event_id for v in variants]
        assert len(ids) == len(set(ids))

    def test_random_rotation_changes_raw_axes(self):
        rng = np.random.default_rng(6)
        base = generate_event("crash", rng, rider_id="r1", shift_id="s1")
        rotated = apply_random_rotation(base, np.random.default_rng(7))
        assert not np.allclose(base.accel_x, rotated.accel_x)

    def test_random_rotation_preserves_accel_magnitude(self):
        rng = np.random.default_rng(8)
        base = generate_event("crash", rng, rider_id="r1", shift_id="s1")
        rotated = apply_random_rotation(base, np.random.default_rng(9))

        base_mag = np.sqrt(base.accel_x ** 2 + base.accel_y ** 2 + base.accel_z ** 2)
        rotated_mag = np.sqrt(rotated.accel_x ** 2 + rotated.accel_y ** 2 + rotated.accel_z ** 2)
        np.testing.assert_allclose(base_mag, rotated_mag, rtol=1e-6, atol=1e-6)

    def test_sensor_noise_changes_values_but_preserves_shape(self):
        rng = np.random.default_rng(10)
        base = generate_event("normal", rng, rider_id="r1", shift_id="s1")
        noisy = add_sensor_noise(base, np.random.default_rng(11))
        assert noisy.accel_x.shape == base.accel_x.shape
        assert not np.allclose(noisy.accel_x, base.accel_x)

    def test_time_jitter_keeps_timestamps_sorted(self):
        rng = np.random.default_rng(12)
        base = generate_event("normal", rng, rider_id="r1", shift_id="s1")
        jittered = apply_time_jitter(base, np.random.default_rng(13))
        assert np.all(np.diff(jittered.accel_t_ms) >= 0)

    def test_sensor_drift_is_subtle(self):
        rng = np.random.default_rng(14)
        base = generate_event("normal", rng, rider_id="r1", shift_id="s1")
        drifted = apply_sensor_drift(base, np.random.default_rng(15))
        # Drift should nudge values, not blow them up.
        assert np.max(np.abs(drifted.accel_x - base.accel_x)) < 2.0  # m/s^2


class TestGenerateDataset:
    def test_produces_expected_counts(self):
        windows = generate_dataset(events_per_class=10, augmentations_per_event=2,
                                    num_riders=3, shifts_per_rider=2, seed=1)
        expected_total = len(cfg.EVENT_CLASSES) * 10 * (1 + 2)
        assert len(windows) == expected_total

        base_count = sum(1 for w in windows if not w.is_augmented)
        assert base_count == len(cfg.EVENT_CLASSES) * 10

    def test_all_classes_present(self):
        windows = generate_dataset(events_per_class=5, augmentations_per_event=1,
                                    num_riders=2, shifts_per_rider=1, seed=2)
        labels = {w.class_label for w in windows}
        assert labels == set(cfg.EVENT_CLASSES)

    def test_riders_and_shifts_are_drawn_from_the_configured_pool(self):
        windows = generate_dataset(events_per_class=5, augmentations_per_event=1,
                                    num_riders=2, shifts_per_rider=2, seed=3)
        rider_ids = {w.rider_id for w in windows}
        assert len(rider_ids) <= 2

    def test_dataset_generation_is_reproducible(self):
        w1 = generate_dataset(events_per_class=5, augmentations_per_event=1,
                               num_riders=2, shifts_per_rider=1, seed=42)
        w2 = generate_dataset(events_per_class=5, augmentations_per_event=1,
                               num_riders=2, shifts_per_rider=1, seed=42)
        assert [w.event_id for w in w1] == [w.event_id for w in w2]
        np.testing.assert_array_equal(w1[0].accel_x, w2[0].accel_x)
