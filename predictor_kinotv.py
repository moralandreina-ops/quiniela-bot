import pandas as pd
import numpy as np
from collections import Counter

RUTA = r"C:\Users\pjorge\Downloads\Resultados KinoTV 2025.xlsx"

def cargar_datos():
    df = pd.read_excel(RUTA)
    cols = ["fecha"] + [f"b{i}" for i in range(1, 21)]
    df.columns = cols
    df["fecha"] = df["fecha"].dt.date
    for c in [f"b{i}" for i in range(1, 21)]:
        df[c] = df[c].astype(int)
    return df

def hot(data):
    c = Counter(data.flatten())
    return {n for n, _ in c.most_common(10)}

def cold(data):
    c = Counter(data.flatten())
    return {n for n, _ in c.most_common()[-10:]}

def balanced(data):
    f = Counter(data.flatten())
    lo = {n: f[n] for n in range(1, 41)}
    hi = {n: f[n] for n in range(41, 81)}
    return {n for n, _ in Counter(lo).most_common(5)} | {n for n, _ in Counter(hi).most_common(5)}

def ens_hot_bal_cold(data):
    p = list(balanced(data)) + list(hot(data)) + list(cold(data))
    return {n for n, _ in Counter(p).most_common(10)}

def ens_score(data):
    f = Counter(data.flatten())
    t = len(data) * 20
    last_set = set(data[-1])
    last_seen = {}
    for i, r in enumerate(data):
        for x in r:
            last_seen[x] = i
    now = len(data)
    scores = Counter()
    for n in range(1, 81):
        freq_score = f.get(n, 0) / t * 100
        gap = now - last_seen.get(n, -1)
        gap_score = gap / now * 100
        recent = sum(1 for r in data[-10:] if n in r) / 10 * 100
        anti = 0 if n in last_set else 20
        scores[n] = freq_score * 0.4 + gap_score * 0.15 + recent * 0.25 + anti * 0.1
    return {n for n, _ in scores.most_common(10)}

def backtest(method, data):
    hits = [len(method(data[:i]) & set(data[i])) for i in range(100, len(data))]
    return float(np.mean(hits))

def main():
    df = cargar_datos()
    balls = df.iloc[:, 1:].values
    
    print(f"Cargados {len(df)} sorteos KinoTV")
    print(f"Rango: {df['fecha'].min()} a {df['fecha'].max()}")
    print(f"Ultimo sorteo ({df['fecha'].max()}):")
    print("  " + " ".join(str(x) for x in balls[-1]))
    print()
    
    print("Ingresa los 20 numeros del ultimo sorteo:")
    ultimo = input("Numeros (separados por espacio): ").strip()
    
    try:
        nums = [int(x) for x in ultimo.split()]
        if len(nums) != 20:
            print(f"Error: se requieren 20 numeros, ingresaste {len(nums)}")
            return
        if not all(1 <= n <= 80 for n in nums):
            print("Error: numeros deben estar entre 1 y 80")
            return
    except ValueError:
        print("Error: entrada invalida")
        return
    
    user_set = set(nums)
    data = balls
    
    metodos = [
        (ens_score, "ENS-SCORE (recomendado)"),
        (balanced, "BALANCE"),
        (ens_hot_bal_cold, "ENS-H+B+C"),
        (hot, "HOT"),
    ]
    
    consenso = Counter()
    
    for method, nombre in metodos:
        pred = method(data)
        aciertos = backtest(method, data)
        diff = aciertos - 2.5
        signo = "+" if diff > 0 else ""
        
        pred_limpia = pred - user_set
        if len(pred_limpia) < 10:
            f = Counter(data.flatten())
            extras = [n for n, _ in f.most_common(50) if n not in pred_limpia and n not in user_set]
            pred_limpia = pred_limpia | set(extras[:10 - len(pred_limpia)])
        
        consenso.update(pred_limpia)
        nums_out = sorted(pred_limpia)[:10]
        
        sep = "-" * 50
        print(sep)
        print("  " + nombre)
        print(sep)
        print("  " + " ".join(f"{n:>2}" for n in nums_out))
        print(f"  Promedio: {aciertos:.3f}/10 ({signo}{diff:.3f} vs aleatorio)")
        print()
    
    sep2 = "=" * 50
    print(sep2)
    print("  CONSENSO (numeros en 3+ metodos)")
    print(sep2)
    consensus_nums = [n for n, c in consenso.most_common() if c >= 3]
    if consensus_nums:
        print("  " + " ".join(f"{n:>2}" for n in sorted(consensus_nums)))
    else:
        print("  (ningun numero coincide en 3+ metodos)")
    print()
    
    print(sep2)
    print("  BACKTEST - ENS-SCORE (ultimos 50 sorteos)")
    print(sep2)
    test_hits = []
    for i in range(len(data) - 50, len(data)):
        p = ens_score(data[:i])
        r = set(data[i])
        test_hits.append(len(p & r))
    avg = float(np.mean(test_hits))
    pct = avg / 10 * 100
    print(f"  Aciertos: {avg:.2f}/10 ({pct:.1f}%)")
    print(f"  Mejor: {max(test_hits)}/10 | Peor: {min(test_hits)}/10")
    print(f"  vs aleatorio: {avg-2.5:+.3f}")

if __name__ == "__main__":
    main()
