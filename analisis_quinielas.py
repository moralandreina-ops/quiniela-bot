import pandas as pd
from collections import Counter, defaultdict
import requests
import re
from datetime import date, timedelta
import os

_script_dir = os.path.dirname(os.path.abspath(__file__))
RUTA = os.path.join(_script_dir, "Resultados quinielas completo.xlsx")

def inverso(n):
    return int(str(n).zfill(2)[::-1])

def cargar_datos():
    df = pd.read_excel(RUTA)
    df.columns = ["loteria", "fecha", "b1", "b2", "b3"]
    df["fecha"] = df["fecha"].dt.date
    df["b1"] = df["b1"].astype("Int64")
    df["b2"] = df["b2"].astype("Int64")
    df["b3"] = df["b3"].astype("Int64")
    df = df.dropna()
    return df

def construir_indices(df):
    b1_a_fechas = defaultdict(set)
    for _, row in df.iterrows():
        b1_a_fechas[row["b1"]].add(row["fecha"])
    return b1_a_fechas

def analizar(numeros_buscar, b1_a_fechas, df):
    numeros_con_inversos = set()
    for n in numeros_buscar:
        numeros_con_inversos.add(n)
        numeros_con_inversos.add(inverso(n))
    fechas_por_num = {}
    for n in numeros_buscar:
        fechas = b1_a_fechas.get(n, set()) | b1_a_fechas.get(inverso(n), set())
        fechas_por_num[n] = fechas
    numeros_validos = {n for n, f in fechas_por_num.items() if f}
    numeros_invalidos = {n for n, f in fechas_por_num.items() if not f}
    if not numeros_validos:
        problemas = [(n, "nunca ha salido en B1 (ni su inverso)") for n in numeros_invalidos]
        return {}, set(), problemas, {}, 0, set()
    fecha_count = Counter()
    for n, fechas in fechas_por_num.items():
        if fechas:
            for f in fechas:
                fecha_count[f] += 1
    max_count = max(fecha_count.values())
    mejores_fechas = {f for f, c in fecha_count.items() if c == max_count}
    numeros_activos = {n for n in numeros_validos if fechas_por_num[n] & mejores_fechas}
    numeros_inactivos = numeros_validos - numeros_activos
    problemas = ([(n, "nunca ha salido en B1 (ni su inverso)") for n in numeros_invalidos] +
                 [(n, "no coincide el mismo dia con el grupo maximo") for n in numeros_inactivos])
    rows = df[df["fecha"].isin(mejores_fechas) & df["b1"].isin(numeros_con_inversos)]
    contador = Counter()
    pares = defaultdict(Counter)
    for _, row in rows.iterrows():
        b1, b2, b3 = row["b1"], row["b2"], row["b3"]
        for companion, other in [(b2, b3), (b3, b2)]:
            if companion not in numeros_con_inversos:
                contador[companion] += 1
                pares[companion][other] += 1
    mejores_pares = {}
    for comp, pair_counter in pares.items():
        if pair_counter:
            mejor_num, mejor_count = pair_counter.most_common(1)[0]
            mejores_pares[comp] = (mejor_num, mejor_count)
    return contador, mejores_fechas, problemas, mejores_pares, max_count, numeros_activos

def predecir_b1(pool, b1_a_fechas, df):
    pool_con_inv = set(pool)
    for n in pool:
        pool_con_inv.add(inverso(n))
    fecha_count = Counter()
    for _, row in df.iterrows():
        if row["b1"] in pool_con_inv:
            fecha_count[row["fecha"]] += 1
    if not fecha_count:
        return {}, set(), 0, {}
    max_count = max(fecha_count.values())
    mejores_fechas = {f for f, c in fecha_count.items() if c == max_count}
    rows = df[df["fecha"].isin(mejores_fechas)]
    contador = Counter()
    pale = defaultdict(Counter)
    for _, row in rows.iterrows():
        b1 = row["b1"]
        contador[b1] += 1
        pale[b1][row["b2"]] += 1
        pale[b1][row["b3"]] += 1
    mejores_pales = {}
    for b1, pc in pale.items():
        if pc:
            mejores_pales[b1] = pc.most_common(1)[0]
    return contador, mejores_fechas, max_count, mejores_pales

