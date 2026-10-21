from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(os.environ.get("PUBLIC_TASKS_DIR", "public_tasks")).resolve()


def json_safe(value):
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        if np.isnan(value):
            return None
        return float(value)
    return value


def profile_task(folder: str, target: str) -> dict:
    root = ROOT / folder
    train = pd.read_csv(root / "train.csv")
    test = pd.read_csv(root / "test.csv")
    dictionary = pd.read_csv(root / "data_dictionary.csv")
    sample = pd.read_csv(root / "sample_submission.csv")

    features_train = [c for c in train.columns if c not in {"id", target}]
    features_test = [c for c in test.columns if c != "id"]
    object_columns = [c for c in features_train if train[c].dtype == "object"]
    numeric_columns = [c for c in features_train if pd.api.types.is_numeric_dtype(train[c])]

    unseen_categories = {}
    for column in object_columns:
        train_values = set(train[column].dropna().astype(str))
        test_values = set(test[column].dropna().astype(str))
        unseen = sorted(test_values - train_values)
        if unseen:
            unseen_categories[column] = {
                "count": len(unseen),
                "values": unseen[:20],
            }

    numeric_nonfinite = {}
    for column in numeric_columns:
        train_values = pd.to_numeric(train[column], errors="coerce").to_numpy(dtype=float)
        test_values = pd.to_numeric(test[column], errors="coerce").to_numpy(dtype=float)
        train_inf = int(np.isinf(train_values).sum())
        test_inf = int(np.isinf(test_values).sum())
        if train_inf or test_inf:
            numeric_nonfinite[column] = {"train_inf": train_inf, "test_inf": test_inf}

    dictionary_features = set(dictionary["feature"].astype(str)) if "feature" in dictionary else set()
    train_columns = set(train.columns)
    missing_rates_train = train.isna().mean().sort_values(ascending=False)
    missing_rates_test = test.isna().mean().sort_values(ascending=False)
    constant_train = [c for c in features_train if train[c].nunique(dropna=False) <= 1]

    train_feature_hash = pd.util.hash_pandas_object(train[features_train], index=False)
    test_feature_hash = pd.util.hash_pandas_object(test[features_test], index=False)
    train_hash_counts = train_feature_hash.value_counts()
    repeated_train_hashes = set(train_hash_counts[train_hash_counts > 1].index)
    shared_hashes = set(train_feature_hash) & set(test_feature_hash)
    train_hash_frame = pd.DataFrame({"feature_hash": train_feature_hash, "target": train[target]})
    target_nunique_by_hash = train_hash_frame.groupby("feature_hash", sort=False)["target"].nunique(dropna=False)
    conflicting_hashes = set(target_nunique_by_hash[target_nunique_by_hash > 1].index)
    shared_train_rows = train_feature_hash.isin(shared_hashes)
    shared_test_rows = test_feature_hash.isin(shared_hashes)

    result = {
        "folder": folder,
        "target": target,
        "shapes": {
            "train": list(train.shape),
            "test": list(test.shape),
            "dictionary": list(dictionary.shape),
            "sample_submission": list(sample.shape),
        },
        "schema": {
            "features_train": len(features_train),
            "features_test": len(features_test),
            "feature_sets_equal": set(features_train) == set(features_test),
            "feature_order_equal": features_train == features_test,
            "dictionary_matches_train_columns": dictionary_features == train_columns,
            "dictionary_missing_columns": sorted(train_columns - dictionary_features),
            "dictionary_extra_columns": sorted(dictionary_features - train_columns),
            "dictionary_columns": list(dictionary.columns),
            "object_columns": object_columns,
            "numeric_columns_count": len(numeric_columns),
            "constant_train_features": constant_train,
            "dictionary_role_counts": {
                str(k): int(v) for k, v in dictionary["role"].value_counts(dropna=False).items()
            },
            "dictionary_dtype_counts": {
                str(k): int(v) for k, v in dictionary["dtype"].value_counts(dropna=False).items()
            },
        },
        "ids": {
            "train_null": int(train["id"].isna().sum()),
            "test_null": int(test["id"].isna().sum()),
            "train_duplicate_rows": int(train["id"].duplicated().sum()),
            "test_duplicate_rows": int(test["id"].duplicated().sum()),
            "train_test_overlap": int(len(set(train["id"]) & set(test["id"]))),
            "sample_matches_test_ids": sample["id"].tolist() == test["id"].tolist(),
        },
        "duplicates": {
            "train_exact_duplicate_rows": int(train.duplicated().sum()),
            "test_exact_duplicate_rows": int(test.duplicated().sum()),
            "train_feature_duplicates_excluding_id_target": int(train.duplicated(features_train).sum()),
            "test_feature_duplicates_excluding_id": int(test.duplicated(features_test).sum()),
            "repeated_train_feature_hashes": int(len(repeated_train_hashes)),
            "repeated_train_feature_hashes_with_conflicting_targets": int(len(conflicting_hashes)),
            "train_rows_in_conflicting_feature_groups": int(train_feature_hash.isin(conflicting_hashes).sum()),
            "train_test_shared_exact_feature_hashes": int(len(shared_hashes)),
            "train_rows_with_feature_match_in_test": int(shared_train_rows.sum()),
            "test_rows_with_feature_match_in_train": int(shared_test_rows.sum()),
            "test_rows_matching_ambiguous_train_target": int(test_feature_hash.isin(conflicting_hashes).sum()),
        },
        "missing": {
            "train_total_cells": int(train.isna().sum().sum()),
            "test_total_cells": int(test.isna().sum().sum()),
            "train_columns_with_missing": int((missing_rates_train > 0).sum()),
            "test_columns_with_missing": int((missing_rates_test > 0).sum()),
            "train_top_rates": {
                k: round(float(v), 6) for k, v in missing_rates_train.head(10).items() if v > 0
            },
            "test_top_rates": {
                k: round(float(v), 6) for k, v in missing_rates_test.head(10).items() if v > 0
            },
        },
        "categoricals": {
            "unseen_test_categories": unseen_categories,
        },
        "numeric_nonfinite": numeric_nonfinite,
        "sample_submission": {
            "columns": list(sample.columns),
            "target_null": int(sample[target].isna().sum()),
            "target_unique_preview": [json_safe(x) for x in sample[target].drop_duplicates().head(10).tolist()],
        },
    }

    if pd.api.types.is_numeric_dtype(train[target]):
        result["target_profile"] = {
            "null": int(train[target].isna().sum()),
            "inf": int(np.isinf(train[target].to_numpy(dtype=float)).sum()),
            "min": float(train[target].min()),
            "max": float(train[target].max()),
            "mean": float(train[target].mean()),
            "std": float(train[target].std()),
            "quantiles": {
                str(q): float(v)
                for q, v in train[target].quantile([0, 0.01, 0.5, 0.99, 1]).items()
            },
            "zero_count": int((train[target] == 0).sum()),
            "negative_count": int((train[target] < 0).sum()),
        }
    else:
        counts = train[target].value_counts(dropna=False)
        result["target_profile"] = {
            "null": int(train[target].isna().sum()),
            "classes": int(train[target].nunique(dropna=True)),
            "class_counts": {str(k): int(v) for k, v in counts.items()},
            "class_rates": {str(k): round(float(v / len(train)), 6) for k, v in counts.items()},
            "sample_labels_subset_of_train": set(sample[target].dropna().astype(str)).issubset(
                set(train[target].dropna().astype(str))
            ),
        }

    return result


if __name__ == "__main__":
    report = {
        "regression": profile_task("regression/regression/participants", "site_eui"),
        "multiclass": profile_task("multiclass/multiclass/participants", "attack_cat"),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
