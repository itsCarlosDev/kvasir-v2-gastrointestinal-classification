"""Baseline RGB de Kvasir v2 (issue #1).

Usa solo las imágenes marcadas como train en metadata/splits.csv.
El test permanece reservado para la evaluación final del proyecto.

Ejemplos:
    python -m src.ml_baseline_rgb --demo
    python -m src.ml_baseline_rgb --rgb-csv data/rgb_features.csv \
        --splits-csv metadata/splits.csv
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_validate
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

RANDOM_STATE = 42
N_FOLDS = 5
RGB_FEATURES = (
    "rojo_medio", "verde_medio", "azul_medio",
    "rojo_std", "verde_std", "azul_std",
)
CLASS_NAMES = (
    "dyed-lifted-polyps",
    "dyed-resection-margins",
    "esophagitis",
    "normal-cecum",
    "normal-pylorus",
    "normal-z-line",
    "polyps",
    "ulcerative-colitis",
)


def make_demo_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Datos ficticios solo para probar el código (NO son resultados)."""
    rng = np.random.default_rng(RANDOM_STATE)
    rows = []
    splits = []
    for class_name in CLASS_NAMES:
        for index in range(10):
            image_path = f"{class_name}/{class_name}/demo_{index:02d}.jpg"
            values = rng.normal(size=len(RGB_FEATURES))
            rows.append({
                "image_path": image_path,
                "clase": class_name,
                **dict(zip(RGB_FEATURES, values)),
            })
            splits.append({
                "image_path": image_path,
                "class_name": class_name,
                "split": "train" if index < 8 else "test",
            })
    return pd.DataFrame(rows), pd.DataFrame(splits)


def prepare_training_data(
    rgb_df: pd.DataFrame, splits_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    """Alinea las características RGB con el manifest, sin leer test como X/y."""
    required_rgb = {"image_path", *RGB_FEATURES}
    missing_rgb = required_rgb - set(rgb_df.columns)
    if missing_rgb:
        raise ValueError(f"Faltan columnas RGB: {sorted(missing_rgb)}")

    if "clase" in rgb_df.columns:
        rgb_class_column = "clase"
    elif "class_name" in rgb_df.columns:
        rgb_class_column = "class_name"
    else:
        raise ValueError("El CSV RGB necesita una columna 'clase' o 'class_name'.")

    required_manifest = {"image_path", "class_name", "split"}
    missing_manifest = required_manifest - set(splits_df.columns)
    if missing_manifest:
        raise ValueError(f"Faltan columnas en splits.csv: {sorted(missing_manifest)}")

    if rgb_df["image_path"].duplicated().any():
        raise ValueError("Hay rutas image_path duplicadas en el CSV RGB.")
    if splits_df["image_path"].duplicated().any():
        raise ValueError("Hay rutas image_path duplicadas en splits.csv.")
    if not splits_df["split"].isin(["train", "test"]).all():
        raise ValueError("El manifest debe contener únicamente splits 'train' o 'test'.")

    train_manifest = splits_df.loc[
        splits_df["split"] == "train", ["image_path", "class_name"]
    ]
    rgb_values = rgb_df[["image_path", rgb_class_column, *RGB_FEATURES]].rename(
        columns={rgb_class_column: "rgb_class_name"}
    )
    train = train_manifest.merge(
        rgb_values, on="image_path", how="left",
        validate="one_to_one", indicator=True,
    )
    missing_images = train.loc[train["_merge"] != "both", "image_path"]
    if not missing_images.empty:
        raise ValueError(
            f"Faltan características RGB de {len(missing_images)} imágenes train. "
            f"Ejemplo: {missing_images.iloc[0]}. "
            "Comprueba que image_path sea relativo a la misma raíz en ambos CSV."
        )
    if (train["class_name"] != train["rgb_class_name"]).any():
        raise ValueError("Las clases del CSV RGB y de splits.csv no coinciden.")

    unknown = set(train["class_name"]) - set(CLASS_NAMES)
    if unknown:
        raise ValueError(f"Clases desconocidas: {sorted(unknown)}")

    train = train.sort_values("image_path").reset_index(drop=True)
    X = train[list(RGB_FEATURES)].apply(pd.to_numeric, errors="raise")
    if X.isna().all(axis=0).any() or np.isinf(X.to_numpy()).any():
        raise ValueError("Hay columnas totalmente vacías o valores infinitos en RGB.")
    y = train["class_name"].map({name: i for i, name in enumerate(CLASS_NAMES)})
    if y.value_counts().reindex(range(8), fill_value=0).min() < N_FOLDS:
        raise ValueError("Se necesitan al menos 5 ejemplos train por cada clase.")
    return X, y.astype(int), train["image_path"]


def evaluate_rgb_baseline(
    X: pd.DataFrame, y: pd.Series, image_paths: pd.Series,
) -> tuple[dict, pd.DataFrame]:
    """CV estratificada dentro de train; imputación y escalado en el Pipeline."""
    model = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
        ("clf", LogisticRegression(max_iter=3000, random_state=RANDOM_STATE)),
    ])
    cv = StratifiedKFold(
        n_splits=N_FOLDS, shuffle=True, random_state=RANDOM_STATE
    )
    scores = cross_validate(
        model, X, y, cv=cv,
        scoring={"accuracy": "accuracy", "f1_macro": "f1_macro"},
        error_score="raise",
    )
    result = {
        "model": "LogisticRegression",
        "features": "rgb",
        "n_train": len(X),
        "cv_folds": N_FOLDS,
        "seed": RANDOM_STATE,
        "cv_accuracy_mean": float(np.mean(scores["test_accuracy"])),
        "cv_accuracy_std": float(np.std(scores["test_accuracy"])),
        "cv_f1_macro_mean": float(np.mean(scores["test_f1_macro"])),
        "cv_f1_macro_std": float(np.std(scores["test_f1_macro"])),
    }

    fold_rows = []
    for fold, (_, validation_indices) in enumerate(cv.split(X, y)):
        fold_rows.extend(
            {"image_path": image_paths.iloc[i], "fold": fold}
            for i in validation_indices
        )
    fold_df = pd.DataFrame(fold_rows).sort_values("image_path")
    return result, fold_df


