"""
Actualiza el Excel con resultados de dias faltantes desde la ultima fecha registrada hasta ayer.
"""
import pandas as pd
import requests
import json
import re
from datetime import date, timedelta
import os

_script_dir = os.path.dirname(os.path.abspath(__file__))
RUTA = os.path.join(_script_dir, "Resultados quinielas completo.xlsx")

def scrapear_fecha_completa(fecha):
    """Scrapea B1, B2, B3 de una fecha especifica"""
    fecha_str = fecha.strftime("%Y-%m-%d")
    url = f"https://enloteria.com/resultados-loterias-{fecha_str}"
    print(f"  Scrapeando {url} ...")
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        resp.encoding = "utf-8"
    except Exception as e:
        print(f"  Error de conexion: {e}")
        return []
    m = re.search(r'<script type="application/ld\+json">(.*?)</script>', resp.text, re.DOTALL)
    if not m:
        print("  No se encontro JSON-LD.")
        return []
    try:
        data = json.loads(m.group(1))
    except Exception as e:
        print(f"  Error parseando JSON: {e}")
        return []
    eventos = data.get("@graph", []) if isinstance(data, dict) and "@graph" in data else (data if isinstance(data, list) else [])
    resultados = []
    for ev in eventos:
        if not isinstance(ev, dict) or ev.get("@type") != "Event":
            continue
        props = ev.get("additionalProperty", [])
        nombre = ev.get("name", "")
        b1 = b2 = b3 = None
        for p in props:
            if isinstance(p, dict):
                nm = p.get("name", "")
                vl = p.get("value", "")
                if nm == "Primer Premio":
                    b1 = int(vl) if vl else None
                elif nm == "Segundo Premio":
                    b2 = int(vl) if vl else None
                elif nm == "Tercer Premio":
                    b3 = int(vl) if vl else None
        if b1 is not None:
            resultados.append({"loteria": nombre, "fecha": fecha, "b1": b1, "b2": b2, "b3": b3})
    return resultados

def main():
    print("Cargando datos existentes...")
    df = pd.read_excel(RUTA)
    df.columns = ["loteria", "fecha", "b1", "b2", "b3"]
    df["fecha"] = df["fecha"].dt.date

    ultima_por_loteria = df.groupby("loteria")["fecha"].max()
    ultima_global = ultima_por_loteria.max()
    primera_global = ultima_por_loteria.min()
    print(f"Fecha max global: {ultima_global}")
    print(f"Fecha min (loteria mas atrasada): {primera_global}")

    existentes = set(zip(df["loteria"], df["fecha"]))

    hoy = date.today()
    ayer = hoy - timedelta(days=1)
    dias_a_scrapear = []
    dia = primera_global
    while dia <= ayer:
        dias_a_scrapear.append(dia)
        dia += timedelta(days=1)

    if not dias_a_scrapear:
        print("No hay dias faltantes. Datos al dia!")
        return

    print(f"Dias a revisar: {len(dias_a_scrapear)} ({dias_a_scrapear[0]} a {dias_a_scrapear[-1]})")

    nuevos = []
    for dia in dias_a_scrapear:
        resultados = scrapear_fecha_completa(dia)
        if resultados:
            nuevos_filtrados = [r for r in resultados if (r["loteria"], r["fecha"]) not in existentes]
            nuevos.extend(nuevos_filtrados)
            omitidos = len(resultados) - len(nuevos_filtrados)
            msg = f"  -> {len(resultados)} sorteos"
            if omitidos:
                msg += f" ({omitidos} ya existian)"
            print(msg)
        else:
            print(f"  -> Sin datos")

    if not nuevos:
        print("No se encontraron nuevos resultados.")
        return

    df_nuevos = pd.DataFrame(nuevos)
    df_total = pd.concat([df, df_nuevos], ignore_index=True)
    df_total.to_excel(RUTA, index=False)
    print(f"\nActualizado! {len(df_nuevos)} nuevos registros agregados.")
    print(f"Total ahora: {len(df_total):,} registros.")
    print(f"Nueva ultima fecha: {df_total['fecha'].max()}")

if __name__ == "__main__":
    main()
