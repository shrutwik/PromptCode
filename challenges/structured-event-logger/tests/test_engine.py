"""Candidate-visible behavioral fixtures; independent from server grading probes."""

def test_threshold_inclusive():
    from contracts import enabled
    result=enabled('INFO','INFO')
    assert result == True

def test_disabled_level():
    from engine import Logger
    rows=[];l=Logger('INFO',[rows.append],lambda:100);result=[l.emit('DEBUG','hello'),rows]
    assert result == [[], []]

def test_record():
    from engine import Logger
    rows=[];l=Logger('INFO',[rows.append],lambda:100);l.emit('INFO','hello',{'id':1});result=rows
    assert result == [{'level': 'INFO', 'message': 'hello', 'timestamp': 100, 'context': {'id': 1}}]

def test_sink_failure():
    from engine import Logger
    rows=[]
    def bad(_):raise RuntimeError('sink')
    l=Logger('DEBUG',[bad,rows.append],lambda:1);result=[l.emit('INFO','x'),len(rows)]
    assert result == [[0], 1]

def test_copied_context():
    from engine import Logger
    rows=[];ctx={'nested':[1]};Logger('INFO',[rows.append],lambda:0).emit('INFO','x',ctx);ctx['nested'].append(2);result=rows[0]['context']
    assert result == {'nested': [1]}

def test_reconfigure():
    from engine import Logger
    rows=[];l=Logger('ERROR',[rows.append],lambda:0);l.configure('DEBUG',[rows.append]);l.emit('INFO','x');result=len(rows)
    assert result == 1

def test_invalid_config_preserves():
    from engine import Logger
    rows=[];l=Logger('INFO',[rows.append],lambda:0)
    try:l.configure('UNKNOWN',[])
    except ValueError:pass
    l.emit('INFO','x');result=len(rows)
    assert result == 1

def test_json_escaping():
    from contracts import format_json
    import json
    record={'message':'line\n"quote','context':{'x':1}};result=json.loads(format_json(record))==record
    assert result == True


def test_part_three_pressure_case():
    from engine import Logger
    records=[];ticks=[]
    def clock():ticks.append(1);return 44
    l=Logger('INFO',[records.append],clock)
    try:l.configure('DEBUG',[None])
    except ValueError:pass
    else:raise RuntimeError('accepted invalid config')
    l.emit('DEBUG','hidden');failures=l.emit('WARN','visible');result=[len(ticks),[r['level'] for r in records],[r['timestamp'] for r in records],failures]
    assert result == [1, ['WARN'], [44], []]
