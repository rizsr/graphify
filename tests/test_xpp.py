"""Tests for X++ / D365 F&O XML metadata extractor."""
from __future__ import annotations
from pathlib import Path
import pytest
from graphify.extract import extract_xpp
from graphify.detect import is_xpp_file, XPP_ARTIFACT_TAGS

FIXTURES = Path(__file__).parent / "fixtures" / "xpp"


def _ids(r):
    return {n["id"] for n in r["nodes"]}


def _labels(r):
    return [n["label"] for n in r["nodes"]]


def _edges_by_rel(r, relation):
    return [(e["source"], e["target"]) for e in r["edges"] if e["relation"] == relation]


def _relations(r):
    return {e["relation"] for e in r["edges"]}


# ── is_xpp_file detection ─────────────────────────────────────────────────────

def test_is_xpp_file_true_for_axclass():
    assert is_xpp_file(FIXTURES / "SampleClass.xml") is True

def test_is_xpp_file_true_for_axtable():
    assert is_xpp_file(FIXTURES / "SampleTable.xml") is True

def test_is_xpp_file_true_for_axenum():
    assert is_xpp_file(FIXTURES / "SampleEnum.xml") is True

def test_is_xpp_file_false_for_non_xpp():
    assert is_xpp_file(FIXTURES / "NonXppFile.xml") is False

def test_is_xpp_file_false_for_missing():
    assert is_xpp_file(FIXTURES / "does_not_exist.xml") is False


# ── AxClass ───────────────────────────────────────────────────────────────────

def test_axclass_no_error():
    r = extract_xpp(FIXTURES / "SampleClass.xml")
    assert "error" not in r

def test_axclass_class_node():
    r = extract_xpp(FIXTURES / "SampleClass.xml")
    labels = _labels(r)
    assert any("SampleOrderProcessor" in l for l in labels)

def test_axclass_method_nodes():
    r = extract_xpp(FIXTURES / "SampleClass.xml")
    labels = _labels(r)
    assert any("processOrder" in l for l in labels)
    assert any("createInstance" in l for l in labels)

def test_axclass_defines_method_edges():
    r = extract_xpp(FIXTURES / "SampleClass.xml")
    assert "defines_method" in _relations(r)

def test_axclass_extends_edge():
    r = extract_xpp(FIXTURES / "SampleClass.xml")
    ext_edges = _edges_by_rel(r, "extends")
    targets = [t for _, t in ext_edges]
    assert any("samplebaseprocessor" in t.lower() for t in targets)

def test_axclass_static_call_edges():
    r = extract_xpp(FIXTURES / "SampleClass.xml")
    calls = _edges_by_rel(r, "calls")
    call_targets = [t for _, t in calls]
    # SampleValidator:: and SampleLogger:: should be extracted
    assert any("SampleValidator" in t or "samplevalidator" in t.lower() for t in call_targets)
    assert any("SampleLogger" in t or "samplelogger" in t.lower() for t in call_targets)

def test_axclass_table_str_edge():
    r = extract_xpp(FIXTURES / "SampleClass.xml")
    table_edges = _edges_by_rel(r, "uses_table")
    targets = [t for _, t in table_edges]
    assert any("SalesTable" in t or "salestable" in t.lower() for t in targets)

def test_axclass_field_str_edge():
    r = extract_xpp(FIXTURES / "SampleClass.xml")
    field_edges = _edges_by_rel(r, "uses_field")
    assert len(field_edges) >= 1

def test_axclass_enum_ref_edge():
    r = extract_xpp(FIXTURES / "SampleClass.xml")
    enum_edges = _edges_by_rel(r, "references_enum")
    targets = [t for _, t in enum_edges]
    assert any("SampleStatus" in t or "samplestatus" in t.lower() for t in targets)

def test_axclass_new_instance_edge():
    r = extract_xpp(FIXTURES / "SampleClass.xml")
    new_edges = _edges_by_rel(r, "new_instance")
    targets = [t for _, t in new_edges]
    assert any("SampleOrderProcessor" in t or "sampleorderprocessor" in t.lower()
               for t in targets)

def test_axclass_no_dangling_define_method_edges():
    r = extract_xpp(FIXTURES / "SampleClass.xml")
    node_ids = _ids(r)
    for e in r["edges"]:
        if e["relation"] == "defines_method":
            assert e["source"] in node_ids
            assert e["target"] in node_ids


# ── AxTable ───────────────────────────────────────────────────────────────────

def test_axtable_no_error():
    r = extract_xpp(FIXTURES / "SampleTable.xml")
    assert "error" not in r

def test_axtable_table_node():
    r = extract_xpp(FIXTURES / "SampleTable.xml")
    assert any("SampleOrderTable" in l for l in _labels(r))

def test_axtable_field_nodes():
    r = extract_xpp(FIXTURES / "SampleTable.xml")
    labels = _labels(r)
    assert any("OrderId" in l for l in labels)
    assert any("TotalAmount" in l for l in labels)

def test_axtable_field_of_edges():
    r = extract_xpp(FIXTURES / "SampleTable.xml")
    assert "field_of" in _relations(r)

def test_axtable_edt_type_edges():
    r = extract_xpp(FIXTURES / "SampleTable.xml")
    assert "edt_type" in _relations(r)

def test_axtable_index_node():
    r = extract_xpp(FIXTURES / "SampleTable.xml")
    assert any("OrderIdx" in l for l in _labels(r))

def test_axtable_index_on_edge():
    r = extract_xpp(FIXTURES / "SampleTable.xml")
    assert "index_on" in _relations(r)

