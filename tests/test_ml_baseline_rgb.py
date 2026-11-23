"""Pruebas rápidas sin descargar imágenes ni tocar el conjunto test."""

import unittest

import pandas as pd

from src.ml_baseline_rgb import (
    evaluate_rgb_baseline,
    make_demo_data,
    prepare_training_data,
)


class RGBBaselineTests(unittest.TestCase):
    def setUp(self):
        self.rgb, self.splits = make_demo_data()

    def test_train_only_and_features(self):
        X, y, paths = prepare_training_data(self.rgb, self.splits)
        self.assertEqual(X.shape, (64, 6))
        self.assertEqual(len(y), 64)
        test_paths = set(self.splits.loc[
            self.splits["split"] == "test", "image_path"
        ])
        self.assertTrue(test_paths.isdisjoint(paths))

    def test_folds_and_metrics(self):
        X, y, paths = prepare_training_data(self.rgb, self.splits)
        result, folds = evaluate_rgb_baseline(X, y, paths)
        self.assertEqual(len(folds), 64)
        self.assertEqual(set(folds["fold"]), set(range(5)))
        self.assertTrue(folds["image_path"].is_unique)
        self.assertGreaterEqual(result["cv_f1_macro_mean"], 0)
        self.assertLessEqual(result["cv_accuracy_mean"], 1)

    def test_changing_test_does_not_change_train_result(self):
        X, y, paths = prepare_training_data(self.rgb, self.splits)
        initial, _ = evaluate_rgb_baseline(X, y, paths)

        modified = self.rgb.copy()
        test_paths = set(self.splits.loc[
            self.splits["split"] == "test", "image_path"
        ])
        modified.loc[
            modified["image_path"].isin(test_paths), "rojo_medio"
        ] += 9999
        X2, y2, paths2 = prepare_training_data(modified, self.splits)
        after, _ = evaluate_rgb_baseline(X2, y2, paths2)
        self.assertEqual(initial, after)

    def test_duplicate_paths_rejected(self):
        duplicate = pd.concat(
            [self.rgb, self.rgb.iloc[[0]]], ignore_index=True
        )
        with self.assertRaisesRegex(ValueError, "duplicadas"):
            prepare_training_data(duplicate, self.splits)


if __name__ == "__main__":
    unittest.main()
