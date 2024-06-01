"""Unit tests for classifier/regressor input output."""

__author__ = ["mloning", "TonyBagnall", "fkiraly"]


import numpy as np
import pandas as pd
import pytest

from sktime.classification.tests._expected_outputs import (
    basic_motions_proba,
    unit_test_proba,
)
from sktime.datasets import load_basic_motions, load_unit_test
from sktime.datatypes import check_is_scitype
from sktime.tests.test_all_estimators import BaseFixtureGenerator, QuickTester
from sktime.utils._testing.estimator_checks import _assert_array_almost_equal
from sktime.utils._testing.panel import make_classification_problem
from sktime.utils._testing.scenarios_classification import (
    ClassifierFitPredictMultivariate,
)
from sktime.utils.validation._dependencies import _check_soft_dependencies


class ClassifierFixtureGenerator(BaseFixtureGenerator):
    """Fixture generator for classifier tests.

    Fixtures parameterized
    ----------------------
    estimator_class: estimator inheriting from BaseObject
        ranges over estimator classes not excluded by EXCLUDE_ESTIMATORS, EXCLUDED_TESTS
    estimator_instance: instance of estimator inheriting from BaseObject
        ranges over estimator classes not excluded by EXCLUDE_ESTIMATORS, EXCLUDED_TESTS
        instances are generated by create_test_instance class method
    scenario: instance of TestScenario
        ranges over all scenarios returned by retrieve_scenarios
    """

    # note: this should be separate from TestAllClassifiers
    #   additional fixtures, parameters, etc should be added here
    #   Classifiers should contain the tests only

    estimator_type_filter = "classifier"


