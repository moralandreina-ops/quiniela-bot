"""
Backtest walk-forward del metodo Powerball "DESDE ULTIMO SORTEO" (boton METODO 1).

Sin look-ahead: para cada sorteo i la prediccion se arma solo con los sorteos 0..i
y se valida contra el sorteo i+1. Compara contra el azar real (5/69 blancos, 1/26 Powerball)
y contra un metodo1 aleatorio de control.
"""

import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from analisis_quinielas import (
    cargar_powerball,
    predecir_powerball_desde_ultimo,
    POWERBALL_WHITE_COUNT,
    POWERBALL_WHITE_MAX,
    POWERBALL_RED_MAX,
)

VENTANAS = [3, 5, 10, 20]
MIN_HISTORIAL = 300


def backtest(ventana):
    historial = cargar_powerball()
    aciertos_blancos = 0
    aciertos_pb = 0
    muestras_pb = 0
    predicciones = 0
    repetidos_base = 0
    suma_muestras = 0

    for i in range(MIN_HISTORIAL, len(historial) - 1):
        pred = predecir_powerball_desde_ultimo(
            ventana=ventana,
            minimo_muestras=20,
            historial=historial[: i + 1],
        )
        if pred is None:
            continue
        siguiente_blancos, siguiente_rojo = historial[i + 1][1]
        aciertos_blancos += len(set(pred["blancos"]) & set(siguiente_blancos))
        aciertos_pb += int(pred["rojo"] == siguiente_rojo)
        muestras_pb += 1
        predicciones += 1
        suma_muestras += pred["muestras"]
        repetidos_base += len(set(pred["blancos"]) & set(pred["base_blancos"]))

    azar_blancos = POWERBALL_WHITE_COUNT / POWERBALL_WHITE_MAX
    azar_pb = 1 / POWERBALL_RED_MAX
    return {
        "ventana": ventana,
        "predicciones": predicciones,
        "muestras_prom": suma_muestras / predicciones if predicciones else 0,
        "blancos_pct": aciertos_blancos / (predicciones * POWERBALL_WHITE_COUNT) if predicciones else 0,
        "azar_blancos": azar_blancos,
        "pb_pct": aciertos_pb / muestras_pb if muestras_pb else 0,
        "azar_pb": azar_pb,
        "repetidos_base": repetidos_base / (predicciones * POWERBALL_WHITE_COUNT) if predicciones else 0,
    }


def principales(resultados, clave, azar, etiqueta):
    print(f"\n{etiqueta}")
    print(f"{'ventana':>8} {'n':>6} {'blancos%':>10} {'azar%':>8} {'delta':>8} {'z':>7} {'PB%':>8} {'azarPB%':>9} {'muestras':>9} {'repite base%':>13}")
    for r in sorted(resultados, key=lambda x: -x[clave]):
        n = r["predicciones"]
        p = r["azar_blancos"]
        se_blancos = ((POWERBALL_WHITE_COUNT * p * (1 - p)) / n) ** 0.5 if n else 0
        z_blancos = (r["blancos_pct"] - p) / se_blancos if se_blancos else 0
        se_pb = (r["azar_pb"] * (1 - r["azar_pb"]) / n) ** 0.5 if n else 0
        z_pb = (r["pb_pct"] - r["azar_pb"]) / se_pb if se_pb else 0
        print(
            f"{r['ventana']:>8} {n:>6} {r['blancos_pct']*100:>10.2f} {r['azar_blancos']*100:>8.2f} "
            f"{(r['blancos_pct']-r['azar_blancos'])*100:>+8.2f} {z_blancos:>+7.2f} {r['pb_pct']*100:>8.2f} {r['azar_pb']*100:>9.2f} "
            f"{r['muestras_prom']:>9.0f} {r['repetidos_base']*100:>13.2f}   z(PB)={z_pb:+.2f}"
        )


if __name__ == "__main__":
    historial = cargar_powerball()
    if not historial:
        print("Sin historial. Ejecuta primero actualizar_powerball()")
        sys.exit(1)
    print(f"Historial: {len(historial)} sorteos, {historial[0][0]} -> {historial[-1][0]}")
    resultados = [backtest(v) for v in VENTANAS]
    principales(resultados, "blancos_pct", 5 / 69, "ACIERTO DE BLANCOS (top 5 de 69)")
