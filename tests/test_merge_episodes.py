"""How re-treatment is collapsed into one hypoglycaemia episode.

Study 05 turns on this function. It reports how much carbohydrate a person takes per episode and
how often an episode happens, and both change if a run of re-treatments is counted as several
episodes or if two separate lows are merged into one. The boundary at exactly the gap is the case
worth pinning, since the comparison is a strict inequality and either direction looks equally
plausible from the call site.

The cases below were drafted by the local model and reviewed here. Each was then run against four
deliberately broken versions of the function, recorded in `test_merge_episodes_mutants`, because a
test that passes whatever the implementation does is not a test.
"""
import pytest

from examples.real_rescues import merge_episodes

EPISODE_GAP_MIN = 45.0


def _entry(t_ms, grams, reading):
    return {"t": t_ms, "grams": grams, "reading": reading}


def test_empty_list_returns_empty_list():
    result = merge_episodes([], EPISODE_GAP_MIN)
    assert result == [], "Expected an empty list for empty input"


def test_single_entry_returns_one_episode():
    entries = [_entry(0, 15.0, 80.0)]
    result = merge_episodes(entries, EPISODE_GAP_MIN)
    assert len(result) == 1, "Expected exactly one episode"
    assert result[0]["helpings"] == 1, "Expected helpings to be 1"
    assert result[0]["grams"] == 15.0, "Expected grams to be 15.0"


def test_two_entries_20_minutes_apart_merge():
    t0 = 0
    t1 = 20 * 60000
    entries = [
        _entry(t0, 10.0, 75.0),
        _entry(t1, 5.0, 80.0),
    ]
    result = merge_episodes(entries, EPISODE_GAP_MIN)
    assert len(result) == 1, "Expected entries 20 minutes apart to merge into one episode"
    assert result[0]["grams"] == 15.0, "Expected summed grams to be 15.0"
    assert result[0]["helpings"] == 2, "Expected helpings to be 2"


def test_two_entries_60_minutes_apart_stay_separate():
    t0 = 0
    t1 = 60 * 60000
    entries = [
        _entry(t0, 10.0, 75.0),
        _entry(t1, 5.0, 80.0),
    ]
    result = merge_episodes(entries, EPISODE_GAP_MIN)
    assert len(result) == 2, "Expected entries 60 minutes apart to remain separate"
    assert result[0]["grams"] == 10.0, "Expected first episode grams to be 10.0"
    assert result[1]["grams"] == 5.0, "Expected second episode grams to be 5.0"


def test_two_entries_exactly_45_minutes_apart_stay_separate():
    t0 = 0
    t1 = 45 * 60000
    entries = [
        _entry(t0, 10.0, 75.0),
        _entry(t1, 5.0, 80.0),
    ]
    result = merge_episodes(entries, EPISODE_GAP_MIN)
    assert len(result) == 2, "Expected entries exactly 45 minutes apart to remain separate (strictly less than)"
    assert result[0]["grams"] == 10.0, "Expected first episode grams to be 10.0"
    assert result[1]["grams"] == 5.0, "Expected second episode grams to be 5.0"


def test_three_entries_each_30_minutes_apart_merge_into_one():
    t0 = 0
    t1 = 30 * 60000
    t2 = 60 * 60000
    entries = [
        _entry(t0, 10.0, 75.0),
        _entry(t1, 5.0, 80.0),
        _entry(t2, 3.0, 85.0),
    ]
    result = merge_episodes(entries, EPISODE_GAP_MIN)
    assert len(result) == 1, "Expected three entries each 30 minutes apart to merge into one episode"
    assert result[0]["helpings"] == 3, "Expected helpings to be 3"
    assert result[0]["grams"] == 18.0, "Expected summed grams to be 18.0"


def test_episode_keeps_reading_of_first_entry():
    t0 = 0
    t1 = 20 * 60000
    entries = [
        _entry(t0, 10.0, 70.0),
        _entry(t1, 5.0, 90.0),
    ]
    result = merge_episodes(entries, EPISODE_GAP_MIN)
    assert len(result) == 1, "Expected entries to merge into one episode"
    assert result[0]["reading"] == 70.0, "Expected episode reading to be that of the first entry (70.0), not the last"


# ---------------------------------------------------------------------------
# The tests above pass against the implementation. That is not the same as their
# being able to fail, which is the failure mode generated tests have most often, so
# each broken variant below has to be caught by at least one of them.

def _mutant(entries, gap_min, cmp=None, from_start=False, last_reading=False,
            no_count=False):
    """`merge_episodes` with one decision deliberately wrong."""
    cmp = cmp or (lambda d, g: d < g)
    eps = []
    for e in entries:
        ref = None
        if eps:
            ref = eps[-1]["start"] if from_start else eps[-1]["end"]
        if ref is not None and cmp((e["t"] - ref) / 60000.0, gap_min):
            eps[-1]["grams"] += e["grams"]
            eps[-1]["end"] = e["t"]
            if last_reading:
                eps[-1]["reading"] = e["reading"]
            if not no_count:
                eps[-1]["helpings"] += 1
        else:
            eps.append({"grams": e["grams"], "reading": e["reading"],
                        "end": e["t"], "start": e["t"], "helpings": 1})
    return eps


MUTANTS = {
    "boundary merges": dict(cmp=lambda d, g: d <= g),
    "gap from the episode start": dict(from_start=True),
    "keeps the last reading": dict(last_reading=True),
    "helpings not counted": dict(no_count=True),
}

CASES = [
    ("empty", [], None),
    ("single", [{"t": 0, "grams": 15.0, "reading": 80.0}], None),
    ("20 min apart", [{"t": 0, "grams": 10.0, "reading": 75.0},
                      {"t": 20 * 60000, "grams": 5.0, "reading": 80.0}], None),
    ("60 min apart", [{"t": 0, "grams": 10.0, "reading": 75.0},
                      {"t": 60 * 60000, "grams": 5.0, "reading": 80.0}], None),
    ("exactly 45 min", [{"t": 0, "grams": 10.0, "reading": 75.0},
                        {"t": 45 * 60000, "grams": 5.0, "reading": 80.0}], None),
    ("three at 30 min", [{"t": 0, "grams": 10.0, "reading": 75.0},
                         {"t": 30 * 60000, "grams": 5.0, "reading": 80.0},
                         {"t": 60 * 60000, "grams": 3.0, "reading": 85.0}], None),
    ("first reading kept", [{"t": 0, "grams": 10.0, "reading": 70.0},
                            {"t": 20 * 60000, "grams": 5.0, "reading": 90.0}], None),
]


def _strip(eps):
    """Drop the bookkeeping key the mutant carries and the real function does not."""
    return [{k: v for k, v in e.items() if k != "start"} for e in eps]


@pytest.mark.parametrize("label", sorted(MUTANTS))
def test_every_mutant_is_caught_by_some_case(label):
    """A broken variant must differ from the real function on at least one case."""
    kwargs = MUTANTS[label]
    differs = [name for name, entries, _ in CASES
               if _strip(_mutant(entries, EPISODE_GAP_MIN, **kwargs))
               != merge_episodes(entries, EPISODE_GAP_MIN)]
    assert differs, (
        f"the {label!r} mutant produces identical output to the real function on every "
        f"case above, so nothing here would catch it")
