"""L9 velocity/acceleration/jerk parameter sweep; separate from fixed-time."""
import hashlib
import math
from pathlib import Path
from experiments.csv_servo.points import load_points
from experiments.piecewise_fixed_time import _verify_config
from experiments.polynomial_fixed_time import (
    REFERENCE_START, REFERENCE_END, SAMPLE_PERIOD_S, MOVEL_FAST_PLATEAU_MM_S,
)
MATRIX = (
    (300.,500.,6000.),(300.,800.,10000.),(300.,1100.,16000.),
    (380.,500.,10000.),(380.,800.,16000.),(380.,1100.,6000.),
    (460.,500.,16000.),(460.,800.,6000.),(460.,1100.,10000.),
)
DISTANCE = math.dist(REFERENCE_START[:3],REFERENCE_END[:3])


def parameters(profile,V,A,J=None):
    if profile not in ("trapezoidal","double_s"):
        raise ValueError("Unsupported profile")
    if not all(math.isfinite(x) and x>0 for x in (V,A)+(() if J is None else (J,))):
        raise ValueError("Limits must be finite positive")
    if profile=="double_s":
        if J is None:
            raise ValueError("Double-S requires jerk")
        tj=A/J
        ta=V/A-tj
        if ta<=0:
            raise ValueError("No acceleration plateau")
        r=2*tj+ta
    else:
        tj=0.
        ta=V/A
        r=ta
    cruise=DISTANCE/V-r
    if cruise<=0:
        raise ValueError("No velocity plateau")
    Tmin=DISTANCE/V+r
    n=math.ceil(Tmin/SAMPLE_PERIOD_S-1e-12)
    T=n*SAMPLE_PERIOD_S
    k=T/Tmin
    return dict(duration_s=T,minimum_duration_s=Tmin,intervals=n,
                ramp_s=r*k,tj_s=tj*k,ta_s=ta*k,cruise_s=cruise*k,
                peak_v=V/k,peak_a=A/k**2,
                peak_j=J/k**3 if profile=="double_s" else None)


def position(profile,t,V,A,J=None):
    p=parameters(profile,V,A,J)
    if not math.isfinite(t):
        raise ValueError("Nonfinite time")
    t=min(max(t,0.),p["duration_s"])
    r,v,a=p["ramp_s"],p["peak_v"],p["peak_a"]

    def first_ramp(z):
        if profile=="trapezoidal":
            return .5*a*z*z
        tj,ta,j=p["tj_s"],p["ta_s"],p["peak_j"]
        if z<=tj:
            return j*z**3/6
        x1,v1=j*tj**3/6,a*tj/2
        if z<=tj+ta:
            d=z-tj
            return x1+v1*d+.5*a*d*d
        x2=x1+v1*ta+.5*a*ta*ta
        v2=v1+a*ta
        d=z-tj-ta
        return x2+v2*d+.5*a*d*d-j*d**3/6

    if t<=r:
        return first_ramp(t)
    if t>=p["duration_s"]-r:
        return DISTANCE-first_ramp(p["duration_s"]-t)
    return v*r/2+v*(t-r)


def expected_rows(profile,V,A,J=None):
    p=parameters(profile,V,A,J)
    delta=[b-a for a,b in zip(REFERENCE_START,REFERENCE_END)]
    rows=[]
    for i in range(p["intervals"]+1):
        if i==0:
            rows.append(list(REFERENCE_START))
        elif i==p["intervals"]:
            rows.append(list(REFERENCE_END))
        else:
            s=position(profile,i*SAMPLE_PERIOD_S,V,A,J)/DISTANCE
            rows.append([a+s*d for a,d in zip(REFERENCE_START,delta)])
    return rows


def verify(profile,path,V,A,J=None):
    expected=expected_rows(profile,V,A,J)
    points=load_points(path,"ServoP")
    if len(points)!=len(expected):
        raise ValueError("Unexpected CSV row count")
    previous=-math.inf
    for i,(pt,row) in enumerate(zip(points,expected),1):
        if pt.mode!="ServoP" or not all(map(math.isfinite,pt.values)):
            raise ValueError("Invalid CSV values/mode")
        if any(abs(a-b)>2e-6 for a,b in zip(pt.values,row)):
            raise ValueError(f"Unexpected pose row {i}")
        if pt.values[1]<previous-1e-7:
            raise ValueError("Nonmonotonic Y")
        previous=pt.values[1]


def sweep_cases(profile,cfg):
    if profile not in ("trapezoidal","double_s","ruckig"):
        raise ValueError("Invalid piecewise algorithm")
    _verify_config(cfg)
    cases=[]
    for i,(V,A,J) in enumerate(MATRIX,1):
        case=dict(name=f"{profile}_sweep_{i:02d}",study="L9",
                  velocity_limit_mm_s=V,acceleration_limit_mm_s2=A,
                  global_speed_factor=100,
                  exceeds_movel_fast_speed=V>MOVEL_FAST_PLATEAU_MM_S)
        if profile!="trapezoidal":
            case["jerk_limit_mm_s3"]=J
        else:
            case["unbounded_transition_jerk"]=True
        if profile=="ruckig":
            case.update(mode="ruckig",start=list(REFERENCE_START),
                        target=list(REFERENCE_END),max_velocity=[V]*6,
                        max_acceleration=[A]*6,max_jerk=[J]*6,
                        minimum_duration_s=None)
        else:
            jerk=J if profile=="double_s" else None
            p=parameters(profile,V,A,jerk)
            path=Path(__file__).resolve().parent/profile/f"points_{profile}_sweep_{i:02d}.csv"
            verify(profile,path,V,A,jerk)
            case.update(mode="csv",csv_path=str(path),
                        csv_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                        expected_points=p["intervals"]+1,
                        duration_s=p["duration_s"],
                        minimum_theoretical_duration_s=p["minimum_duration_s"],
                        expected_peak_speed_mm_s=p["peak_v"],
                        expected_peak_acceleration_mm_s2=p["peak_a"])
            if jerk is not None:
                case["expected_peak_jerk_mm_s3"]=p["peak_j"]
        cases.append(case)
    return cases
