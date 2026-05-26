import numpy as np
import pytest
import tempfile
from pathlib import Path


@pytest.fixture
def synthetic_celsius_array() -> np.ndarray:
    """2D float32 array simulating a thermal TIFF with a hot fire region and cool background.

    Returns a (512, 640) float32 ndarray with a diagonal band of hot pixels (200-400°C)
    against a cool background (~25°C), plus Gaussian noise.
    """
    rng = np.random.default_rng(42)
    img = np.full((512, 640), 25.0, dtype=np.float32)
    img += rng.normal(0, 1.5, img.shape).astype(np.float32)

    hot_region = np.zeros((512, 640), dtype=bool)
    hot_region[100:250, 200:420] = True
    hot_y, hot_x = np.where(hot_region)
    for y, x in zip(hot_y, hot_x):
        dist_from_center = np.sqrt(((x - 310) / 150) ** 2 + ((y - 175) / 100) ** 2)
        temp = 400.0 - 200.0 * dist_from_center
        img[y, x] = max(temp, 80.0) + rng.normal(0, 3.0)

    return img.astype(np.float32)


@pytest.fixture
def celsius_fire_array(synthetic_celsius_array: np.ndarray) -> np.ndarray:
    """Alias for synthetic_celsius_array — thermal array with fire region."""
    return synthetic_celsius_array


@pytest.fixture
def celsius_nofire_array() -> np.ndarray:
    """2D float32 array simulating a no-fire thermal TIFF — all pixels below 50°C."""
    rng = np.random.default_rng(99)
    img = np.full((512, 640), 25.0, dtype=np.float32)
    img += rng.normal(0, 2.0, img.shape).astype(np.float32)
    return np.clip(img, 0, 50).astype(np.float32)


@pytest.fixture
def celsius_with_nan() -> np.ndarray:
    """2D float32 array with NaN values in corner regions, simulating masked/bad pixels."""
    rng = np.random.default_rng(7)
    img = np.full((200, 300), 30.0, dtype=np.float32)
    img += rng.normal(0, 2.0, img.shape).astype(np.float32)
    img[30:80, 200:280] = 200.0
    img[0:20, 0:300] = np.nan
    img[180:200, 0:300] = np.nan
    return img


@pytest.fixture
def synthetic_fire_mask(celsius_fire_array: np.ndarray) -> np.ndarray:
    """Binary mask (uint8) corresponding to fire pixels above 150°C."""
    return ((celsius_fire_array > 150.0) & (~np.isnan(celsius_fire_array))).astype(np.uint8)


@pytest.fixture
def sample_bboxes() -> list[dict]:
    """Sample pixel-coordinate bounding boxes in cluster_fire_regions output format."""
    return [
        {"x_min": 220, "y_min": 110, "x_max": 300, "y_max": 170,
         "fill_ratio": 0.44, "area_px": 4800, "n_pixels": 2100},
        {"x_min": 300, "y_min": 130, "x_max": 350, "y_max": 170,
         "fill_ratio": 0.50, "area_px": 2000, "n_pixels": 900},
    ]


@pytest.fixture
def single_bbox() -> list[dict]:
    """Single bbox dict in cluster_fire_regions output format."""
    return [{"x_min": 100, "y_min": 80, "x_max": 160, "y_max": 130,
             "fill_ratio": 0.67, "area_px": 3000, "n_pixels": 2000}]


@pytest.fixture
def sample_config_dict() -> dict:
    """Valid auto_label config dict for wildfire (150°C threshold)."""
    return {
        "absolute_threshold": 150.0,
        "gradient_threshold": 40.0,
        "min_area": 50,
        "max_aspect_ratio": 8.0,
        "dbscan_eps": 30,
        "dbscan_min_samples": 5,
        "max_bbox_ratio": 0.4,
        "kmeans_subdivide_threshold": 500,
        "min_fill_ratio": 0.15,
        "class_id": 0,
    }


@pytest.fixture
def temp_data_dir(tmp_path: Path) -> Path:
    """Temporary directory with mock image/label structure for split/pipeline tests."""
    images_dir = tmp_path / "images" / "all"
    labels_dir = tmp_path / "labels" / "all"
    images_dir.mkdir(parents=True)
    labels_dir.mkdir(parents=True)

    prefixes = ["flame_fire", "flame_nofire", "hanna_plot1", "hanna_plot2"]
    counts = {"flame_fire": 20, "flame_nofire": 10, "hanna_plot1": 15, "hanna_plot2": 12}

    for prefix, count in counts.items():
        for i in range(count):
            img_name = f"{prefix}_{i:04d}.jpg"
            (images_dir / img_name).touch()
            label_name = f"{prefix}_{i:04d}.txt"
            label_file = labels_dir / label_name
            if "nofire" not in prefix:
                label_file.write_text(f"0 0.45{i%10} 0.56{i%8} 0.23 0.31\n")
            else:
                label_file.write_text("")

    return tmp_path


@pytest.fixture
def test_data_dir() -> Path:
    """Path to tests/data/ with real FLAME TIFFs for integration tests."""
    return Path(__file__).parent / "data"
