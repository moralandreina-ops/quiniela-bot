from analisis_quinielas import cargar_datos, anguila_horarios_ordenados, inverso
from collections import defaultdict, Counter
import re

df = cargar_datos()

# Pre-filter and normalize Anguilla data once
ang = df[df["loteria"].str.contains("Anguilla", case=False, na=False)].copy()
ang["norm"] = ang["loteria"].apply(lambda n: re.sub(r"(\d)\s+(AM|PM)", r"\1\2", n, flags=re.IGNORECASE))

# Build lookup: for each (tag, fecha) -> b1
tag_fecha_b1 = defaultdict(dict)
for _, row in ang.iterrows():
    tag = None
    for t in anguila_horarios_ordenados():
        if row["norm"].endswith(t):
            tag = t
            break
    if tag:
        tag_fecha_b1[tag][row["fecha"]] = int(row["b1"])

# Precompute predictions for each number (0-99) and each starting tag
print("Precomputando predicciones secuenciales...")
horarios = anguila_horarios_ordenados()
cache = {}
for tag in horarios[:-1]:
    sig_tag = horarios[horarios.index(tag) + 1]
    sig_fecha_b1 = tag_fecha_b1.get(sig_tag, {})
    
    for n in range(100):
        # Find dates where this number (or inverse) appeared at this tag
        pool = {n, inverso(n)}
        fechas = {f for f, b in tag_fecha_b1[tag].items() if b in pool}
        if not fechas:
            continue
        
        # Count what appeared in the next tag on those dates
        counter = Counter()
        for f in fechas:
            if f in sig_fecha_b1:
                counter[sig_fecha_b1[f]] += 1
        
        if counter:
            cache[(tag, n)] = counter

print("Evaluando...")
horarios = anguila_horarios_ordenados()
total_pred = 0
hit_top1 = 0
hit_top3 = 0
hit_top5 = 0
hit_top10 = 0
por_h = defaultdict(lambda: [0, 0, 0, 0, 0])

for i in range(len(horarios) - 1):
    h_act = horarios[i]
    h_sig = horarios[i + 1]
    act_fecha_b1 = tag_fecha_b1.get(h_act, {})
    sig_fecha_b1 = tag_fecha_b1.get(h_sig, {})
    
    for fecha, b1 in act_fecha_b1.items():
        if fecha not in sig_fecha_b1:
            continue
        b1_real = sig_fecha_b1[fecha]
        
        counter = cache.get((h_act, b1))
        if not counter:
            continue
        
        total_pred += 1
        por_h[h_act][0] += 1
        top = [n for n, _ in counter.most_common()]
        
        if top and top[0] == b1_real:
            hit_top1 += 1; por_h[h_act][1] += 1
        if b1_real in top[:3]:
            hit_top3 += 1; por_h[h_act][2] += 1
        if b1_real in top[:5]:
            hit_top5 += 1; por_h[h_act][3] += 1
        if b1_real in top[:10]:
            hit_top10 += 1; por_h[h_act][4] += 1

print(f"Total predicciones: {total_pred}")
print(f"Top 1:  {hit_top1:>4} ({hit_top1/total_pred*100:.1f}%)")
print(f"Top 3:  {hit_top3:>4} ({hit_top3/total_pred*100:.1f}%)")
print(f"Top 5:  {hit_top5:>4} ({hit_top5/total_pred*100:.1f}%)")
print(f"Top 10: {hit_top10:>4} ({hit_top10/total_pred*100:.1f}%)")

print()
for h in horarios[:-1]:
    p, t1, t3, t5, t10 = por_h[h]
    if p == 0:
        continue
    print(f"{h:>5} -> {p:>3} pred | T1: {t1/p*100:>4.0f}% | T3: {t3/p*100:>4.0f}% | T5: {t5/p*100:>4.0f}% | T10: {t10/p*100:>4.0f}%")
