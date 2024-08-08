from re import M
import pytest
import tempfile

from numpy.testing import assert_array_equal
from numpy.testing import assert_equal
import numpy as np

from ProcessOptimizer import gp_minimize
from ProcessOptimizer import load
from ProcessOptimizer import dump
from ProcessOptimizer import expected_minimum
from ProcessOptimizer.model_systems.benchmarks import bench1
from ProcessOptimizer.model_systems.benchmarks import bench3
from ProcessOptimizer.learning import (
    cook_estimator,
    ExtraTreesRegressor,
    has_gradients,
    use_named_args,
)
from ProcessOptimizer import Optimizer
from ProcessOptimizer import Categorical, Integer, Space, Real
from ProcessOptimizer.utils import (
    point_asdict,
    point_aslist,
    dimensions_aslist,
)
from ProcessOptimizer.space import normalize_dimensions
from ProcessOptimizer.space.constraints import SumEquals


def check_optimization_results_equality(res_1, res_2):
    # Check if the results objects have the same keys
    assert_equal(sorted(res_1.keys()), sorted(res_2.keys()))
    # Shallow check of the main optimization results
    assert_array_equal(res_1.x, res_2.x)
    assert_array_equal(res_1.x_iters, res_2.x_iters)
    assert_array_equal(res_1.fun, res_2.fun)
    assert_array_equal(res_1.func_vals, res_2.func_vals)


@pytest.mark.fast_test
def test_dump_and_load():
    res = gp_minimize(
        bench3,
        [(-2.0, 2.0)],
        x0=[0.0],
        acq_func="LCB",
        n_calls=2,
        n_random_starts=1,
        random_state=1,
    )

    # Test normal dumping and loading
    with tempfile.TemporaryFile() as f:
        dump(res, f)
        f.seek(0)
        res_loaded = load(f)
    check_optimization_results_equality(res, res_loaded)
    assert "func" in res_loaded.specs["args"]

    # Test dumping without objective function
    with tempfile.TemporaryFile() as f:
        dump(res, f, store_objective=False)
        f.seek(0)
        res_loaded = load(f)
    check_optimization_results_equality(res, res_loaded)
    assert not ("func" in res_loaded.specs["args"])

    # Delete the objective function and dump the modified object
    del res.specs["args"]["func"]
    with tempfile.TemporaryFile() as f:
        dump(res, f, store_objective=False)
        f.seek(0)
        res_loaded = load(f)
    check_optimization_results_equality(res, res_loaded)
    assert not ("func" in res_loaded.specs["args"])


@pytest.mark.fast_test
def test_dump_and_load_optimizer():
    base_estimator = ExtraTreesRegressor(random_state=2)
    opt = Optimizer(
        [(-2.0, 2.0)], base_estimator, n_initial_points=2, acq_optimizer="sampling"
    )

    opt.run(bench1, n_iter=3)

    with tempfile.TemporaryFile() as f:
        dump(opt, f)
        f.seek(0)
        load(f)


@pytest.mark.fast_test
def test_create_result():
    opt = Optimizer(
        dimensions=[(-2, 2), ("A", "B")], base_estimator="GP", n_initial_points=1
    )
    x = [[-2, "A"], [-1, "A"], [0, "A"], [1, "A"], [2, "A"]]
    y = [2, 1, 0, 1, 2]
    result = opt.tell(x, y)
    # Test that all the desired properties appear in the result object
    assert hasattr(result, "x")
    assert hasattr(result, "fun")
    assert hasattr(result, "func_vals")
    assert hasattr(result, "x_iters")
    assert hasattr(result, "models")
    assert hasattr(result, "space")
    assert hasattr(result, "random_state")
    assert hasattr(result, "specs")
    assert hasattr(result, "constraints")


@pytest.mark.fast_test
def test_expected_minimum_min():
    res = gp_minimize(
        bench3,
        [(-2.0, 2.0)],
        x0=[0.0],
        noise=1e-8,
        n_calls=8,
        n_random_starts=3,
        random_state=1,
    )

    x_min, f_min = expected_minimum(res, random_state=1)
    x_min2, f_min2 = expected_minimum(res, random_state=1)

    assert f_min <= res.fun  # true since noise ~= 0.0
    assert x_min == x_min2
    assert f_min == f_min2


