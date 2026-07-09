import pandas as pd
from collections import Counter, defaultdict
from datetime import date, timedelta, datetime
from analisis_quinielas import cargar_datos, construir_indices, predecir_b1, inverso

df = cargar_datos()
b1_a_fechas = construir_indices(df)

ang_8am = df[df["loteria"] == "Anguilla 8AM"].copy()
print(f"Total Anguilla 8AM: {len(ang_8am)}")
print(f"Rango: {ang_8am['fecha'].min()} a {ang_8am['fecha'].max()}")

ang_8am = ang_8am.sort_values("fecha")
top_n_pred = 10
todas_fechas = sorted(df["fecha"].unique())
fecha_set = set(todas_fechas)

hoy_por_loteria = defaultdict(int)
dia1_por_loteria = defaultdict(int)
resultados = []

for idx, row in ang_8am.iterrows():
    fecha = row["fecha"]
    pool = [int(row["b1"])]

    contador, mejores_fechas, max_count, mejores_pales = predecir_b1(pool, b1_a_fechas, df)
    if not contador:
        continue

    top_pred = [num for num, count in contador.most_common(top_n_pred)]

    # MISMO DIA: todas las loterias del mismo dia, excepto Anguilla 8AM
    mismo_dia = df[(df["fecha"] == fecha) & (df["loteria"] != "Anguilla 8AM")]
    for _, frow in mismo_dia.iterrows():
        if int(frow["b1"]) in top_pred:
            hoy_por_loteria[frow["loteria"]] += 1
            resultados.append((fecha, pool[0], int(frow["b1"]), 0, frow["loteria"]))

    # DIA SIGUIENTE
    sig_fecha = fecha + timedelta(days=1)
    if sig_fecha in fecha_set:
        sig_dia = df[df["fecha"] == sig_fecha]
        for _, frow in sig_dia.iterrows():
            if int(frow["b1"]) in top_pred:
                dia1_por_loteria[frow["loteria"]] += 1
                resultados.append((fecha, pool[0], int(frow["b1"]), 1, frow["loteria"]))

print(f"\n=== TOTAL HITS ===")
total_hoy = len([r for r in resultados if r[3] == 0])
total_dia1 = len([r for r in resultados if r[3] == 1])
print(f"Mismo dia: {total_hoy}")
print(f"Dia siguiente: {total_dia1}")

print(f"\n=== LOTERIAS QUE MAS PEGAN - MISMO DIA ===")
top_hoy = sorted(hoy_por_loteria.items(), key=lambda x: -x[1])
for lot, c in top_hoy[:15]:
    print(f"  {lot:<35}: {c}")

print(f"\n=== LOTERIAS QUE MAS PEGAN - DIA SIGUIENTE ===")
top_dia1 = sorted(dia1_por_loteria.items(), key=lambda x: -x[1])
for lot, c in top_dia1[:15]:
    print(f"  {lot:<35}: {c}")

# Ejemplos mismo dia
print(f"\n=== EJEMPLOS MISMO DIA (primeros 20) ===")
for r in resultados:
    if r[3] == 0:
        print(f"  {r[0]} Anguila8AM={r[1]:02d} -> predijo {r[2]:02d} en {r[4]}")