def test_axtable_relation_to_edge():
    r = extract_xpp(FIXTURES / "SampleTable.xml")
    rel_edges = _edges_by_rel(r, "relation_to")
    targets = [t for _, t in rel_edges]
    assert any("SalesTable" in t or "salestable" in t.lower() for t in targets)


# ── AxEnum ────────────────────────────────────────────────────────────────────

def test_axenum_no_error():
    r = extract_xpp(FIXTURES / "SampleEnum.xml")
    assert "error" not in r

def test_axenum_enum_node():
    r = extract_xpp(FIXTURES / "SampleEnum.xml")
    assert any("SampleStatus" in l for l in _labels(r))

def test_axenum_value_nodes():
    r = extract_xpp(FIXTURES / "SampleEnum.xml")
    labels = _labels(r)
    assert any("Pending" in l for l in labels)
    assert any("Processed" in l for l in labels)

def test_axenum_value_of_edges():
    r = extract_xpp(FIXTURES / "SampleEnum.xml")
    val_edges = _edges_by_rel(r, "value_of")
    assert len(val_edges) == 3  # None, Pending, Processed


# ── AxQuery ───────────────────────────────────────────────────────────────────

def test_axquery_no_error():
    r = extract_xpp(FIXTURES / "SampleQuery.xml")
    assert "error" not in r

def test_axquery_query_node():
    r = extract_xpp(FIXTURES / "SampleQuery.xml")
    assert any("SampleOrderQuery" in l for l in _labels(r))

def test_axquery_data_source_edges():
    r = extract_xpp(FIXTURES / "SampleQuery.xml")
    ds_edges = _edges_by_rel(r, "data_source")
    targets = [t for _, t in ds_edges]
    assert any("SampleOrderTable" in t or "sampleordertable" in t.lower() for t in targets)
    assert any("SalesTable" in t or "salestable" in t.lower() for t in targets)


# ── AxSecurityDuty ────────────────────────────────────────────────────────────

def test_axduty_no_error():
    r = extract_xpp(FIXTURES / "SampleDuty.xml")
    assert "error" not in r

def test_axduty_node():
    r = extract_xpp(FIXTURES / "SampleDuty.xml")
    assert any("SampleOrderDuty" in l for l in _labels(r))

def test_axduty_includes_privilege_edges():
    r = extract_xpp(FIXTURES / "SampleDuty.xml")
    priv_edges = _edges_by_rel(r, "includes_privilege")
    assert len(priv_edges) == 2


# ── AxSecurityRole ────────────────────────────────────────────────────────────

def test_axrole_no_error():
    r = extract_xpp(FIXTURES / "SampleRole.xml")
    assert "error" not in r

def test_axrole_node():
    r = extract_xpp(FIXTURES / "SampleRole.xml")
    assert any("SampleOrderRole" in l for l in _labels(r))

def test_axrole_has_duty_edge():
    r = extract_xpp(FIXTURES / "SampleRole.xml")
    duty_edges = _edges_by_rel(r, "has_duty")
    targets = [t for _, t in duty_edges]
    assert any("SampleOrderDuty" in t or "sampleorderduty" in t.lower() for t in targets)


# ── AxAggregateMeasurement ────────────────────────────────────────────────────

def test_axmeasurement_no_error():
    r = extract_xpp(FIXTURES / "SampleMeasurement.xml")
    assert "error" not in r

def test_axmeasurement_node():
    r = extract_xpp(FIXTURES / "SampleMeasurement.xml")
    assert any("SampleSalesAnalysis" in l for l in _labels(r))

def test_axmeasurement_measure_group_node():
    r = extract_xpp(FIXTURES / "SampleMeasurement.xml")
    assert any("SalesLines" in l for l in _labels(r))

def test_axmeasurement_uses_table_edge():
    r = extract_xpp(FIXTURES / "SampleMeasurement.xml")
    tbl_edges = _edges_by_rel(r, "uses_table")
    targets = [t for _, t in tbl_edges]
    assert any("SampleOrderTable" in t or "sampleordertable" in t.lower() for t in targets)

def test_axmeasurement_has_dimension_edge():
    r = extract_xpp(FIXTURES / "SampleMeasurement.xml")
    assert "has_dimension" in _relations(r)


# ── AxTableExtension ──────────────────────────────────────────────────────────

def test_axtableext_no_error():
    r = extract_xpp(FIXTURES / "SampleTableExtension.xml")
    assert "error" not in r

def test_axtableext_extends_base_table():
    r = extract_xpp(FIXTURES / "SampleTableExtension.xml")
    ext_edges = _edges_by_rel(r, "extends")
    targets = [t for _, t in ext_edges]
    assert any("SampleOrderTable" in t or "sampleordertable" in t.lower() for t in targets)

def test_axtableext_name_parsing():
    r = extract_xpp(FIXTURES / "SampleTableExtension.xml")
    # Extension node should exist with the full name
    labels = _labels(r)
    assert any("SampleTableExtension" in l or "SampleOrderTable" in l for l in labels)

def test_axtableext_field_added():
    r = extract_xpp(FIXTURES / "SampleTableExtension.xml")
    assert any("ExtraField" in l for l in _labels(r))

def test_axtableext_relation_added():
    r = extract_xpp(FIXTURES / "SampleTableExtension.xml")
    rel_edges = _edges_by_rel(r, "relation_to")
    targets = [t for _, t in rel_edges]
    assert any("AnotherTable" in t or "anothertable" in t.lower() for t in targets)


# ── Non-XPP XML ───────────────────────────────────────────────────────────────

def test_non_xpp_xml_returns_empty():
    # NonXppFile.xml has a <NotAnAxFile> root — extract_xpp should return empty gracefully
    r = extract_xpp(FIXTURES / "NonXppFile.xml")
    assert "error" not in r
    assert r["nodes"] == []
    assert r["edges"] == []
