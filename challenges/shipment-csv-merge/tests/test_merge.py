from shipment_merge.parse import parse_csv
from shipment_merge.summarize import summarize
from shipment_merge.models import ShipmentEvent
from shipment_merge.merge import merge_events, total_quantity
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

def test_timestamp_ties_negative_deltas_and_duplicates():
    a = ShipmentEvent('a', 'ship', 'scan', '2026-01-01', 5)
    b = ShipmentEvent('b', 'ship', 'scan', '2026-01-01', -2)
    assert [e.event_id for e in merge_events([[b, a], [], [a, b, a]])] == ['a', 'b']
    assert total_quantity('ship') == 3

def test_next_merge_replaces_previous_totals():
    merge_events([[ShipmentEvent('old', 'old-ship', 'scan', '2026-01-01', 9)]])
    merge_events([[ShipmentEvent('new', 'new-ship', 'scan', '2026-01-02', 4)]])
    assert total_quantity('old-ship') == 0
    assert total_quantity('new-ship') == 4
    assert merge_events([]) == []
    assert total_quantity('new-ship') == 0

def test_repartitioning_files_preserves_results_and_input_batches():
    a = ShipmentEvent('one', 'ship', 'scan', '2026-01-01', 5)
    b = ShipmentEvent('two', 'ship', 'scan', '2026-01-02', -2)
    batches = [[b, a], [a]]
    first = [(e.event_id, e.quantity_delta) for e in merge_events(batches)]
    quantity = total_quantity('ship')
    second = [(e.event_id, e.quantity_delta) for e in merge_events([[a], [b], [a]])]
    assert first == second == [('one', 5), ('two', -2)]
    assert quantity == total_quantity('ship') == 3
    assert batches == [[b, a], [a]]

def test_part_three_pressure_case():
    from shipment_merge.models import ShipmentEvent
    from shipment_merge.merge import merge_events,total_quantity
    a=ShipmentEvent('a','one','scan','2026-01-01',8);b=ShipmentEvent('b','one','scan','2026-01-02',-2);c=ShipmentEvent('c','two','scan','2026-01-01',9)
    base=merge_events([[a,b]]);before=total_quantity('one');merged=merge_events([[c,a],[b,a]]);result=[[e.event_id for e in merged if e.shipment_id=='one'],before,total_quantity('one'),total_quantity('two')]
    assert result == [['a', 'b'], 6, 6, 9]
