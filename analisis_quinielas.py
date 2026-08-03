import pandas as pd
from collections import Counter, defaultdict
import requests
import re
from datetime import date, timedelta
import os

_script_dir = os.path.dirname(os.path.abspath(__file__))
RUTA = os.path.join(_script_dir, "Resultados quinielas completo.xlsx")

LOTTERY_MAP = {
    "La Primera": "La Primera Dia",
    "La Primera Medio D\u00eda": "La Primera Dia",
    "La Primera Noche": "La Primera Noche",
    "Anguilla 1 PM": "Anguilla 1PM",
    "Anguilla 10 AM": "Anguilla 10AM",
    "Anguilla 6 PM": "Anguilla 6PM",
    "Anguilla 9 PM": "Anguilla 9PM",
    "La Suerte": "La Suerte Dia",
    "La Suerte D\u00eda": "La Suerte Dia",
    "La Suerte 6PM": "La Suerte Tarde",
    "La Suerte Tarde": "La Suerte Tarde",
    "LoteDom": "Quiniela Lotedom",
    "Loteka": "Quiniela Loteka",
    "Real": "Quiniela Real",
    "Quiniela Pal\u00e9": "Leidsa",
    "Georgia D\u00eda": "Georgia Dia",
    "King Lottery D\u00eda": "King Lottery Dia",
    "King Lottery Medio D\u00eda": "King Lottery Dia",
}

def inverso(n):
    return int(str(n).zfill(2)[::-1])

def cargar_datos():
    df = pd.read_excel(RUTA)
    df.columns = ["loteria", "fecha", "b1", "b2", "b3"]
    df["loteria"] = df["loteria"].map(lambda x: LOTTERY_MAP.get(x, x))
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

def scrapear_fecha_dict(fecha):
    import json
    if fecha == date.today():
        url = "https://enloteria.com/resultados-loterias-hoy"
    else:
        fecha_str = fecha.strftime("%Y-%m-%d")
        url = f"https://enloteria.com/resultados-loterias-{fecha_str}"
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        resp.encoding = "utf-8"
    except Exception:
        return {}
    m = re.search(r'<script type="application/ld\+json">(.*?)</script>', resp.text, re.DOTALL)
    if not m:
        return {}
    try:
        data = json.loads(m.group(1))
    except Exception:
        return {}
    eventos = data.get("@graph", []) if isinstance(data, dict) and "@graph" in data else (data if isinstance(data, list) else [])
    resultado = {}
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
        nombre_norm = LOTTERY_MAP.get(nombre, nombre)
        resultado[nombre_norm] = b1
    return resultado

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
                dias_cache[(tag, n)] = sum(counter.values())

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
    return contador, sig_tag, sum(contador.values())

def predecir_loteria_secuencia(loteria, df):
    from collections import Counter, defaultdict

    ultimo = None
    ultima_fecha = None

    scrape_hoy = obtener_scrape_hoy()
    if scrape_hoy and loteria in scrape_hoy:
        ultimo = scrape_hoy[loteria]
        ultima_fecha = date.today()

    ldf = df[df["loteria"] == loteria].sort_values("fecha")
    if ultimo is None:
        if len(ldf) < 2:
            return None, None, None, 0
        ultimo = int(ldf.iloc[-1]["b1"])
        ultima_fecha = ldf.iloc[-1]["fecha"]

    seq = defaultdict(Counter)
    b1_prev = None
    for _, row in ldf.iterrows():
        if b1_prev is not None:
            seq[b1_prev][int(row["b1"])] += 1
        b1_prev = int(row["b1"])

    if ultimo not in seq:
        return [], ultimo, ultima_fecha, 0

    siguientes = seq[ultimo]
    total = sum(siguientes.values())
    return siguientes.most_common(10), ultimo, ultima_fecha, total


def buscar_loterias(query, df):
    import re
    q = re.sub(r"[^a-z0-9]", "", query.lower())
    loterias = df["loteria"].unique()
    matches = []
    for l in sorted(loterias):
        l_norm = re.sub(r"[^a-z0-9]", "", l.lower())
        if q in l_norm:
            matches.append(l)
    return matches

