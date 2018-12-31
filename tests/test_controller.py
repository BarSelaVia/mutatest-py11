"""Tests for the controller module.
"""
import ast
import subprocess

from subprocess import CompletedProcess

import pytest

from mutatest.controller import (
    BaselineTestException,
    build_src_trees_and_targets,
    clean_trial,
    get_py_files,
    get_sample_space,
    run_mutation_trials,
)
from mutatest.maker import LocIndex


def test_get_py_files_flat(tmp_path):
    """Test the only .py files are grabbed in a basic pass."""
    test_files = [
        "first.py",
        "second.py",
        "third.py",
        "test_first.py",
        "test_second.py",
        "first.pyc",
        "first.pyo",
        "first.pyi",
    ]

    expected = {"first.py", "second.py", "third.py"}

    for tf in test_files:
        with open(tmp_path / tf, "w") as temp_py:
            temp_py.write("import this")

    results = get_py_files(tmp_path)
    assert set([r.name for r in results]) == expected


def test_get_py_files_recursive(tmp_path):
    """Ensure recursive glob search works for finding py files."""
    f = tmp_path / "folder"
    f.mkdir()

    test_files = [
        tmp_path / "first.py",
        tmp_path / "second.py",
        tmp_path / "test_first.py",
        tmp_path / "test_second.py",
        f / "third.py",
        f / "test_third.py",
    ]

    expected = {"first.py", "second.py", "third.py"}

    for tf in test_files:
        with open(tf, "w") as temp_py:
            temp_py.write("import this")

    results = get_py_files(tmp_path)
    assert set([i.name for i in results]) == expected


def test_get_py_files_single(binop_file):
    """Ensure a single file gets a list of one item with absolute path."""
    expected = binop_file.resolve()
    result = get_py_files(binop_file)

    assert len(result) == 1
    assert result[0] == expected


def test_get_py_files_filenotfound():
    """Files that do not exist raise FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        _ = get_py_files("somerandomlocation.py")


def test_clean_trial_exception(binop_file, monkeypatch):
    """Ensure clean trial raises a BaselineTestException on non-zero returncode"""

    def mock_subprocess_run(*args, **kwargs):
        return CompletedProcess(args="pytest", returncode=1)

    monkeypatch.setattr(subprocess, "run", mock_subprocess_run)

    with pytest.raises(BaselineTestException):
        clean_trial(binop_file.parent, ["pytest"])


def test_build_src_trees_and_targets(binop_file, binop_expected_locs):
    """Test source tree and target for the temporary binop python file."""
    src_trees, src_targets = build_src_trees_and_targets(binop_file.parent)

    # src_tress and _targets store by key to absolute path to the file
    expected_key = str(binop_file.resolve())

    assert isinstance(src_trees[expected_key], ast.Module)
    assert set(src_targets[expected_key]) == binop_expected_locs


def test_get_sample_space():
    """Sample space should flatten out a dictionary of multiple entries to tuple pairs."""
    mock_LocIdx = LocIndex(ast_class="BinOp", lineno=1, col_offset=2, op_type=ast.Add)

    mock_src_file = "source.py"
    mock_src_targets = {mock_src_file: [mock_LocIdx, mock_LocIdx, mock_LocIdx]}

    results = get_sample_space(mock_src_targets)

    assert len(results) == 3
    for s, l in results:
        assert s == mock_src_file
        assert l == mock_LocIdx


@pytest.mark.slow
@pytest.mark.parametrize(
    "bos, bod, exp_trials", [(False, False, 6), (True, True, 1), (False, True, 1)]
)
def test_run_mutation_trials_good_binop(bos, bod, exp_trials, single_binop_file_with_good_test):
    """Slow test to run detection trials on a simple mutation on a binop.

    Based on fixture, there is one Add operation, with 6 substitutions e.g.
    sub, div, mult, pow, mod, floordiv, therefore, 6 total trials are expected for a full run
    and 1 trial is expected when break on detected is used.

    Args:
        bos: break on survival
        bod: break on detection
        exp_trials: number of expected trials
        single_binop_file_with_good_test: fixture for single op with a good test
    """

    test_cmds = f"pytest {single_binop_file_with_good_test.test_file.resolve()}".split()

    results_summary = run_mutation_trials(
        single_binop_file_with_good_test.src_file.resolve(),
        test_cmds=test_cmds,
        break_on_survival=bos,
        break_on_detected=bod,
    )

    assert len(results_summary.results) == exp_trials

    # in all trials the status should be detected
    for mutant_trial in results_summary.results:
        assert mutant_trial.return_code == 1
        assert mutant_trial.status == "DETECTED"


@pytest.mark.slow
@pytest.mark.parametrize(
    "bos, bod, exp_trials", [(False, False, 6), (True, True, 1), (True, False, 1)]
)
def test_run_mutation_trials_bad_binop(bos, bod, exp_trials, single_binop_file_with_bad_test):
    """Slow test to run detection trials on a simple mutation on a binop.

    Based on fixture, there is one Add operation, with 6 substitutions e.g.
    sub, div, mult, pow, mod, floordiv, therefore, 6 total trials are expected for a full run
    and 1 trial is expected when break on detected is used.

    Args:
        bos: break on survival
        bod: break on detection
        exp_trials: number of expected trials
        single_binop_file_with_good_test: fixture for single op with a good test
    """

    test_cmds = f"pytest {single_binop_file_with_bad_test.test_file.resolve()}".split()

    results_summary = run_mutation_trials(
        single_binop_file_with_bad_test.src_file.resolve(),
        test_cmds=test_cmds,
        break_on_survival=bos,
        break_on_detected=bod,
    )

    assert len(results_summary.results) == exp_trials

    # in all trials the status should be survivors
    for mutant_trial in results_summary.results:
        assert mutant_trial.return_code == 0
        assert mutant_trial.status == "SURVIVED"