def main() -> None:
    parser = argparse.ArgumentParser(description="Baseline RGB, sin evaluar test.")
    parser.add_argument("--rgb-csv", type=Path, help="CSV RGB ya extraído.")
    parser.add_argument("--splits-csv", type=Path, help="Manifest de François.")
    parser.add_argument(
        "--output-dir", type=Path, default=Path("results"),
        help="Directorio para resultados reales.",
    )
    parser.add_argument(
        "--demo", action="store_true",
        help="Smoke test con datos simulados; NO guarda métricas.",
    )
    args = parser.parse_args()

    if args.demo:
        rgb_df, splits_df = make_demo_data()
        print("DEMO SINTÉTICA: las métricas no son resultados del proyecto.")
    else:
        if args.rgb_csv is None or args.splits_csv is None:
            parser.error("Indica --rgb-csv y --splits-csv, o utiliza --demo.")
        rgb_df = pd.read_csv(args.rgb_csv)
        splits_df = pd.read_csv(args.splits_csv)

    X, y, image_paths = prepare_training_data(rgb_df, splits_df)
    result, fold_df = evaluate_rgb_baseline(X, y, image_paths)
    print(f"Train: {result['n_train']} imágenes; {X.shape[1]} variables RGB")
    print(f"Accuracy CV: {result['cv_accuracy_mean']:.4f} "
          f"± {result['cv_accuracy_std']:.4f}")
    print(f"F1-macro CV: {result['cv_f1_macro_mean']:.4f} "
          f"± {result['cv_f1_macro_std']:.4f}")

    if not args.demo:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        pd.DataFrame([result]).to_csv(
            args.output_dir / "cv_rgb.csv", index=False
        )
        fold_df.to_csv(
            args.output_dir / "cv_rgb_folds.csv", index=False
        )
        print(f"Guardado en {args.output_dir}; test NO utilizado.")


if __name__ == "__main__":
    main()
