import pandas as pd
from collections import Counter, defaultdict
from datetime import date, timedelta
import re
from analisis_quinielas import cargar_datos, construir_indices, predecir_b1, inverso

df = cargar_datos()
b1_a_fechas = construir_indices(df)

df["loteria_norm"] = df["loteria"].str.replace(r"(\d)\s+(AM|PM)", r"\1\2", regex=True)

def parse_hour(name):
    name = name.strip()
    m = re.search(r"(\d+)(:\d+)?\s*(AM|PM)", name, re.IGNORECASE)
    if m:
        h = int(m.group(1))
        if m.group(2):
            h += int(m.group(2).replace(":", "")) / 60.0
        if m.group(3).upper() == "PM" and h < 12:
            h += 12
        if m.group(3).upper() == "AM" and h == 12:
            h = 0
        return h
    if "DIA" in name.upper() or "DÍA" in name.upper():
        return 12.0
    if "MEDIO DIA" in name.upper() or "MEDIO DÍA" in name.upper():
        return 12.5
    if "TARDE" in name.upper():
        return 15.0
    if "NOCHE" in name.upper():
        return 20.0
    return 14.0

lot_times = {name: parse_hour(name) for name in df["loteria_norm"].unique()}

top_n_pred = 10

# Precompute predictions for all 100 numbers once
print("Precomputando predicciones para 0-99...")
pred_cache = {}
for n in range(100):
    contador, *_ = predecir_b1([n], b1_a_fechas, df)
    if contador:
        pred_cache[n] = [num for num, count in contador.most_common(top_n_pred)]
    else:
        pred_cache[n] = []
print(f"  {len([k for k,v in pred_cache.items() if v])} numeros con prediccion")

todas_fechas = sorted(df["fecha"].unique())
fecha_set = set(todas_fechas)

# Build date -> sorted list of (loteria_norm, b1)
print("Construyendo mapa de fechas...")
fecha_map = defaultdict(list)
for _, row in df.iterrows():
    fecha_map[row["fecha"]].append((row["loteria_norm"], int(row["b1"])))

for f in fecha_map:
    fecha_map[f].sort(key=lambda x: lot_times.get(x[0], 14.0))

resultados = []
count_total = 0

print("Procesando predicciones historicas...")
for fecha in todas_fechas:
    if fecha not in fecha_map:
        continue
    entries = fecha_map[fecha]
    for i, (lot, b1_pool) in enumerate(entries):
        top_pred = pred_cache.get(b1_pool, [])
        if not top_pred:
            continue

        # Same day after this lottery
        for j in range(i + 1, len(entries)):
            lot_after, b1_after = entries[j]
            if b1_after in top_pred:
                resultados.append((fecha, lot, b1_pool, b1_after, fecha, lot_after, 0))

        # Next day
        sig_fecha = fecha + timedelta(days=1)
        if sig_fecha in fecha_map:
            for lot_sig, b1_sig in fecha_map[sig_fecha]:
                if b1_sig in top_pred:
                    resultados.append((fecha, lot, b1_pool, b1_sig, sig_fecha, lot_sig, 1))

    count_total += 1

# Aggregate
hoy_lot = Counter()
dia1_lot = Counter()
hoy_desde = Counter()
dia1_desde = Counter()

for r in resultados:
    _, lot_desde, _, _, _, lot_hit, dias = r
    if dias == 0:
        hoy_lot[lot_hit] += 1
        hoy_desde[lot_desde] += 1
    else:
        dia1_lot[lot_hit] += 1
        dia1_desde[lot_desde] += 1

total_hoy = sum(hoy_lot.values())
total_dia1 = sum(dia1_lot.values())

print(f"\n=== RESULTADOS FINALES ===")
print(f"Dias procesados: {count_total}")
print(f"Mismo dia (despues del horario): {total_hoy}")
print(f"Dia siguiente: {total_dia1}")

print(f"\n=== LOTERIAS QUE MAS PEGAN - MISMO DIA ===")
for lot, c in hoy_lot.most_common(20):
    print(f"  {lot:<35}: {c}")

print(f"\n=== LOTERIAS QUE MAS PEGAN - DIA SIGUIENTE ===")
for lot, c in dia1_lot.most_common(20):
    print(f"  {lot:<35}: {c}")

print(f"\n=== LOTERIAS QUE MAS PREDICEN (ORIGEN) ===")
print("MISMO DIA:")
for lot, c in hoy_desde.most_common(10):
    print(f"  {lot:<35}: {c}")
print("DIA SIGUIENTE:")
for lot, c in dia1_desde.most_common(10):
    print(f"  {lot:<35}: {c}")