def jugar_b2b3(b1_a_fechas, df):
    print("=== METODO 1: ACOMPANANTES B2/B3 ===")
    print("Cada numero incluye automaticamente su inverso (ej: 30 <-> 03)\n")
    while True:
        entrada = input("Numeros B1 (0-99, ej: 12 45 83) o 'salir': ").strip()
        if entrada.lower() in ("salir", "exit", "q"):
            break
        entrada = entrada.replace(",", " ").replace("-", " ")
        try:
            numeros = sorted({int(x) for x in entrada.split()})
            if not all(0 <= n <= 99 for n in numeros):
                print("Solo numeros entre 0 y 99\n"); continue
        except ValueError:
            print("Entrada invalida.\n"); continue
        contador, fechas, problemas, mejores_pares, max_count, _ = analizar(numeros, b1_a_fechas, df)
        print(f"\n--- Resultados B1={numeros} ---")
        if problemas:
            print(f"Maximo que coincide el mismo dia: {max_count}/{len(numeros)}")
            for num, motivo in problemas:
                print(f"  - {num}: {motivo}")
        print(f"Analizando {len(fechas)} fechas\n")
        if contador:
            print(f"{'#':<5}{'Frec':<8}{'%':<8}{'Mejor par':<14}")
            print("-" * 35)
            for num, count in contador.most_common(10):
                pct = count / len(fechas) * 100
                par_str = ""
                if num in mejores_pares:
                    pn, pc = mejores_pares[num]
                    par_str = f"+{pn} ({pc})"
                print(f"{num:<5}{count:<8}{pct:.1f}%{par_str:<14}")
        else:
            print("Sin acompanantes en B2/B3.")
        print()

def jugar_b1(b1_a_fechas, df):
    print("=== METODO 2: B1 DE FECHA SIMILAR (MANUAL) ===")
    print("Busca fecha historica con mas B1s del pool y predice los que faltan\n")
    while True:
        entrada = input("Pool de B1s del dia (0-99, ej: 12 45 83) o 'salir': ").strip()
        if entrada.lower() in ("salir", "exit", "q"):
            break
        entrada = entrada.replace(",", " ").replace("-", " ")
        try:
            numeros = sorted({int(x) for x in entrada.split()})
            if not all(0 <= n <= 99 for n in numeros):
                print("Solo numeros entre 0 y 99\n"); continue
        except ValueError:
            print("Entrada invalida.\n"); continue
        mostrar_prediccion(numeros, b1_a_fechas, df)

def jugar_auto(b1_a_fechas, df):
    print("=== METODO 1: AUTOMATICO DEL DIA ===")
    print("Scrapea resultados de hoy y predice los B1s que faltan\n")
    pool = scrapear_hoy()
    if not pool:
        print("No se pudieron obtener resultados.")
        return
    print(f"B1s encontrados hoy ({len(pool)}): {pool}\n")
    mostrar_prediccion(pool, b1_a_fechas, df)

