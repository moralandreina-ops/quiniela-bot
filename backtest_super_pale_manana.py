"""
Backtest SUPER PALE HOY vs SUPER PALE DE MANANA (jugado un dia antes)
=====================================================================

Que mide (walk-forward, sin look-ahead: el pool de un dia D solo usa
sorteos con fecha < D):

  A) HOY             -> pool del mismo mes/dia que D, jugado el dia D.
  B) MANANA 1D ANTES -> pool del mismo mes/dia que D+1, jugado el dia D
                        (lo que muestra el boton "SUPER PALE DE MANANA" hoy).
  C) MANANA EN SU DIA-> pool del mismo mes/dia que D+1, jugado el dia D+1
                        (referencia: el metodo en su fecha natural).

Metricas por sorteo (loteria-dia):
  - bolo      : el B1 (agrupado con su inverso) esta en el top-10 de bolos.
  - par_b1    : el B1 esta entre los numeros de los 10 pares.
  - pale_real : los DOS numeros de alguno de los 10 pares salieron en
                B1/B2/B3 del MISMO sorteo (condicion real de ganar el pale).

Baselines:
  - bolo: 10/55 = 18.18% (00-99 colapsan a 55 clases al agrupar inversos).
  - par_b1 y pale_real: se estiman empiricamente con predicciones aleatorias
    del mismo tamano sobre los mismos sorteos (mas justo que una formula).
"""
import os
import random
import sys
from collections import Counter, defaultdict
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analisis_quinielas import cargar_datos, super_pale_pares, _par_key

N_BOLOS = 10
N_PARES = 10
MIN_HIST = 20
N_RANDOM = 300
# Clases reales tras agrupar inversos (00-99 -> 55): 00-09, 11-19, 22-29, ...
CLASES_LISTA = sorted({_par_key(n) for n in range(100)})
CLASES = len(CLASES_LISTA)


def pools_por_mes_dia(df):
    pools = defaultdict(list)
    for f, b in zip(df["fecha"], df["b1"]):
        pools[(f.month, f.day)].append((f, int(b)))
    return pools


def construir_prediccion(pool, fecha_corte):
    hist = [b for f, b in pool if f < fecha_corte]
    if len(hist) < MIN_HIST:
        return None
    contador = Counter(_par_key(b) for b in hist)
    bolos = {k for k, _ in contador.most_common(N_BOLOS)}
    pares = super_pale_pares(contador, N_PARES)
    claves_par = {k for par in pares for k in par}
    return {"n_hist": len(hist), "bolos": bolos, "pares": pares,
            "claves_par": claves_par}


def nuevo():
    return {"sorteos": 0, "dias": 0, "hb": 0, "hp": 0, "hpr": 0,
            "base_par": 0.0, "dias_pale": 0}


def acumular(acc, clave, n, hb, hp, hpr, base_par, pale):
    d = acc[clave]
    d["sorteos"] += n
    d["dias"] += 1
    d["hb"] += hb
    d["hp"] += hp
    d["hpr"] += hpr
    d["base_par"] += base_par
    d["dias_pale"] += 1 if pale else 0


def z_vs(p, base, n):
    p0 = base / 100
    se = (p0 * (1 - p0) / n) ** 0.5 * 100
    return (p - base) / se if se else 0.0


def bloque(titulo, acc, orden, base_bolo):
    print(f"\n{titulo}")
    print(f"  {'':<13s} {'Sorteos':>8s} {'Bolo%':>8s} {'z':>6s}"
          f" {'ParB1%':>8s} {'ParAzar%':>9s} {'PaleReal%':>10s}")
    print("  " + "-" * 68)
    filas = []
    for k in orden:
        if k not in acc or not acc[k]["sorteos"]:
            continue
        d = acc[k]
        pb = d["hb"] / d["sorteos"] * 100
        pp = d["hp"] / d["sorteos"] * 100
        pr = d["hpr"] / d["sorteos"] * 100
        filas.append((k, d, pb, z_vs(pb, base_bolo, d["sorteos"]), pp, pr))
    for k, d, pb, z, pp, pr in filas:
        print(f"  {k:<13s} {d['sorteos']:>8d} {pb:>7.2f}% {z:>+6.2f}"
              f" {pp:>7.2f}% {d['base_par']/d['sorteos']*100:>8.2f}%"
              f" {pr:>9.2f}%")


