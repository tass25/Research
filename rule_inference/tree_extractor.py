"""
Decision tree rule extractor for Group B.

Trains sklearn DecisionTreeClassifier on D_legacy and extracts
each root-to-leaf path as a grammar-compliant DNF rule.
"""

from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field
import math

from sklearn.tree import DecisionTreeClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, f1_score

from cbf_data.loader import SimulationDataset


@dataclass
class CandidateRule:
    """A single candidate operational rule extracted from a model."""
    rule_id: str
    rule_text: str                  # Grammar-compliant syntax
    rule_type: str                  # "pass" or "fail"
    train_accuracy: float
    val_accuracy: float
    train_f1: float
    val_f1: float
    complexity: int                 # Number of predicates
    support: int                    # Number of training samples matching
    confidence: float               # Fraction of matching samples with predicted class
    source_model: str               # "decision_tree", "random_forest", etc.
    feature_importances: Dict[str, float] = field(default_factory=dict)


def _threshold_to_str(val: float) -> str:
    """Format a threshold value for grammar output.

    Rounds to 4 decimal places, removes trailing zeros.
    """
    rounded = round(val, 4)
    if rounded == int(rounded):
        return str(int(rounded))
    return f"{rounded:.4f}".rstrip("0").rstrip(".")


def _extract_paths(tree, feature_names: List[str]) -> List[Dict]:
    """Extract all root-to-leaf paths from a fitted decision tree.

    Each path is a list of (feature, operator, threshold) conditions
    leading to a leaf node with a class prediction.

    Returns:
        List of dicts with keys: conditions, predicted_class, n_samples,
        confidence, leaf_id
    """
    tree_ = tree.tree_
    paths = []

    def recurse(node_id: int, conditions: List[Tuple[str, str, float]]):
        # Leaf node
        if tree_.children_left[node_id] == tree_.children_right[node_id]:
            class_counts = tree_.value[node_id][0]
            predicted_class = int(class_counts.argmax())
            total = int(class_counts.sum())
            confidence = class_counts[predicted_class] / total if total > 0 else 0.0
            paths.append({
                "conditions": list(conditions),
                "predicted_class": predicted_class,  # 0=Fail, 1=Pass
                "n_samples": total,
                "confidence": confidence,
                "leaf_id": node_id,
            })
            return

        feat_name = feature_names[tree_.feature[node_id]]
        threshold = tree_.threshold[node_id]

        # Left child: feature <= threshold
        recurse(
            tree_.children_left[node_id],
            conditions + [(feat_name, "<=", threshold)],
        )
        # Right child: feature > threshold
        recurse(
            tree_.children_right[node_id],
            conditions + [(feat_name, ">", threshold)],
        )

    recurse(0, [])
    return paths


def _path_to_rule_text(conditions: List[Tuple[str, str, float]]) -> str:
    """Convert a decision path to grammar-compliant rule text.

    Produces a conjunction: pred1 AND pred2 AND ...
    """
    predicates = []
    for feat, op, thresh in conditions:
        predicates.append(f"{feat} {op} {_threshold_to_str(thresh)}")
    return " AND ".join(predicates)


def _merge_pass_rules_to_dnf(pass_paths: List[Dict]) -> str:
    """Merge multiple pass-rule paths into a single DNF rule.

    DNF = conjunction1 OR conjunction2 OR ...
    Each conjunction is a path from root to a Pass leaf.
    """
    if not pass_paths:
        return ""
    clauses = []
    for path in pass_paths:
        clause = _path_to_rule_text(path["conditions"])
        if " AND " in clause:
            clauses.append(f"({clause})")
        else:
            clauses.append(clause)
    return " OR ".join(clauses)


def _merge_fail_rules_to_dnf(fail_paths: List[Dict]) -> str:
    """Merge multiple fail-rule paths into a single DNF rule."""
    if not fail_paths:
        return ""
    clauses = []
    for path in fail_paths:
        clause = _path_to_rule_text(path["conditions"])
        if " AND " in clause:
            clauses.append(f"({clause})")
        else:
            clauses.append(clause)
    return " OR ".join(clauses)


def extract_rules_from_tree(
    dataset: SimulationDataset,
    max_depth: Optional[int] = None,
    min_samples_leaf: int = 5,
    random_state: int = 42,
    test_size: float = 0.2,
    tree_id_prefix: str = "DT",
) -> Tuple[List[CandidateRule], DecisionTreeClassifier]:
    """Train a decision tree on D_legacy and extract candidate rules.

    Args:
        dataset: SimulationDataset to learn from.
        max_depth: Maximum tree depth (None for unrestricted).
        min_samples_leaf: Minimum samples per leaf.
        random_state: Random seed for reproducibility.
        test_size: Validation split fraction.
        tree_id_prefix: Prefix for rule IDs.

    Returns:
        Tuple of (list of CandidateRule, fitted DecisionTreeClassifier).
    """
    X, y = dataset.get_feature_matrix()
    feature_names = dataset.feature_names

    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )

    clf = DecisionTreeClassifier(
        max_depth=max_depth,
        min_samples_leaf=min_samples_leaf,
        random_state=random_state,
    )
    clf.fit(X_train, y_train)

    # Overall metrics
    train_acc = accuracy_score(y_train, clf.predict(X_train))
    val_acc = accuracy_score(y_val, clf.predict(X_val))
    train_f1 = f1_score(y_train, clf.predict(X_train), zero_division=0)
    val_f1 = f1_score(y_val, clf.predict(X_val), zero_division=0)

    # Feature importances
    importances = {
        feat: float(imp)
        for feat, imp in zip(feature_names, clf.feature_importances_)
    }

    # Extract all paths
    paths = _extract_paths(clf, feature_names)

    candidates = []
    for i, path in enumerate(paths):
        rule_text = _path_to_rule_text(path["conditions"])
        predicted = path["predicted_class"]
        rule_type = "pass" if predicted == 1 else "fail"
        rule_id = f"{tree_id_prefix}_d{max_depth or 'X'}_r{i + 1}"

        candidates.append(CandidateRule(
            rule_id=rule_id,
            rule_text=rule_text,
            rule_type=rule_type,
            train_accuracy=train_acc,
            val_accuracy=val_acc,
            train_f1=train_f1,
            val_f1=val_f1,
            complexity=len(path["conditions"]),
            support=path["n_samples"],
            confidence=path["confidence"],
            source_model="decision_tree",
            feature_importances=importances,
        ))

    return candidates, clf