@pytest.mark.fast_test
def test_expected_minimum_max():
    res = gp_minimize(
        bench3,
        [(-2.0, 2.0)],
        x0=[0.0],
        noise=1e-8,
        n_calls=8,
        n_random_starts=3,
        random_state=1,
    )

    x_max, f_max = expected_minimum(res, random_state=1, minmax="max")
    x_max2, f_max2 = expected_minimum(res, random_state=1, minmax="max")

    assert f_max >= res.fun  # true since noise ~= 0.0
    assert x_max == x_max2
    assert f_max == f_max2


@pytest.mark.fast_test
def test_expected_minimum_minmax_argument():
    opt = Optimizer(
        dimensions=[(-2, 2), ("A", "B")], base_estimator="GP", n_initial_points=1
    )
    x = [[-2, "A"], [-1, "A"], [0, "A"], [1, "A"], [2, "A"]]
    y = [2, 1, 0, 1, 2]
    result = opt.tell(x, y)
    x_min, f_min = expected_minimum(
        result, n_random_starts=20, random_state=1, minmax="min"
    )
    x_max, f_max = expected_minimum(
        result, n_random_starts=20, random_state=1, minmax="max"
    )
    assert x_min != x_max
    assert f_min < f_max


@pytest.mark.fast_test
def test_expected_minimum_return_std():
    opt = Optimizer(
        dimensions=[(-2, 2), ("A", "B")], base_estimator="GP", n_initial_points=1
    )
    x = [[-2, "A"], [-1, "A"], [0, "A"], [1, "A"], [2, "A"]]
    y = [2, 1, 0, 1, 2]
    result = opt.tell(x, y)
    x_min, f_min = expected_minimum(
        result, n_random_starts=20, random_state=1, return_std=False, minmax="min"
    )
    assert len(x_min) == len(opt.space.dimensions)
    assert isinstance(f_min, float)

    x_min, f_min = expected_minimum(
        result, n_random_starts=20, random_state=1, return_std=True, minmax="min"
    )
    assert len(x_min) == len(opt.space.dimensions)
    assert isinstance(f_min, list)
    assert isinstance(f_min[0], float) and f_min[1] >= 0


@pytest.mark.fast_test
def test_expected_minimum_respects_constraints():
    dimensions = [(-3.0, 3.0), (-2.0, 2.0), (-3.0, 3.0), (0, 4)]
    opt = Optimizer(
        dimensions=dimensions,
        lhs=False,
        n_initial_points=3,
    )
    constraints = [SumEquals(dimensions=[0, 1, 2], value=2)]
    opt.set_constraints(constraints)
    x = opt.ask(3,strategy='cl_min')
    y = [1, 2, 0]
    result = opt.tell(x, y)
    x_min, _ = expected_minimum(result, random_state=1, return_std=False)
    assert np.isclose(sum(x_min[:3]), constraints[0].value)

    # Feed the optimizer a really good data-point that does not respect the constraints
    result = opt.tell([0, 0, 0, 0], -1)
    x_min, _ = expected_minimum(result, random_state=1, return_std=False)
    # Check that expected_minimum still doesn't violate constraints
    assert np.isclose(sum(x_min[:3]), constraints[0].value)

    # Check that removing the constraint and generating a new result allows you
    # to find an optimum outside the constraints
    opt.remove_constraints()
    result = opt.get_result()
    x_min, _ = expected_minimum(result, random_state=1, return_std=False)
    assert sum(x_min[:3]) != constraints[0].value


@pytest.mark.fast_test
def test_dict_list_space_representation():
    """
    Tests whether the conversion of the dictionary and list representation
    of a point from a search space works properly.
    """

    chef_space = {
        "Cooking time": (0, 1200),  # in minutes
        "Main ingredient": [
            "cheese",
            "cherimoya",
            "chicken",
            "chard",
            "chocolate",
            "chicory",
        ],
        "Secondary ingredient": ["love", "passion", "dedication"],
        "Cooking temperature": (-273.16, 10000.0),  # in Celsius
    }

    opt = Optimizer(dimensions=dimensions_aslist(chef_space))
    point = opt.ask()

    # check if the back transformed point and original one are equivalent
    assert_equal(point, point_aslist(chef_space, point_asdict(chef_space, point)))


