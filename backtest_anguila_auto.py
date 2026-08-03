"""
Backtest walk-forward del nuevo metodo ANGUILA AUTO (siguiente hora).
Reproduce exactamente predecir_anguila_auto:
  Parte A: siguiente hora mismo dia tras el B1 actual.
  Parte B: semilla = B1 de ayer en la siguiente hora -> numeros que lo sucedieron
           en Anguilla los 5 dias calendario siguientes.
Fusiona A+B en un ranking. Sin look-ahead: las ventanas de 5 dias solo se usan
cuando el dia 'futuro' de la ventana ya paso (cola deslizante de 5 dias).
"""
from collections import Counter, defaultdict, deque
from datetime import timedelta
from analisis_quinielas import cargar_datos, inverso, normalizar_loteria, anguila_horarios_ordenados


def main():
    df = cargar_datos()
    ang = df[df["loteria"].str.contains("Anguilla", case=False, na=False)].copy()
    ang["norm"] = ang["loteria"].apply(normalizar_loteria)
    horarios = anguila_horarios_ordenados()

    tag_fecha_b1 = defaultdict(dict)
    for _, row in ang.iterrows():
        for t in horarios:
            if row["norm"].endswith(t):
                tag_fecha_b1[t][row["fecha"]] = int(row["b1"])
                break

    b1_fecha = defaultdict(list)  # fecha -> lista de b1s de todos los horarios
    for t in horarios:
        for f, b in tag_fecha_b1[t].items():
            b1_fecha[f].append(b)

    dias = sorted(b1_fecha)
    stats = defaultdict(lambda: [0, 0, 0, 0])
    total = [0, 0, 0, 0]
    evaluadas = 0
    recientes = defaultdict(lambda: [0, 0])
    desde = dias[-1] - timedelta(days=30)

    counter_a = defaultdict(Counter)
    counter_b = defaultdict(Counter)
    ventana = deque()  # seeds (con inverso) de los ultimos 5 dias

    for d in dias:
        for tag in horarios[:-1]:
            if d not in tag_fecha_b1[tag]:
                continue
            tag_sig = horarios[horarios.index(tag) + 1]
            sig_fb = tag_fecha_b1.get(tag_sig, {})
            if d not in sig_fb:
                continue
            b1_actual = tag_fecha_b1[tag][d]
            b1s = sig_fb[d]
            b1_seed = sig_fb.get(d - timedelta(days=1))

            merged = Counter()
            ca = counter_a.get((tag, b1_actual))
            if ca is None:
                ca = counter_a.get((tag, inverso(b1_actual)))
            cb = None
            if b1_seed is not None:
                cb = counter_b.get(b1_seed)
                if cb is None:
                    cb = counter_b.get(inverso(b1_seed))
            if ca:
                merged.update(ca)
            if cb:
                merged.update(cb)

            if merged:
                evaluadas += 1
                top = [b for b, _ in merged.most_common()]
                top1 = top[0]
                top5 = set(top[:5])
                top10 = set(top[:10])
                hits = (
                    1 if (b1s == top1 or inverso(b1s) == top1) else 0,
                    1 if (b1s in top5 or inverso(b1s) in top5) else 0,
                    1 if b1s in top10 else 0,
                    1 if (b1s in top10 or inverso(b1s) in top10) else 0,
                )
                for idx in range(4):
                    stats[tag][idx] += hits[idx]
                    total[idx] += hits[idx]
                if d >= desde:
                    recientes[tag][0] += hits[3]
                    recientes[tag][1] += 1

        # Parte A: transiciones mismo dia (disponibles desde manana)
        for tag in horarios[:-1]:
            if d not in tag_fecha_b1[tag]:
                continue
            tag_sig = horarios[horarios.index(tag) + 1]
            sig_fb = tag_fecha_b1.get(tag_sig, {})
            if d not in sig_fb:
                continue
            b1 = tag_fecha_b1[tag][d]
            b1s = sig_fb[d]
            counter_a[(tag, b1)][b1s] += 1
            counter_a[(tag, inverso(b1))][b1s] += 1

        # Parte B: ventanas 5 dias (futuro dia = d) -> disponibles desde manana
        for g in ventana:
            for s in g:
                for b in b1_fecha[d]:
                    counter_b[s][b] += 1
        ventana.append(set(b1_fecha[d]) | {inverso(b) for b in b1_fecha[d]})
        if len(ventana) > 5:
            ventana.popleft()

    print("=== ANGUILA AUTO (A mismo dia + B semilla 5 dias) walk-forward ===")
    print("Muestras: %d transiciones | baseline top1=1%%, top5=5%%, top10=10%%\n" % evaluadas)
    print("  Top1 (exacto/inv): %d/%d = %.1f%%" % (total[0], evaluadas, total[0] / evaluadas * 100))
    print("  Top5 (exacto/inv): %d/%d = %.1f%%" % (total[1], evaluadas, total[1] / evaluadas * 100))
    print("  Top10 exacto:      %d/%d = %.1f%%" % (total[2], evaluadas, total[2] / evaluadas * 100))
    print("  Top10 +inverso:    %d/%d = %.1f%%" % (total[3], evaluadas, total[3] / evaluadas * 100))
    print("\nUltimos 30 dias (top10+inv):")
    for tag in horarios[:-1]:
        if tag in recientes and recientes[tag][1]:
            a = recientes[tag]
            print("  %s->%s: %d/%d = %.1f%%" % (tag, horarios[horarios.index(tag) + 1], a[0], a[1], a[0] / a[1] * 100))


if __name__ == "__main__":
    main()