def main():
    random.seed(7)
    print("Cargando datos...")
    df = cargar_datos()
    fechas = sorted(set(df["fecha"]))
    print(f"  {len(df):,} registros | {fechas[0]} -> {fechas[-1]} | "
          f"{df['loteria'].nunique()} loterias")

    pools = pools_por_mes_dia(df)

    # Sorteos con sus 3 bolas (clases con inverso)
    sorteos = []
    por_fecha = defaultdict(list)
    for f, lot, b1, b2, b3 in zip(df["fecha"], df["loteria"], df["b1"],
                                  df["b2"], df["b3"]):
        clases = {_par_key(int(b1)), _par_key(int(b2)), _par_key(int(b3))}
        sorteos.append((f, lot, _par_key(int(b1)), clases))
        por_fecha[f].append((lot, _par_key(int(b1)), clases))

    desde = fechas[0].replace(year=fechas[0].year + 1, month=1, day=1)
    hasta = fechas[-1] - timedelta(days=1)
    dias_test = [f for f in fechas if desde <= f <= hasta]
    print(f"  Dias de test: {len(dias_test)} ({dias_test[0]} -> {dias_test[-1]})\n")

    # ---- Baseline aleatorio (mismas metricas, prediccion al azar) ----
    def prediccion_aleatoria():
        clases = random.sample(CLASES_LISTA, 2 * N_PARES)
        pares = [(clases[2 * i], clases[2 * i + 1]) for i in range(N_PARES)]
        return {"bolos": set(random.sample(CLASES_LISTA, N_BOLOS)),
                "claves_par": set(clases), "pares": pares}

    muestra = [s for s in sorteos if desde <= s[0] <= hasta]
    sum_b = sum_p = sum_pr = 0
    for _ in range(N_RANDOM):
        pr = prediccion_aleatoria()
        for _f, _lot, k, clases in muestra:
            sum_b += 1 if k in pr["bolos"] else 0
            sum_p += 1 if k in pr["claves_par"] else 0
            sum_pr += 1 if any(a in clases and b in clases for a, b in pr["pares"]) else 0
    n_m = len(muestra)
    base_bolo = sum_b / N_RANDOM / n_m * 100
    base_par = sum_p / N_RANDOM / n_m * 100
    base_pale = sum_pr / N_RANDOM / n_m * 100
    print(f"Baseline aleatorio sobre {n_m:,} sorteos ({N_RANDOM} simulaciones):")
    print(f"  bolo {base_bolo:.2f}% | par_b1 {base_par:.2f}% | "
          f"pale_real {base_pale:.3f}%\n")

    metodos = {m: defaultdict(nuevo) for m in
               ("HOY (jugado hoy)", "MANANA 1D ANTES", "MANANA EN SU DIA")}
    tasas_dia = {m: [] for m in metodos}  # (fecha, dow, tasa_bolo_dia)
    por_loteria = {m: defaultdict(nuevo) for m in metodos}
    por_dow_juego = {m: defaultdict(nuevo) for m in metodos}
    por_dow_objetivo = {m: defaultdict(nuevo) for m in metodos}
    por_mes_juego = {m: defaultdict(nuevo) for m in metodos}
    ultimo_anio = {m: nuevo() for m in metodos}
    limite_reciente = fechas[-1] - timedelta(days=365)
    MESES_ES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
                "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    DOW_ES = {"Monday": "Lunes", "Tuesday": "Martes", "Wednesday": "Miercoles",
              "Thursday": "Jueves", "Friday": "Viernes", "Saturday": "Sabado",
              "Sunday": "Domingo"}

    def registrar(metodo, claves, sorteos_dia, pred):
        n = len(sorteos_dia)
        hb = sum(1 for _l, k, _c in sorteos_dia if k in pred["bolos"])
        hp = sum(1 for _l, k, _c in sorteos_dia if k in pred["claves_par"])
        hpr = sum(1 for _l, _k, c in sorteos_dia
                  if any(a in c and b in c for a, b in pred["pares"]))
        pale = any(a in {k for _l, k, _c in sorteos_dia}
                   and b in {k for _l, k, _c in sorteos_dia}
                   for a, b in pred["pares"])
        base_par_dia = len(pred["claves_par"]) / CLASES * n
        for acc, clave in claves:
            acumular(acc[metodo], clave, n, hb, hp, hpr, base_par_dia, pale)
        return n, hb, hp, hpr

    for d in dias_test:
        obj = d + timedelta(days=1)
        p_hoy = construir_prediccion(pools.get((d.month, d.day), []), d)
        p_man = construir_prediccion(pools.get((obj.month, obj.day), []), d)
        sd = por_fecha.get(d, [])
        so = por_fecha.get(obj, [])
        dow, dow_obj = DOW_ES[d.strftime("%A")], DOW_ES[obj.strftime("%A")]
        mes = MESES_ES[d.month - 1]

        if p_hoy and sd:
            n, hb, hp, hpr = registrar(
                "HOY (jugado hoy)",
                [(metodos, "TOTAL"), (por_dow_juego, dow),
                 (por_dow_objetivo, dow_obj), (por_mes_juego, mes)], sd, p_hoy)
            tasas_dia["HOY (jugado hoy)"].append((d, dow, hb / n))
            t = ultimo_anio["HOY (jugado hoy)"]
            if d >= limite_reciente:
                t["sorteos"] += n; t["dias"] += 1; t["hb"] += hb
                t["hp"] += hp; t["hpr"] += hpr
            for lot, k, _c in sd:
                q = por_loteria["HOY (jugado hoy)"][lot]
                q["sorteos"] += 1
                q["hb"] += 1 if k in p_hoy["bolos"] else 0

        if p_man and sd:
            n, hb, hp, hpr = registrar(
                "MANANA 1D ANTES",
                [(metodos, "TOTAL"), (por_dow_juego, dow),
                 (por_dow_objetivo, dow_obj), (por_mes_juego, mes)], sd, p_man)
            tasas_dia["MANANA 1D ANTES"].append((d, dow, hb / n))
            t = ultimo_anio["MANANA 1D ANTES"]
            if d >= limite_reciente:
                t["sorteos"] += n; t["dias"] += 1; t["hb"] += hb
                t["hp"] += hp; t["hpr"] += hpr
            for lot, k, _c in sd:
                q = por_loteria["MANANA 1D ANTES"][lot]
                q["sorteos"] += 1
                q["hb"] += 1 if k in p_man["bolos"] else 0

        if p_man and so:
            registrar("MANANA EN SU DIA",
                      [(metodos, "TOTAL"), (por_dow_objetivo, dow_obj)], so, p_man)

    # ---------------- GLOBAL ----------------
    print("=" * 78)
    print(f"RESULTADO GLOBAL  (azar medido: bolo {base_bolo:.2f}% | "
          f"par_b1 {base_par:.2f}% | pale_real {base_pale:.3f}%)")
    print("=" * 78)
    print(f"  {'Metodo':<18s} {'Sorteos':>8s} {'Bolo%':>7s} {'z':>6s}"
          f" {'ParB1%':>7s} {'PaleReal%':>10s} {'vsAzar':>8s}")
    print("  " + "-" * 70)
    for m, datos in metodos.items():
        t = nuevo()
        for d in datos.values():
            for k in t:
                t[k] += d[k]
        pb = t["hb"] / t["sorteos"] * 100
        pp = t["hp"] / t["sorteos"] * 100
        pr = t["hpr"] / t["sorteos"] * 100
        print(f"  {m:<18s} {t['sorteos']:>8d} {pb:>6.2f}% "
              f"{z_vs(pb, base_bolo, t['sorteos']):>+6.2f} {pp:>6.2f}% "
              f"{pr:>9.3f}% {pr/base_pale:>7.2f}x")

    print(f"\n  Ultimos 12 meses ({limite_reciente} -> {fechas[-1]}):")
    for m in ("HOY (jugado hoy)", "MANANA 1D ANTES"):
        t = ultimo_anio[m]
        pb = t["hb"] / t["sorteos"] * 100
        pr = t["hpr"] / t["sorteos"] * 100
        print(f"    {m:<18s} {t['sorteos']:>7d} sorteos | bolo {pb:5.2f}% "
              f"(z {z_vs(pb, base_bolo, t['sorteos']):+.2f}) | "
              f"pale_real {pr:5.3f}% ({pr/base_pale:.2f}x)")

    orden = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado",
             "Domingo"]
    print("\n" + "=" * 78)
    print("POR DIA DE LA SEMANA DEL DIA EN QUE SE JUEGA (el 'hoy')")
    print("=" * 78)
    for m in ("HOY (jugado hoy)", "MANANA 1D ANTES"):
        bloque(m, por_dow_juego[m], orden, base_bolo)

    print("\n" + "=" * 78)
    print("POR DIA DE LA SEMANA DEL DIA OBJETIVO (el dia del super pale)")
    print("=" * 78)
    for m in ("HOY (jugado hoy)", "MANANA 1D ANTES"):
        bloque(m, por_dow_objetivo[m], orden, base_bolo)

    print("\n" + "=" * 78)
    print("MANANA 1D ANTES - POR MES DEL DIA DE JUEGO")
    print("=" * 78)
    bloque("", por_mes_juego["MANANA 1D ANTES"], MESES_ES, base_bolo)

    print("\n" + "=" * 78)
    print("POR LOTERIA - MANANA 1D ANTES (>=200 sorteos, bolo B1)")
    print("=" * 78)
    filas = []
    for lot, t in por_loteria["MANANA 1D ANTES"].items():
        if t["sorteos"] < 200:
            continue
        p = t["hb"] / t["sorteos"] * 100
        filas.append((lot, t["sorteos"], p, z_vs(p, base_bolo, t["sorteos"])))
    filas.sort(key=lambda x: x[2], reverse=True)
    print(f"  {'Loteria':<26s} {'Sorteos':>8s} {'Bolo%':>8s} {'z':>7s}")
    print("  " + "-" * 52)
    for lot, n, p, z in filas[:12]:
        print(f"  {lot:<26s} {n:>8d} {p:>7.2f}% {z:>+7.2f}")
    print("  ...")
    for lot, n, p, z in filas[-6:]:
        print(f"  {lot:<26s} {n:>8d} {p:>7.2f}% {z:>+7.2f}")

    # ---------------- Comparativa directa HOY vs MANANA ----------------
    gana_hoy = gana_man = empate = 0
    dif = []
    for d in dias_test:
        obj = d + timedelta(days=1)
        ph = construir_prediccion(pools.get((d.month, d.day), []), d)
        pm = construir_prediccion(pools.get((obj.month, obj.day), []), d)
        sd = por_fecha.get(d, [])
        if not ph or not pm or not sd:
            continue
        hh = sum(1 for _l, k, _c in sd if k in ph["bolos"])
        hm = sum(1 for _l, k, _c in sd if k in pm["bolos"])
        dif.append(hm - hh)
        if hh > hm:
            gana_hoy += 1
        elif hm > hh:
            gana_man += 1
        else:
            empate += 1
    tot = len(dif)
    media = sum(dif) / tot
    var = sum((x - media) ** 2 for x in dif) / tot
    print("\n" + "=" * 78)
    print("COMPARATIVA DIRECTA HOY vs MANANA (mismos sorteos del dia D)")
    print("=" * 78)
    print(f"  Gana HOY: {gana_hoy} dias ({gana_hoy/tot*100:.1f}%) | "
          f"Gana MANANA: {gana_man} ({gana_man/tot*100:.1f}%) | "
          f"Empate: {empate} ({empate/tot*100:.1f}%)  [n={tot}]")
    print(f"  Diferencia media de aciertos/dia (manana - hoy): {media:+.3f} "
          f"(SE {var**0.5/tot**0.5:.3f}, z {media/(var**0.5/tot**0.5):+.2f})")

    # ---------------- Significancia a nivel DIA + estabilidad ----------------
    print("\n" + "=" * 78)
    print("SIGNIFICANCIA A NIVEL DIA (evita inflar n con 43 sorteos/dia)")
    print("=" * 78)
    print(f"  {'Metodo':<18s} {'Dias':>5s} {'Media/dia':>10s} {'SE':>6s}"
          f" {'z vs azar':>10s}")
    print("  " + "-" * 54)
    for m, filas_dia in tasas_dia.items():
        if not filas_dia:
            continue
        xs = [x[2] * 100 for x in filas_dia]
        mu = sum(xs) / len(xs)
        sd = (sum((x - mu) ** 2 for x in xs) / (len(xs) - 1)) ** 0.5
        se = sd / len(xs) ** 0.5
        print(f"  {m:<18s} {len(xs):>5d} {mu:>9.2f}% {se:>5.2f} "
              f"{(mu-base_bolo)/se:>+10.2f}")

    print("\nEstabilidad por dia de la semana (tasa media diaria del bolo,"
          " partido en 2 mitades):")
    mitades = [(fechas[len(fechas)//2] if False else dias_test[0],
                dias_test[len(dias_test)//2 - 1],
                dias_test[len(dias_test)//2], dias_test[-1])]
    print(f"  M1: {mitades[0][0]} -> {mitades[0][1]} | "
          f"M2: {mitades[0][2]} -> {mitades[0][3]}")
    print(f"  {'Dia':<11s} {'M1':>9s} {'n1':>5s} {'M2':>9s} {'n2':>5s}"
          f" {'Dif':>7s}")
    print("  " + "-" * 52)
    filas_dia = tasas_dia["MANANA 1D ANTES"]
    for dow_nombre in orden:
        m1 = [x[2] * 100 for x in filas_dia
              if x[1] == dow_nombre and x[0] <= mitades[0][1]]
        m2 = [x[2] * 100 for x in filas_dia
              if x[1] == dow_nombre and x[0] >= mitades[0][2]]
        if not m1 or not m2:
            continue
        a, b = sum(m1) / len(m1), sum(m2) / len(m2)
        print(f"  {dow_nombre:<11s} {a:>8.2f}% {len(m1):>5d} {b:>8.2f}%"
              f" {len(m2):>5d} {b-a:>+6.2f}")

    print(f"\n  Referencia azar: {base_bolo:.2f}%")


if __name__ == "__main__":
    main()
