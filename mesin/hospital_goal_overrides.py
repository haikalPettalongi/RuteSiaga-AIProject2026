"""Apply documented hospital road-access goals without changing road geometry."""
import json
from pathlib import Path
BASE=Path(__file__).resolve().parent

def apply_goal_overrides(graph):
 path=BASE/'network_diy_akses_awal/hospital_goal_overrides.json'
 if not path.exists():return []
 overrides=json.loads(path.read_text(encoding='utf-8'))
 for item in overrides:
  n=item['road_node'];name=item['name']
  if n not in graph['nodes']:raise ValueError('Goal override node absent from road graph')
  if not any(e['v']==n for e in graph['edges']):raise ValueError('Goal override has no incoming edge')
  if n not in graph['goals']:graph['goals'].append(n)
  names=graph['goal_hospitals'].setdefault(n,[])
  if name not in names:names.append(name)
 graph['hospital_goal_overrides']=overrides
 return overrides
