import json,time,server
xy=server.forward(110.376947373952,-7.773595801763427)
for radius,overview in [(1800,False),(12000,True)]:
 t=time.perf_counter();r=server.road_map(xy,radius,overview)
 xs=[p[0] for road in r['roads'] for p in [road['a'],road['b']]]
 ys=[p[1] for road in r['roads'] for p in [road['a'],road['b']]]
 print(radius,overview,len(r['roads']),round(max(xs)-min(xs)),round(max(ys)-min(ys)),round(time.perf_counter()-t,2),flush=True)
 assert max(xs)-min(xs)>radius*1.8
 assert max(ys)-min(ys)>radius*1.8