@pytest.mark.fast_test
@pytest.mark.parametrize(
    "estimator, gradients",
    zip(["GP", "RF", "ET", "GBRT", "DUMMY"], [True, False, False, False, False]),
)
def test_has_gradients(estimator, gradients):
    space = Space([(-2.0, 2.0)])

    assert has_gradients(cook_estimator(estimator, space=space)) == gradients


@pytest.mark.fast_test
def test_categorical_gp_has_gradients():
    space = Space([("a", "b")])

    assert not has_gradients(cook_estimator("GP", space=space))


@pytest.mark.fast_test
def test_normalize_dimensions_all_categorical():
    dimensions = (["a", "b", "c"], ["1", "2", "3"])
    space = normalize_dimensions(dimensions)
    assert space.is_categorical


@pytest.mark.fast_test
def test_categoricals_mixed_types():
    domain = [[1, 2, 3, 4], ["a", "b", "c"], [True, False]]
    x = [1, "a", True]
    space = normalize_dimensions(domain)
    assert space.inverse_transform(space.transform([x])) == [x]


@pytest.mark.fast_test
@pytest.mark.parametrize(
    "dimensions, normalizations",
    [
        (((1, 3), (1.0, 3.0)), ("normalize", "normalize")),
        (((1, 3), ("a", "b", "c")), ("normalize", "onehot")),
    ],
)
def test_normalize_dimensions(dimensions, normalizations):
    space = normalize_dimensions(dimensions)
    for dimension, normalization in zip(space, normalizations):
        assert dimension.transform_ == normalization


@pytest.mark.fast_test
@pytest.mark.parametrize(
    "dimension, name",
    [
        (Real(1, 2, name="learning rate"), "learning rate"),
        (Integer(1, 100, name="no of trees"), "no of trees"),
        (Categorical(["red, blue"], name="colors"), "colors"),
    ],
)
def test_normalize_dimensions_name(dimension, name):
    space = normalize_dimensions([dimension])
    assert space.dimensions[0].name == name


@pytest.mark.fast_test
def test_use_named_args():
    """
    Test the function wrapper @use_named_args which is used
    for wrapping an objective function with named args so it
    can be called by the optimizers which only pass a single
    list as the arg.

    This test does not actually use the optimizers but merely
    simulates how they would call the function.
    """

    # Define the search-space dimensions. They must all have names!
    dim1 = Real(name="foo", low=0.0, high=1.0)
    dim2 = Real(name="bar", low=0.0, high=1.0)
    dim3 = Real(name="baz", low=0.0, high=1.0)

    # Gather the search-space dimensions in a list.
    dimensions = [dim1, dim2, dim3]

    # Parameters that will be passed to the objective function.
    default_parameters = [0.5, 0.6, 0.8]

    # Define the objective function with named arguments
    # and use this function-decorator to specify the search-space dimensions.
    @use_named_args(dimensions=dimensions)
    def func(foo, bar, baz):
        # Assert that all the named args are indeed correct.
        assert foo == default_parameters[0]
        assert bar == default_parameters[1]
        assert baz == default_parameters[2]

        # Return some objective value.
        return foo**2 + bar**4 + baz**8

    # Ensure the objective function can be called with a single
    # argument named x.
    res = func(x=default_parameters)
    assert isinstance(res, float)

    # Ensure the objective function can be called with a single
    # argument that is unnamed.
    res = func(default_parameters)
    assert isinstance(res, float)

    # Ensure the objective function can be called with a single
    # argument that is a numpy array named x.
    res = func(x=np.array(default_parameters))
    assert isinstance(res, float)

    # Ensure the objective function can be called with a single
    # argument that is an unnamed numpy array.
    res = func(np.array(default_parameters))
    assert isinstance(res, float)
