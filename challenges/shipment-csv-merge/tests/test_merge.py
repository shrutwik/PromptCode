from shipment_merge.parse import parse_csv
from shipment_merge.summarize import summarize
from shipment_merge.models import ShipmentEvent
from shipment_merge.merge import merge_events
DAY1 = """event_id,shipment_id,status,ts,quantity_delta
e1,s1,created,2024-01-01T10:00:00Z,1
e2,s1,picked,2024-01-01T15:00:00Z,0
"""
DAY2 = """event_id,shipment_id,status,ts,quantity_delta
e3,s1,shipped,2024-01-02T09:00:00Z,0
e4,s1,delivered,2024-01-02T18:00:00Z,0
"""
def test_basic_timeline_order_happy_path():
    assert summarize([parse_csv(DAY1), parse_csv(DAY2)])["timelines"]["s1"] == ["created", "picked", "shipped", "delivered"]
def test_quantity_single_batch():
    events = [ShipmentEvent("a","s2","created","2024-01-01T10:00:00Z",2), ShipmentEvent("b","s2","picked","2024-01-01T11:00:00Z",0)]
    assert summarize([events])["quantities"]["s2"] == 2
def test_duplicate_event_id_across_batches_not_double_counted():
    day1=[ShipmentEvent("e9","s1","created","2024-01-01T23:30:00Z",1)]
    day2=[ShipmentEvent("e9","s1","created","2024-01-01T23:30:00Z",1)]
    assert summarize([day1, day2])["quantities"]["s1"] == 1
def test_same_status_different_event_ids_kept_in_ts_order():
    events=[ShipmentEvent("e1","s1","picked","2024-01-01T10:00:00Z",0), ShipmentEvent("e2","s1","picked","2024-01-01T12:00:00Z",0)]
    assert [e.event_id for e in merge_events([events])] == ["e1","e2"]
