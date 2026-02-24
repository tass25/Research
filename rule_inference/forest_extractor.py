"""
Random forest rule extractor for Group B.

Trains sklearn RandomForestClassifier on D_legacy and extracts
rules from the most important trees and paths.
"""

from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, f1_score

from cbf_data.loader import SimulationDataset
from rule_inference.tree_extractor import (
    CandidateRule,
    _extract_paths,
    _path_to_rule_text,
    _merge_pass_rules_to_dnf,
    _merge_fail_rules_to_dnf,
)


def extract_rules_from_forest(
    dataset: SimulationDataset,
    n_estimators: int = 100,
    max_depth: Optional[int] = 4,
    min_samples_leaf: int = 5,
    random_state: int = 42,
    test_size: float = 0.2,
    top_k_trees: int = 5,
) -> Tuple[List[CandidateRule], RandomForestClassifier]:
    """Train a random forest and extract rules from the best individual trees.

    Selects the top-k trees (by validation accuracy) and extracts their paths
    as candidate rules.

    Args:
        dataset: SimulationDataset to learn from.
        n_estimators: Number of trees in the forest.
        max_depth: Maximum depth per tree.
        min_samples_leaf: Minimum samples per leaf.
        random_state: Random seed.
        test_size: Validation split.
        top_k_trees: Number of best trees to extract rules from.

    Returns:
        Tuple of (list of CandidateRule, fitted RandomForestClassifier).
    """
    X, y = dataset.get_feature_matrix()
    feature_names = dataset.feature_names

    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )

    clf = RandomForestClassifier(
        n_estimators=n_estimators,
        max_depth=max_depth,
        min_samples_leaf=min_samples_leaf,
        random_state=random_state,
    )
    clf.fit(X_train, y_train)

    # Overall forest metrics
    forest_train_acc = accuracy_score(y_train, clf.predict(X_train))
    forest_val_acc = accuracy_score(y_val, clf.predict(X_val))
    forest_train_f1 = f1_score(y_train, clf.predict(X_train), zero_division=0)
    forest_val_f1 = f1_score(y_val, clf.predict(X_val), zero_division=0)

    # Feature importances from the forest
    importances = {
        feat: float(imp)
        for feat, imp in zip(feature_names, clf.feature_importances_)
    }

    # Rank individual trees by validation accuracy
    tree_scores = []
    for idx, tree in enumerate(clf.estimators_):
        tree_val_acc = accuracy_score(y_val, tree.predict(X_val))
        tree_scores.append((idx, tree_val_acc, tree))
    tree_scores.sort(key=lambda x: x[1], reverse=True)

    # Extract rules from the top-k trees
    candidates = []
    for rank, (tree_idx, tree_val_acc, tree) in enumerate(tree_scores[:top_k_trees]):
        paths = _extract_paths(tree, feature_names)

        # Individual path rules from this tree
        for i, path in enumerate(paths):
            rule_text = _path_to_rule_text(path["conditions"])
            predicted = path["predicted_class"]
            rule_type = "pass" if predicted == 1 else "fail"
            rule_id = f"RF_t{tree_idx}_r{i + 1}"

            candidates.append(CandidateRule(
                rule_id=rule_id,
                rule_text=rule_text,
                rule_type=rule_type,
                train_accuracy=forest_train_acc,
                val_accuracy=tree_val_acc,
                train_f1=forest_train_f1,
                val_f1=forest_val_f1,
                complexity=len(path["conditions"]),
                support=path["n_samples"],
                confidence=path["confidence"],
                source_model="random_forest",
                feature_importances=importances,
            ))

        # Merged DNF from this tree
        pass_paths = [p for p in paths if p["predicted_class"] == 1]
        fail_paths = [p for p in paths if p["predicted_class"] == 0]

        if pass_paths:
            pass_dnf = _merge_pass_rules_to_dnf(pass_paths)
            total_support = sum(p["n_samples"] for p in pass_paths)
            avg_conf = (
                sum(p["confidence"] * p["n_samples"] for p in pass_paths) / total_support
                if total_support > 0 else 0.0
            )
            candidates.append(CandidateRule(
                rule_id=f"RF_DNF_t{tree_idx}_pass",
                rule_text=pass_dnf,
                rule_type="pass",
                train_accuracy=forest_train_acc,
                val_accuracy=tree_val_acc,
                train_f1=forest_train_f1,
                val_f1=forest_val_f1,
                complexity=sum(len(p["conditions"]) for p in pass_paths),
                support=total_support,
                confidence=avg_conf,
                source_model="random_forest_dnf",
                feature_importances=importances,
            ))

        if fail_paths:
            fail_dnf = _merge_fail_rules_to_dnf(fail_paths)
            total_support = sum(p["n_samples"] for p in fail_paths)
            avg_conf = (
                sum(p["confidence"] * p["n_samples"] for p in fail_paths) / total_support
                if total_support > 0 else 0.0
            )
            candidates.append(CandidateRule(
                rule_id=f"RF_DNF_t{tree_idx}_fail",
                rule_text=fail_dnf,
                rule_type="fail",
                train_accuracy=forest_train_acc,
                val_accuracy=tree_val_acc,
                train_f1=forest_train_f1,
                val_f1=forest_val_f1,
                complexity=sum(len(p["conditions"]) for p in fail_paths),
                support=total_support,
                confidence=avg_conf,
                source_model="random_forest_dnf",
                feature_importances=importances,
            ))

    return candidates, clf


def extract_high_confidence_rules(
    dataset: SimulationDataset,
    n_estimators: int = 200,
    max_depth: Optional[int] = 5,
    min_samples_leaf: int = 5,
    random_state: int = 42,
    test_size: float = 0.2,
    min_confidence: float = 0.75,
    min_support: int = 10,
) -> List[CandidateRule]:
    """Extract only high-confidence rules from a random forest.

    Filters rules by minimum confidence and support thresholds,
    producing a curated set of reliable candidate rules.

    Args:
        dataset: SimulationDataset to learn from.
        min_confidence: Minimum leaf confidence to keep a rule.
        min_support: Minimum samples at the leaf.

    Returns:
        List of high-confidence CandidateRule objects.
    """
    all_rules, clf = extract_rules_from_forest(
        dataset,
        n_estimators=n_estimators,
        max_depth=max_depth,
        min_samples_leaf=min_samples_leaf,
        random_state=random_state,
        test_size=test_size,
        top_k_trees=10,
    )

    filtered = [
        r for r in all_rules
        if r.confidence >= min_confidence
        and r.support >= min_support
        and r.source_model == "random_forest"  # Individual paths only
    ]

    # Deduplicate by rule_text
    seen = set()
    unique = []
    for r in filtered:
        if r.rule_text not in seen:
            seen.add(r.rule_text)
            unique.append(r)

    return unique
