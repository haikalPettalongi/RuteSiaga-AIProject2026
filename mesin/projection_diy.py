"""Pure-Python WGS84 <-> UTM 49S for this DIY project, no native library.
Transverse Mercator series: Snyder, USGS PP1395, pp. 60-64.
https://pubs.usgs.gov/publication/pp1395
Not a general replacement for pyproj. Only EPSG:4326/32749, always_xy=True.
"""
import math
from numbers import Real
A=6378137.0
F=1/298.257223563
E2=F*(2-F)
EP2=E2/(1-E2)
K=.9996
L0=math.radians(111)

def forward(lon,lat):
 if not (math.isfinite(lon) and math.isfinite(lat) and 108<=lon<=114 and -80<=lat<=0):
  raise ValueError('Koordinat di luar wilayah proyeksi UTM 49S (108–114 BT, belahan selatan).')
 p=math.radians(lat);l=math.radians(lon);s=math.sin(p);c=math.cos(p);tan=math.tan(p)
 n=A/math.sqrt(1-E2*s*s);t=tan*tan;cc=EP2*c*c;q=c*(l-L0)
 m=A*((1-E2/4-3*E2**2/64-5*E2**3/256)*p-(3*E2/8+3*E2**2/32+45*E2**3/1024)*math.sin(2*p)+(15*E2**2/256+45*E2**3/1024)*math.sin(4*p)-(35*E2**3/3072)*math.sin(6*p))
 x=500000+K*n*(q+(1-t+cc)*q**3/6+(5-18*t+t*t+72*cc-58*EP2)*q**5/120)
 y=10000000+K*(m+n*tan*(q*q/2+(5-t+9*cc+4*cc*cc)*q**4/24+(61-58*t+t*t+600*cc-330*EP2)*q**6/720))
 return x,y

def inverse(x,y):
 if not (math.isfinite(x) and math.isfinite(y)):raise ValueError('Koordinat tidak finite')
 m=(y-10000000)/K;mu=m/(A*(1-E2/4-3*E2**2/64-5*E2**3/256))
 e1=(1-math.sqrt(1-E2))/(1+math.sqrt(1-E2))
 p=mu+(3*e1/2-27*e1**3/32)*math.sin(2*mu)+(21*e1**2/16-55*e1**4/32)*math.sin(4*mu)+(151*e1**3/96)*math.sin(6*mu)+(1097*e1**4/512)*math.sin(8*mu)
 c=math.cos(p);s=math.sin(p);t=math.tan(p)**2;cc=EP2*c*c;n=A/math.sqrt(1-E2*s*s);rho=A*(1-E2)/(1-E2*s*s)**1.5;d=(x-500000)/(n*K)
 lat=p-(n*math.tan(p)/rho)*(d*d/2-(5+3*t+10*cc-4*cc*cc-9*EP2)*d**4/24+(61+90*t+298*cc+45*t*t-252*EP2-3*cc*cc)*d**6/720)
 lon=L0+(d-(1+2*t+cc)*d**3/6+(5-2*cc+28*t-3*cc*cc+8*EP2+24*t*t)*d**5/120)/c
 result=(math.degrees(lon),math.degrees(lat));forward(*result)
 return result

class Transformer:
 def __init__(self,fn):self.fn=fn
 @classmethod
 def from_crs(cls,source,target,always_xy=False):
  if not always_xy:raise ValueError('Proyeksi lokal memerlukan always_xy=True')
  parse=lambda v:int(str(v).upper().removeprefix('EPSG:'))
  pair=(parse(source),parse(target))
  if pair==(4326,32749):return cls(forward)
  if pair==(32749,4326):return cls(inverse)
  raise ValueError('Hanya EPSG:4326 <-> EPSG:32749 yang didukung')
 def transform(self,x,y,z=None):
  if isinstance(x,Real) and isinstance(y,Real):
   a,b=self.fn(float(x),float(y));return (a,b) if z is None else (a,b,z)
  pairs=[self.fn(float(a),float(b)) for a,b in zip(x,y,strict=True)]
  xx=[a for a,b in pairs];yy=[b for a,b in pairs]
  return (xx,yy) if z is None else (xx,yy,z)