def scrapear_fecha(fecha):
    import json
    fecha_str = fecha.strftime("%Y-%m-%d")
    url = f"https://enloteria.com/resultados-loterias-{fecha_str}"
    print(f"Scrapeando {url} ...")
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        resp.encoding = "utf-8"
    except Exception as e:
        print(f"Error de conexion: {e}")
        return []
    m = re.search(r'<script type="application/ld\+json">(.*?)</script>', resp.text, re.DOTALL)
    if not m:
        print("No se encontro JSON-LD en la pagina.")
        return []
    try:
        data = json.loads(m.group(1))
    except Exception as e:
        print(f"Error parseando JSON: {e}")
        return []
    eventos = data.get("@graph", []) if isinstance(data, dict) and "@graph" in data else (data if isinstance(data, list) else [])
    loterias = []
    for ev in eventos:
        if not isinstance(ev, dict) or ev.get("@type") != "Event":
            continue
        props = ev.get("additionalProperty")
        if not props:
            continue
        b1 = None
        for p in props:
            if isinstance(p, dict) and p.get("name") == "Primer Premio":
                b1 = int(p["value"])
                break
        if b1 is None:
            continue
        nombre = ev.get("name", "")
        inicio = ev.get("startDate", "")
        loterias.append((nombre, inicio, b1))
    if not loterias:
        print(f"No se encontraron sorteos en {fecha_str}.")
        return []
    loterias.sort(key=lambda x: x[1])
    print(f"Encontrados {len(loterias)} sorteos: {[b1 for _, _, b1 in loterias]}")
    return [b1 for _, _, b1 in loterias]

def scrapear_hoy():
    return scrapear_fecha(date.today())

def analizar_decenas(numeros):
    decenas = {}
    conjunto = set(numeros)
    for d in range(10):
        inicio = d * 10
        fin = inicio + 9
        salieron = sorted([n for n in numeros if inicio <= n <= fin])
        faltaron = sorted([n for n in range(inicio, fin + 1) if n not in conjunto])
        inversos = {}
        for n in faltaron:
            inv = inverso(n)
            if inv in conjunto:
                inversos[n] = inv
        if salieron or inversos:
            decenas[d] = {"rango": f"{inicio:02d}-{fin}", "salieron": salieron, "faltaron": faltaron, "inversos": inversos}
    return decenas

def jugar_anguila(df):
    print("=== METODO ANGUILA ===")
    print("Muestra los B1 que mas salen el mismo dia en Anguilla\n")
    ang = df[df["loteria"].str.contains("Anguilla", case=False, na=False)].copy()
    if ang.empty:
        print("No hay datos de Anguilla.")
        return
    ang["horario"] = ang["loteria"].str.replace("Anguilla", "", case=False).str.strip()
    while True:
        entrada = input("Numeros B1 de Anguilla (0-99, ej: 12 45 83) o 'salir': ").strip()
        if entrada.lower() in ("salir", "exit", "q"):
            break
        entrada = entrada.replace(",", " ").replace("-", " ")
        try:
            numeros = sorted({int(x) for x in entrada.split()})
            if not all(0 <= n <= 99 for n in numeros):
                print("Solo numeros entre 0 y 99\n"); continue
        except ValueError:
            print("Entrada invalida.\n"); continue
        pool = set(numeros)
        for n in numeros:
            pool.add(inverso(n))
        match = ang[ang["b1"].isin(pool)]
        if match.empty:
            print("Ninguno de esos numeros ha salido en B1 de Anguilla.\n")
            continue
        fechas = set(match["fecha"])
        rows = ang[ang["fecha"].isin(fechas)]
        contador = Counter()
        horarios_por_num = defaultdict(set)
        for _, row in rows.iterrows():
            b1 = int(row["b1"])
            contador[b1] += 1
            horarios_por_num[b1].add(row["horario"])
        print(f"\n--- Anguila B1={numeros} ---")
        print(f"{len(match)} coincidencias en {len(fechas)} dias")
        print(f"Total sorteos Anguilla en esos dias: {len(rows)}")
        print(f"\n{'#':<5}{'Frec':<8}{'%':<8}Horarios")
        print("-" * 40)
        for num, count in contador.most_common(10):
            pct = count / len(fechas) * 100
            hrs = ", ".join(sorted(horarios_por_num[num])[:3])
            if len(horarios_por_num[num]) > 3:
                hrs += "..."
            print(f"{num:<5}{count:<8}{pct:.1f}%{hrs:<20}")
        print()