def extract_dnf_rules(
    dataset: SimulationDataset,
    max_depth: Optional[int] = None,
    min_samples_leaf: int = 5,
    random_state: int = 42,
    test_size: float = 0.2,
    tree_id_prefix: str = "DT_DNF",
) -> Tuple[List[CandidateRule], DecisionTreeClassifier]:
    """Extract merged DNF rules (one pass-rule, one fail-rule) from a decision tree.

    Groups all Pass paths into one DNF rule and all Fail paths into another.
    This is the grammar-compliant format: disjunction of conjunctions.

    Returns:
        Tuple of (list of 1-2 CandidateRules in DNF, fitted tree).
    """
    X, y = dataset.get_feature_matrix()
    feature_names = dataset.feature_names

    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )

    clf = DecisionTreeClassifier(
        max_depth=max_depth,
        min_samples_leaf=min_samples_leaf,
        random_state=random_state,
    )
    clf.fit(X_train, y_train)

    train_acc = accuracy_score(y_train, clf.predict(X_train))
    val_acc = accuracy_score(y_val, clf.predict(X_val))
    train_f1 = f1_score(y_train, clf.predict(X_train), zero_division=0)
    val_f1 = f1_score(y_val, clf.predict(X_val), zero_division=0)

    importances = {
        feat: float(imp)
        for feat, imp in zip(feature_names, clf.feature_importances_)
    }

    paths = _extract_paths(clf, feature_names)
    pass_paths = [p for p in paths if p["predicted_class"] == 1]
    fail_paths = [p for p in paths if p["predicted_class"] == 0]

    candidates = []

    if pass_paths:
        pass_dnf = _merge_pass_rules_to_dnf(pass_paths)
        total_support = sum(p["n_samples"] for p in pass_paths)
        avg_confidence = (
            sum(p["confidence"] * p["n_samples"] for p in pass_paths) / total_support
            if total_support > 0 else 0.0
        )
        total_complexity = sum(len(p["conditions"]) for p in pass_paths)

        candidates.append(CandidateRule(
            rule_id=f"{tree_id_prefix}_d{max_depth or 'X'}_pass",
            rule_text=pass_dnf,
            rule_type="pass",
            train_accuracy=train_acc,
            val_accuracy=val_acc,
            train_f1=train_f1,
            val_f1=val_f1,
            complexity=total_complexity,
            support=total_support,
            confidence=avg_confidence,
            source_model="decision_tree_dnf",
            feature_importances=importances,
        ))

    if fail_paths:
        fail_dnf = _merge_fail_rules_to_dnf(fail_paths)
        total_support = sum(p["n_samples"] for p in fail_paths)
        avg_confidence = (
            sum(p["confidence"] * p["n_samples"] for p in fail_paths) / total_support
            if total_support > 0 else 0.0
        )
        total_complexity = sum(len(p["conditions"]) for p in fail_paths)

        candidates.append(CandidateRule(
            rule_id=f"{tree_id_prefix}_d{max_depth or 'X'}_fail",
            rule_text=fail_dnf,
            rule_type="fail",
            train_accuracy=train_acc,
            val_accuracy=val_acc,
            train_f1=train_f1,
            val_f1=val_f1,
            complexity=total_complexity,
            support=total_support,
            confidence=avg_confidence,
            source_model="decision_tree_dnf",
            feature_importances=importances,
        ))

    return candidates, clf


def sweep_depths(
    dataset: SimulationDataset,
    depths: Optional[List[Optional[int]]] = None,
    min_samples_leaf: int = 5,
    random_state: int = 42,
    test_size: float = 0.2,
) -> List[CandidateRule]:
    """Generate candidate rules across multiple tree depths.

    Produces both individual path rules and merged DNF rules per depth.

    Args:
        dataset: SimulationDataset to learn from.
        depths: List of max_depth values to try. Defaults to [2, 3, 4, 5, None].
        min_samples_leaf: Minimum samples per leaf.
        random_state: Random seed.
        test_size: Validation split.

    Returns:
        List of all CandidateRule objects across all depths.
    """
    if depths is None:
        depths = [2, 3, 4, 5, None]

    all_candidates = []
    for depth in depths:
        # Individual path rules
        rules, _ = extract_rules_from_tree(
            dataset,
            max_depth=depth,
            min_samples_leaf=min_samples_leaf,
            random_state=random_state,
            test_size=test_size,
            tree_id_prefix="DT",
        )
        all_candidates.extend(rules)

        # Merged DNF rules
        dnf_rules, _ = extract_dnf_rules(
            dataset,
            max_depth=depth,
            min_samples_leaf=min_samples_leaf,
            random_state=random_state,
            test_size=test_size,
            tree_id_prefix="DT_DNF",
        )
        all_candidates.extend(dnf_rules)

    return all_candidates
