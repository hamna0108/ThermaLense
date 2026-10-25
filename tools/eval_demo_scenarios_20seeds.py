import math
import numpy as np
from fastapi.testclient import TestClient
from service.app import app

def imul(a, b):
    return (a * b) & 0xFFFFFFFF

def mulberry32(a):
    def next_rand():
        nonlocal a
        a = (a + 0x6D2B79F5) & 0xFFFFFFFF
        t = imul(a ^ (a >> 15), 1 | a)
        t = (t + imul(t ^ (t >> 7), 61 | t)) & 0xFFFFFFFF
        res = (t ^ (t >> 14)) & 0xFFFFFFFF
        return res / 4294967296.0
    return next_rand

def random_normal(rng, mean=0.0, std=1.0):
    u1 = rng()
    u2 = rng()
    while u1 <= 1e-15:
        u1 = rng()
    z0 = math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)
    return mean + z0 * std

def run_simulation(scenario, seed, L=0.1, T=100.0, Tb=20.0, Tp=80.0, sig=0.5):
    deltaT = Tp - Tb
    kBase = 20
    tb = [2.0 + (i / (kBase - 1)) * 98.0 for i in range(kBase)]
    xb = [[0.03, 0.05, 0.07][i % 3] for i in range(kBase)]
    
    rng = mulberry32(seed)
    
    # Baseline
    yb = []
    for i in range(kBase):
        xNorm = xb[i] / L
        tNorm = tb[i] / T
        uNorm = math.sin(math.pi * xNorm) * math.exp(-0.10 * (math.pi ** 2) * tNorm)
        uClean = Tb + deltaT * uNorm
        uNoisy = round((uClean + random_normal(rng, 0, sig)) * 100) / 100
        yb.append(uNoisy)
        
    # Operational test readings
    to = [1.0, 1.67, 2.78, 4.64, 7.74, 12.92, 21.54, 35.94, 59.95, 100.0]
    xo = [0.03, 0.05, 0.07, 0.03, 0.05, 0.07, 0.03, 0.05, 0.07, 0.03]
    yo = []
    
    for i in range(10):
        xNorm = xo[i] / L
        tNorm = to[i] / T
        
        if scenario == 'H':
            uNorm = math.sin(math.pi * xNorm) * math.exp(-0.10 * (math.pi ** 2) * tNorm)
        elif scenario == 'A':
            uNorm = math.sin(math.pi * xNorm) * math.exp(-2.50 * (math.pi ** 2) * tNorm)
        elif scenario == 'A_weak':
            # factor 1.3
            uNorm = math.sin(math.pi * xNorm) * math.exp(-0.13 * (math.pi ** 2) * tNorm)
        elif scenario in ('F_stuck', 'F_bias', 'F_weak_bias'):
            uNorm = math.sin(math.pi * xNorm) * math.exp(-0.10 * (math.pi ** 2) * tNorm)
        elif scenario == 'C':
            tcNorm = 0.35
            if tNorm < tcNorm:
                uNorm = math.sin(math.pi * xNorm) * math.exp(-0.10 * (math.pi ** 2) * tNorm)
            else:
                uNorm = math.sin(math.pi * xNorm) * math.exp(-(math.pi ** 2) * (0.10 * tcNorm + 0.80 * (tNorm - tcNorm)))
                
        uClean = Tb + deltaT * uNorm
        uNoisy = uClean + random_normal(rng, 0, sig)
        if scenario == 'F_stuck' and i == 3:
            uNoisy = 50.0
        elif scenario == 'F_bias' and i == 5:
            uNoisy += 5.0
        elif scenario == 'F_weak_bias' and i == 5:
            uNoisy += 3.0 * sig  # +1.5 °C
            
        yo.append(round(uNoisy * 100) / 100)
        
    return {
        "bar_length_m": L,
        "test_duration_s": T,
        "boundary_temperature": Tb,
        "initial_peak_temperature": Tp,
        "sigma": sig,
        "readings": {"x": xo, "t": to, "y": yo},
        "baseline": {"x": xb, "t": tb, "y": yb}
    }

def main():
    client = TestClient(app)
    scenarios = [
        ("H", "H", "Healthy run"),
        ("A", "A", "Clear-cut anomalous (factor 2.5)"),
        ("A_weak", "A", "Small change in heat spread (factor 1.3)"),
        ("F_stuck", "F", "Clear-cut sensor stuck (Sensor #3)"),
        ("F_bias", "F", "Clear-cut sensor bias (+5 °C)"),
        ("F_weak_bias", "F", "Weak sensor offset (~3 sigma, +1.5 °C)"),
        ("C", "C", "Clear-cut change-point (tc=35 s)")
    ]
    
    seeds = list(range(1, 21))
    results = {}
    
    for sc_key, expected_class, desc in scenarios:
        counts = {}
        change_times = []
        for s in seeds:
            payload = run_simulation(sc_key, s)
            res = client.post("/v1/diagnose", json=payload)
            assert res.status_code == 200, res.text
            data = res.json()
            c = data["assigned_class"]
            counts[c] = counts.get(c, 0) + 1
            if sc_key == 'C' and c == 'C':
                change_times.append(data.get("change_time"))
        results[sc_key] = {
            "desc": desc,
            "expected": expected_class,
            "counts": counts,
            "correct": counts.get(expected_class, 0),
            "change_times": change_times
        }
        
    print("\n================== BENCHMARK OVER 20 SEEDS ==================")
    for sc_key, info in results.items():
        print(f"Scenario: {sc_key:<12} | Expected: {info['expected']} | Correct: {info['correct']}/20 | Breakdown: {info['counts']}")
        if sc_key == 'C':
            print(f"  Change times detected: {info['change_times']}")

if __name__ == "__main__":
    main()