def mostrar_prediccion(numeros, b1_a_fechas, df):
    contador, fechas, max_count, mejores_pales = predecir_b1(numeros, b1_a_fechas, df)
    print(f"\n--- Pool B1={numeros} ---")
    print(f"Fecha(s) con max coincidencias: {len(fechas)} | {max_count}/{len(numeros)}")
    if fechas:
        print(f"Fechas: {sorted(fechas)[:5]}")
    print()
    if contador:
        print(f"{'#':<5}{'Frec':<8}{'%':<8}{'Mejor pale':<14}")
        print("-" * 35)
        for num, count in contador.most_common(10):
            pct = count / len(fechas) * 100
            pal_str = ""
            if num in mejores_pales:
                pn, pc = mejores_pales[num]
                pal_str = f"+{pn} ({pc})"
            print(f"{num:<5}{count:<8}{pct:.1f}%{pal_str:<14}")
    else:
        print("Sin candidatos.")
    print()

def obtener_calientes(df, top_n=10):
    b1_counts = df["b1"].value_counts()
    total = b1_counts.sum()
    hot = [(int(num), int(count), count / total * 100) for num, count in b1_counts.head(top_n).items()]
    cold = [(int(num), int(count), count / total * 100) for num, count in b1_counts.tail(top_n).items()]
    return hot, cold, total

def pares_frecuentes(df, top_n=10):
    b1_b2 = df.groupby(["b1", "b2"]).size().reset_index(name="freq").sort_values("freq", ascending=False).head(top_n)
    b1_b3 = df.groupby(["b1", "b3"]).size().reset_index(name="freq").sort_values("freq", ascending=False).head(top_n)
    b1_b2_pairs = [(int(r["b1"]), int(r["b2"]), int(r["freq"])) for _, r in b1_b2.iterrows()]
    b1_b3_pairs = [(int(r["b1"]), int(r["b3"]), int(r["freq"])) for _, r in b1_b3.iterrows()]
    return b1_b2_pairs, b1_b3_pairs