class TestAllClassifiers(ClassifierFixtureGenerator, QuickTester):
    """Module level tests for all sktime classifiers."""

    def test_multivariate_input_exception(self, estimator_instance):
        """Test univariate classifiers raise exception on multivariate X."""
        # check if multivariate input raises error for univariate classifiers

        # if handles multivariate, no error is to be raised
        #   that classifier works on multivariate data is tested in test_all_estimators
        if estimator_instance.get_tag("capability:multivariate"):
            return None

        error_msg = "multivariate series"

        scenario = ClassifierFitPredictMultivariate()

        # check if estimator raises appropriate error message
        #   composites will raise a warning, non-composites an exception
        if estimator_instance.is_composite():
            with pytest.warns(UserWarning, match=error_msg):
                scenario.run(estimator_instance, method_sequence=["fit"])
        else:
            with pytest.raises(ValueError, match=error_msg):
                scenario.run(estimator_instance, method_sequence=["fit"])

    def test_classifier_output(self, estimator_instance, scenario):
        """Test classifier outputs the correct data types and values.

        Test predict produces a np.array or pd.Series with only values seen in the train
        data, and that predict_proba probability estimates add up to one.
        """
        n_classes = scenario.get_tag("n_classes")
        X_new = scenario.args["predict"]["X"]
        y_train = scenario.args["fit"]["y"]
        # we use check_is_scitype to get the number instances in X_new
        #   this is more robust against different scitypes in X_new
        _, _, X_new_metadata = check_is_scitype(X_new, "Panel", return_metadata=True)
        X_new_instances = X_new_metadata["n_instances"]

        # run fit and predict
        y_pred = scenario.run(estimator_instance, method_sequence=["fit", "predict"])

        # check predict
        assert isinstance(y_pred, np.ndarray)
        assert y_pred.shape == (X_new_instances,)
        assert np.all(np.isin(np.unique(y_pred), np.unique(y_train)))

        # check predict proba (all classifiers have predict_proba by default)
        y_proba = scenario.run(estimator_instance, method_sequence=["predict_proba"])
        assert isinstance(y_proba, np.ndarray)
        assert y_proba.shape == (X_new_instances, n_classes)
        np.testing.assert_almost_equal(y_proba.sum(axis=1), 1, decimal=4)

        if estimator_instance.get_tag("capability:train_estimate"):
            if not hasattr(estimator_instance, "_get_train_probs"):
                raise ValueError(
                    "Classifier capability:train_estimate tag is set to "
                    "true, but no _get_train_probs method is present."
                )

            X_train = scenario.args["fit"]["X"]
            _, _, X_train_metadata = check_is_scitype(
                X_train, "Panel", return_metadata=["n_instances"]
            )
            X_train_len = X_train_metadata["n_instances"]

            # temp hack until _get_train_probs is implemented for all mtypes
            if hasattr(X_train_len, "index"):
                if isinstance(X_train_len.index, pd.MultiIndex):
                    return None

            train_proba = estimator_instance._get_train_probs(X_train, y_train)

            assert isinstance(train_proba, np.ndarray)
            assert train_proba.shape == (X_train_len, n_classes)
            np.testing.assert_almost_equal(train_proba.sum(axis=1), 1, decimal=4)

    def test_classifier_on_unit_test_data(self, estimator_class):
        """Test classifier on unit test data."""
        # we only use the first estimator instance for testing
        classname = estimator_class.__name__

        # if numba is not installed, some estimators may still try to construct
        # numba dependenct estimators in results_comparison
        # if that is the case, we skip the test
        if classname in unit_test_proba.keys():
            parameter_set = "results_comparison"
        else:
            parameter_set = "default"
        try:
            # we only use the first estimator instance for testing
            estimator_instance = estimator_class.create_test_instance(
                parameter_set=parameter_set
            )
        except ModuleNotFoundError as e:
            if not _check_soft_dependencies("numba", severity="none"):
                return None
            else:
                raise e

        # set random seed if possible
        if "random_state" in estimator_instance.get_params().keys():
            estimator_instance.set_params(random_state=0)

        # load unit test data
        X_train, y_train = load_unit_test(split="train")
        X_test, _ = load_unit_test(split="test")
        indices = np.random.RandomState(0).choice(len(y_train), 10, replace=False)

        # train classifier and predict probas
        estimator_instance.fit(X_train, y_train)

        y_pred = estimator_instance.predict(X_test.iloc[indices])
        assert y_pred.dtype == y_train.dtype
        assert set(y_train).issuperset(set(y_pred))

        y_proba = estimator_instance.predict_proba(X_test.iloc[indices])

        # retrieve expected predict_proba output, and skip test if not available
        if classname in unit_test_proba.keys():
            expected_probas = unit_test_proba[classname]
            # assert probabilities are the same
            _assert_array_almost_equal(y_proba, expected_probas, decimal=2)

    def test_classifier_on_basic_motions(self, estimator_class):
        """Test classifier on basic motions data."""
        # we only use the first estimator instance for testing
        classname = estimator_class.__name__

        # retrieve expected predict_proba output, and skip test if not available
        if classname in basic_motions_proba.keys():
            expected_probas = basic_motions_proba[classname]
        else:
            # skip test if no expected probas are registered
            return None

        # if numba is not installed, some estimators may still try to construct
        # numba dependenct estimators in results_eomparison
        # if that is the case, we skip the test
        try:
            # we only use the first estimator instance for testing
            estimator_instance = estimator_class.create_test_instance(
                parameter_set="results_comparison"
            )
        except ModuleNotFoundError as e:
            if not _check_soft_dependencies("numba", severity="none"):
                return None
            else:
                raise e

        # set random seed if possible
        if "random_state" in estimator_instance.get_params().keys():
            estimator_instance.set_params(random_state=0)

        # load unit test data
        X_train, y_train = load_basic_motions(split="train")
        X_test, _ = load_basic_motions(split="test")
        indices = np.random.RandomState(4).choice(len(y_train), 10, replace=False)

        # train classifier and predict probas
        estimator_instance.fit(X_train.iloc[indices], y_train[indices])
        y_proba = estimator_instance.predict_proba(X_test.iloc[indices])

        # assert probabilities are the same
        _assert_array_almost_equal(y_proba, expected_probas, decimal=2)

    def test_handles_single_class(self, estimator_instance):
        """Test that estimator handles fit when only single class label is seen.

        This is important for compatibility with ensembles that sub-sample, as sub-
        sampling stochastically produces training sets with single class label.
        """
        X, y = make_classification_problem()
        y[:] = 42

        error_msg = "single label"

        with pytest.warns(UserWarning, match=error_msg):
            estimator_instance.fit(X, y)

    def test_multioutput(self, estimator_instance):
        """Test multioutput classification for all classifiers.

        All classifiers should follow the same interface,
        those that do not genuinely should vectorize/broadcast over y.
        """
        n_instances = 20
        X, y = make_classification_problem(n_instances=n_instances)
        y_mult = pd.DataFrame({"a": y, "b": y})

        estimator_instance.fit(X, y_mult)
        y_pred = estimator_instance.predict(X)

        assert isinstance(y_pred, pd.DataFrame)
        assert y_pred.shape == y_mult.shape

        # the estimator vectorizes iff it does not have the multioutput capability
        vectorized = not estimator_instance.get_tag("capability:multioutput")
        if vectorized:
            assert hasattr(estimator_instance, "classifiers_")
            assert isinstance(estimator_instance.classifiers_, pd.DataFrame)
            assert estimator_instance.classifiers_.shape == (1, 2)
