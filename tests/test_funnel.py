import pytest

from hireburn._io import load
from hireburn.funnel import disclosure, labels, metrics


def test_funnel_example(example):
    rep = metrics.analyse(load(example / "funnel.csv"))
    assert rep.show_up_rate == pytest.approx(90 / 110)
    assert rep.completion_rate == pytest.approx(40 / 60)
    assert rep.unaccounted_bookings == 5
    assert rep.biggest_loss == {"stage": "screened", "lost": 1800}
    main = [s for s in rep.stages if s["kind"] == "main"]
    assert [s["stage"] for s in main][-1] == "working_day_30"
    assert "show-up rate" in metrics.render(rep)


def test_funnel_errors():
    with pytest.raises(ValueError):
        metrics.analyse([{"stage": "a", "count": "x"}])
    with pytest.raises(ValueError):
        metrics.analyse([{"stage": "a", "count": 1, "parent": "missing"}])
    with pytest.raises(ValueError):
        metrics.analyse([{"stage": "a", "count": 1, "role": "weird"}])


def test_funnel_name_fallback():
    rep = metrics.analyse([{"stage": "booked", "count": 10}, {"stage": "held", "count": 6},
                           {"stage": "no_show", "count": 4, "parent": "booked"}])
    assert rep.show_up_rate == pytest.approx(0.6)


def test_fisher_known_values():
    # classic tea-tasting table: p = 0.4857 two-sided
    assert labels.fisher_exact(3, 1, 1, 3) == pytest.approx(0.4857, abs=1e-3)
    assert labels.fisher_exact(0, 0, 0, 0) == 1.0
    assert labels.fisher_exact(5, 0, 0, 5) == pytest.approx(0.00794, abs=1e-4)


def test_labels_example(example):
    res = labels.analyse(load(example / "candidates.csv"), day=30, snapshot=60)
    g = {x["group"]: x for x in res["groups"]}
    assert g["HIRE"]["candidates"] == 10 and g["HIRE"]["working"] == 4
    assert g["MAYBE"]["working"] == 5 and g["NO"]["working"] == 0
    assert res["fisher_hire_vs_maybe"]["among_all"] == pytest.approx(1.0)
    assert res["lag"]["n"] == 15
    assert "not a measurement" in res["caveat"]


def test_labels_iso_dates():
    rows = [{"id": "a", "entered": "2026-01-01", "first_work": "2026-01-08", "ai_label": "HIRE", "working_day_n": "yes"}]
    res = labels.analyse(rows, day=30)
    assert res["lag"]["median_days"] == 7


def test_labels_rejects_unknown_label():
    with pytest.raises(ValueError):
        labels.analyse([{"id": "a", "ai_label": "GREAT"}], day=30)


def test_disclosure_defaults_to_no():
    res = disclosure.evaluate({})
    assert res["counts"]["no"] == len(disclosure.REQUIREMENTS)


def test_disclosure_page_downgrades_missing_marker():
    res = disclosure.evaluate({"answers": {"consent": "yes"}}, page_html="<html></html>")
    item = next(i for i in res["items"] if i["id"] == "consent")
    assert item["status"] == "partly" and "MISSING" in item["note"]


def test_disclosure_bool_from_yaml():
    res = disclosure.evaluate({"answers": {"consent": True, "bias_audit": False}})
    st = {i["id"]: i["status"] for i in res["items"]}
    assert st["consent"] == "yes" and st["bias_audit"] == "no"
    with pytest.raises(ValueError):
        disclosure.evaluate({"answers": {"consent": "maybe"}})