def cargar_secuencias(ruta):
    secuencias = []
    with open(ruta, encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea:
                continue
            nums = []
            for tok in linea.split("-"):
                tok = tok.strip()
                if tok == "" or not tok.isdigit():
                    continue
                nums.append(int(tok))
            if nums:
                secuencias.append(nums)
    return secuencias

def analizar_secuencias(secuencias, resultados):
    res_set = set(resultados)
    for n in resultados:
        res_set.add(inverso(n))
    resultados_por_secuencia = []
    for idx, seq in enumerate(secuencias):
        acertados = []
        faltantes = []
        for n in seq:
            if n in res_set or inverso(n) in res_set:
                acertados.append(n)
            else:
                faltantes.append(n)
        resultados_por_secuencia.append({
            "id": idx,
            "secuencia": seq,
            "num_acertados": len(acertados),
            "total": len(seq),
            "acertados": acertados,
            "faltantes": faltantes,
        })
    resultados_por_secuencia.sort(key=lambda x: (-x["num_acertados"], x["total"]))
    return resultados_por_secuencia

def numeros_atrasados(df, dias=7):
    desde = date.today() - timedelta(days=dias)
    df_filtrado = df[df["fecha"] >= desde]
    salidos = set(df_filtrado["b1"].dropna().astype(int))
    atrasados = [n for n in range(100) if n not in salidos]
    return atrasados, len(salidos), len(df_filtrado)

def normalizar_loteria(nombre):
    return re.sub(r"(\d)\s+(AM|PM)", r"\1\2", nombre, flags=re.IGNORECASE)

def anguila_horarios_ordenados():
    return ["8AM", "9AM", "10AM", "11AM", "12PM", "1PM", "2PM", "3PM", "4PM", "5PM", "6PM", "7PM", "8PM", "9PM", "10PM"]

def _hora_a_24h(tag):
    m = re.match(r"(\d+)(AM|PM)", tag.strip(), re.IGNORECASE)
    if not m:
        return None
    h = int(m.group(1))
    if m.group(2).upper() == "PM" and h != 12:
        h += 12
    if m.group(2).upper() == "AM" and h == 12:
        h = 0
    return h

def precomputar_cache_anguila(df):
    ang = df[df["loteria"].str.contains("Anguilla", case=False, na=False)].copy()
    if ang.empty:
        return {}, {}
    ang["norm"] = ang["loteria"].apply(normalizar_loteria)

    horarios = anguila_horarios_ordenados()
    tag_fecha_b1 = defaultdict(dict)
    for _, row in ang.iterrows():
        for t in horarios:
            if row["norm"].endswith(t):
                tag_fecha_b1[t][row["fecha"]] = int(row["b1"])
                break

    cache = {}
    dias_cache = {}
    for tag in horarios[:-1]:
        sig_tag = horarios[horarios.index(tag) + 1]
        sig_fecha_b1 = tag_fecha_b1.get(sig_tag, {})

        for n in range(100):
            pool = {n, inverso(n)}
            fechas = {f for f, b in tag_fecha_b1[tag].items() if b in pool}
            if not fechas:
                continue

            counter = Counter()
            for f in fechas:
                if f in sig_fecha_b1:
                    counter[sig_fecha_b1[f]] += 1

            if counter:
                cache[(tag, n)] = counter
                dias_cache[(tag, n)] = len(fechas)

    return cache, dias_cache

def predecir_anguila_siguiente(b1_actual, horario_tag, df, cache=None, dias_cache=None):
    h_actual = _hora_a_24h(horario_tag)
    if h_actual is None or h_actual >= 22:
        return None, None, 0
    h_sig = h_actual + 1
    horarios = anguila_horarios_ordenados()
    sig_tag = [t for t in horarios if _hora_a_24h(t) == h_sig]
    if not sig_tag:
        return None, None, 0
    sig_tag = sig_tag[0]

    if cache is not None:
        key = (horario_tag, b1_actual)
        if key not in cache:
            key = (horario_tag, inverso(b1_actual))
            if key not in cache:
                return None, sig_tag, 0
        total_dias = dias_cache.get(key, max(sum(cache[key].values()), 1)) if dias_cache else max(sum(cache[key].values()), 1)
        return cache[key], sig_tag, total_dias

    ang_norm = df[df["loteria"].str.contains("Anguilla", case=False, na=False)].copy()
    if ang_norm.empty:
        return None, None, 0
    ang_norm["norm"] = ang_norm["loteria"].apply(normalizar_loteria)

    pool = {b1_actual, inverso(b1_actual)}
    curr = ang_norm[ang_norm["norm"].str.endswith(horario_tag, na=False) & ang_norm["b1"].isin(pool)]
    if curr.empty:
        return None, None, 0

    fechas = set(curr["fecha"])
    sig = ang_norm[ang_norm["norm"].str.endswith(sig_tag, na=False) & ang_norm["fecha"].isin(fechas)]
    if sig.empty:
        return None, sig_tag, 0

    contador = Counter(int(b1) for b1 in sig["b1"])
    return contador, sig_tag, len(fechas)

def menu():
    print("\nSelecciona metodo:")
    print("  1 - Automatico del dia (scrapea + predice)")
    print("  2 - Manual (pool de B1s)")
    print("  3 - Acompanantes B2/B3")
    print("  4 - Anguila (B1 mismo dia)")
    print("  0 - Salir")
    return input("Opcion (0/1/2/3/4): ").strip()

if __name__ == "__main__":
    print("Cargando datos...")
    df = cargar_datos()
    b1_a_fechas = construir_indices(df)
    print(f"Registros: {len(df):,}\n")
    while True:
        op = menu()
        if op == "0":
            print("Hasta luego.")
            break
        elif op == "1":
            jugar_auto(b1_a_fechas, df)
        elif op == "2":
            jugar_b1(b1_a_fechas, df)
        elif op == "3":
            jugar_b2b3(b1_a_fechas, df)
        elif op == "4":
            jugar_anguila(df)
        else:
            print("Opcion invalida.")
