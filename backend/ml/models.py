"""Initial Phase 4 candidates, selected without any test-set results."""
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier

RANDOM_STATE = 42


def decision_tree():
    # Bound depth and avoid leaves based on individual observations.
    return DecisionTreeClassifier(criterion='gini', splitter='best', max_depth=16,
        min_samples_split=10, min_samples_leaf=5, max_features=None,
        class_weight=None, random_state=RANDOM_STATE)


def random_forest():
    # Two workers deliberately avoid exhausting this development machine.
    return RandomForestClassifier(n_estimators=100, criterion='gini', max_depth=20,
        min_samples_split=10, min_samples_leaf=2, max_features='sqrt',
        bootstrap=True, oob_score=False, class_weight=None,
        random_state=RANDOM_STATE, n_jobs=2)
