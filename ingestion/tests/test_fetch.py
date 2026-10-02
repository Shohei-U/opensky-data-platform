from opensky_ingest.fetch import OKINAWA, STATE_FIELDS, state_to_record

SAMPLE_STATE = [
    "8699a1",
    "JAL915  ",
    "Japan",
    1758850000,
    1758850001,
    127.65,
    26.2,
    3048.0,
    False,
    180.5,
    210.0,
    -5.2,
    None,
    3100.0,
    "1234",
    False,
    0,
    4,
]


def test_all_fields_mapped():
    r = state_to_record(SAMPLE_STATE, 1758850005, "2026-09-26T03:00:05+00:00")
    assert set(STATE_FIELDS) <= r.keys()
    assert r["icao24"] == "8699a1"
    assert r["latitude"] == 26.2
    assert r["category"] == 4
    assert r["api_time"] == 1758850005


def test_callsign_is_stripped_and_blank_becomes_none():
    assert state_to_record(SAMPLE_STATE, None, "t")["callsign"] == "JAL915"
    blank = ["abc123", "        "] + SAMPLE_STATE[2:]
    assert state_to_record(blank, None, "t")["callsign"] is None


def test_non_extended_response_has_null_category():
    r = state_to_record(SAMPLE_STATE[:17], None, "t")
    assert r["category"] is None
    assert r["position_source"] == 0


def test_okinawa_bbox_costs_one_credit():
    # <25 sq deg = 1 credit per request
    assert OKINAWA.area() < 25