LOTTERY_SCHEDULE = {
    "Quiniela Lotedom": 720, "La Primera Dia": 720,
    "Georgia Dia": 750, "King Lottery Dia": 750, "La Suerte Dia": 750,
    "New Jersey Tarde": 779, "Quiniela Real": 780, "Florida Dia": 810,
    "New York Tarde": 870, "Gana Más": 870,
    "La Suerte Tarde": 1080, "La Primera Noche": 1140,
    "King Lottery Noche": 1170, "Quiniela Loteka": 1200,
    "Leidsa": 1260, "Nacional Noche": 1260, "Florida Noche": 1290,
    "New York Noche": 1350, "New Jersey Noche": 1380, "Georgia Noche": 1410,
}

ANGUIILA_MINUTOS = {
    "8AM": 480, "9AM": 540, "10AM": 600, "11AM": 660,
    "12PM": 720, "1PM": 780, "2PM": 840, "3PM": 900,
    "4PM": 960, "5PM": 1020, "6PM": 1080, "7PM": 1140,
    "8PM": 1200, "9PM": 1260, "10PM": 1320
}

def metodo_final(df, anguila_cache=None, anguila_dias_cache=None):
    scrape = obtener_scrape_hoy()
    anguila_horarios = anguila_horarios_ordenados()

    hora_actual = None
    b1_anguila = None
    for i in range(len(anguila_horarios) - 1, -1, -1):
        tag = anguila_horarios[i]
        nombre_ang = f"Anguilla {tag}"
        nombre_norm = LOTTERY_MAP.get(nombre_ang, nombre_ang)
        if nombre_norm in scrape:
            hora_actual = tag
            b1_anguila = scrape[nombre_norm]
            break

    if hora_actual is None or b1_anguila is None:
        ang_hoy = [l for l in scrape if "anguilla" in l.lower()]
        return None, None, None, None, ang_hoy

    pred_acomp = Counter()
    pool = {b1_anguila, inverso(b1_anguila)}
    b1_a_fechas = construir_indices(df)
    fechas_match = set()
    for n in pool:
        fechas_match |= b1_a_fechas.get(n, set())
    if fechas_match:
        df_match = df[df["fecha"].isin(fechas_match) & df["b1"].isin(pool)]
        for _, row in df_match.iterrows():
            b2, b3 = int(row["b2"]), int(row["b3"])
            if b2 not in pool:
                pred_acomp[b2] += 1
            if b3 not in pool:
                pred_acomp[b3] += 1

    pred_ang, sig_tag, total_dias = predecir_anguila_siguiente(
        b1_anguila, hora_actual, df, anguila_cache, anguila_dias_cache
    )
    if pred_ang is None:
        pred_ang = Counter()

    pred_combinada = Counter()
    for n, c in pred_acomp.most_common(10):
        pred_combinada[n] += c * 2
    for n, c in pred_ang.most_common(10):
        pred_combinada[n] += c * 2

    return b1_anguila, hora_actual, sig_tag, pred_combinada.most_common(15), scrape


# Cache para scraping de hoy
_scrape_cache = {}
_scrape_cache_fecha = None

def obtener_scrape_hoy():
    """Devuelve los resultados de hoy. Usa cache si es del mismo dia, si no scrapea y guarda con fecha."""
    global _scrape_cache, _scrape_cache_fecha
    hoy = date.today()
    if _scrape_cache_fecha == hoy and _scrape_cache:
        return _scrape_cache
    try:
        scrape = scrapear_fecha_dict(hoy)
        if scrape:
            _scrape_cache = scrape
            _scrape_cache_fecha = hoy
            return scrape
    except Exception as e:
        print("Error scraping hoy: %s" % str(e))
    return {}

def repeticiones_hoy(df):
    """
    Números que se repiten HOY desde 8AM hasta 6:01PM.
    B1+B2+B3 de todas las loterías del día -> cuáles aparecen en múltiples loterías.
    Top 10 más repetidos.
    """
    manana_tarde = ['Anguilla 8AM', 'Anguilla 9AM', 'Anguilla 10AM', 'Anguilla 11AM',
                    'Anguilla 12PM', 'Anguilla 1PM', 'Anguilla 2PM', 'Anguilla 3PM',
                    'Anguilla 4PM', 'Anguilla 5PM',
                    'La Primera Dia', 'King Lottery Dia', 'La Suerte Dia', 'Georgia Dia',
                    'Quiniela Lotedom', 'Florida Dia', 'New Jersey Tarde',
                    'Florida Tarde', 'New York Tarde', 'Gana Mas', 'La Suerte Tarde']

    scrape = obtener_scrape_hoy()

    if not scrape:
        return [], {}
    
    todos_nums = []
    for nombre, b1 in scrape.items():
        if nombre in manana_tarde:
            todos_nums.append(b1)
            # Agregar B2/B3 del historial de hoy
            try:
                ldf = df[df["loteria"] == nombre].sort_values("fecha")
                if len(ldf) > 0:
                    ultimo = ldf.iloc[-1]
                    if int(ultimo["b1"]) == b1:
                        todos_nums.append(int(ultimo["b2"]))
                        todos_nums.append(int(ultimo["b3"]))
            except Exception:
                pass
    
    if not todos_nums:
        return [], scrape
    
    counter = Counter(todos_nums)
    # Top 10 más frecuentes (repiten o no)
    top10 = counter.most_common(10)
    
    return top10, scrape


def repeticiones_ayer(df):
    """
    Top 10 números de AYER (todos B1+B2+B3) que más se repiten.
    Esos números son candidatos a repetirse HOY después de 6PM.
    """
    ayer = date.today() - timedelta(days=1)
    df_ayer = df[df["fecha"] == ayer]
    
    if df_ayer.empty:
        return [], ayer
    
    # Todos los B1+B2+B3 de ayer
    todos_nums = []
    for _, row in df_ayer.iterrows():
        todos_nums.extend([int(row["b1"]), int(row["b2"]), int(row["b3"])])
    
    counter = Counter(todos_nums)
    top10 = counter.most_common(10)
    
    return top10, ayer


def repeticiones_2da_3ra_ayer(df):
    """
    Top 10 números de B2 y B3 de AYER (sin B1).
    Solo la 2da y 3ra bola de ayer -> candidatos a salir hoy.
    """
    ayer = date.today() - timedelta(days=1)
    df_ayer = df[df["fecha"] == ayer]
    
    if df_ayer.empty:
        return [], ayer
    
    # Solo B2 y B3 de ayer (sin B1)
    todos_nums = []
    for _, row in df_ayer.iterrows():
        todos_nums.extend([int(row["b2"]), int(row["b3"])])
    
    counter = Counter(todos_nums)
    top10 = counter.most_common(10)
    
    return top10, ayer


def metodo_super_kino():
    """
    Genera 2 combinaciones de 10 numeros para Super Kino TV.
    Combo 1 "Caliente": momentum reciente + frecuencia historica.
    Combo 2 "Equilibrado": numeros atrasados + frecuencia + momentum.
    Ambas con balance de decadas (max 2 por decada).
    """
    import csv
    _script_dir_local = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(_script_dir_local, "kino_tv_results.csv")
    if not os.path.exists(csv_path):
        return [], []

    data = {}
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            d = date.fromisoformat(row[0])
            nums = [int(x) for x in row[1:]]
            data[d] = nums

    if not data:
        return [], []

    sorted_dates = sorted(data.keys())

    freq = Counter()
    for nums in data.values():
        for n in nums:
            freq[n] += 1
    total = len(data)

    recent14 = sorted_dates[-14:]
    recent_freq = Counter()
    for d in recent14:
        for n in data[d]:
            recent_freq[n] += 1

    last_seen = {}
    for i, d in enumerate(sorted_dates):
        for n in data[d]:
            last_seen[n] = i

    max_overdue = max(len(sorted_dates) - 1 - last_seen.get(n, -1) for n in range(1, 81))
    max_freq = max(freq.get(n, 0) for n in range(1, 81))

    def _pick(weights, n_pick=10):
        scores = {}
        for n in range(1, 81):
            all_rate = freq.get(n, 0) / total
            rec_rate = recent_freq.get(n, 0) / len(recent14)
            momentum = rec_rate / all_rate if all_rate > 0 else 0
            overdue = len(sorted_dates) - 1 - last_seen.get(n, -1)
            mom_n = min(momentum / 2.5, 1.0)
            ov_n = overdue / max_overdue if max_overdue > 0 else 0
            fq_n = freq.get(n, 0) / max_freq if max_freq > 0 else 0
            scores[n] = weights[0] * mom_n + weights[1] * ov_n + weights[2] * fq_n

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        picked = set()
        decades = Counter()
        for n, _ in ranked:
            if len(picked) >= n_pick:
                break
            decade = n // 10
            if decades[decade] >= 2:
                continue
            picked.add(n)
            decades[decade] += 1
        for n, _ in ranked:
            if len(picked) >= n_pick:
                break
            picked.add(n)
        return sorted(picked)

    combo1 = _pick((0.50, 0.20, 0.30))
    combo2 = _pick((0.30, 0.40, 0.30))

    return combo1, combo2


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
