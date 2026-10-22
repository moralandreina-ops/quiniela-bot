"""Smoke test: SUPER PALE HOY vs MAÑANA (sin Telegram)."""
from datetime import timedelta

from analisis_quinielas import cargar_datos, hoy_dr, super_pale_dia, super_pale_dia_como_hoy
import bot_quinielas as b


def main():
    df = cargar_datos()
    hoy = hoy_dr()
    manana = hoy + timedelta(days=1)

    print("HOY:", hoy, "| MAÑANA:", manana)
    print("Botones:", [x[0].text for x in b.teclado_super_pale().inline_keyboard])

    for etiqueta, fecha, fn in (
        (None, hoy, lambda: super_pale_dia_como_hoy(df)),
        ("MAÑANA", manana, lambda: super_pale_dia(df, manana)),
    ):
        contador, fecha_out, total = fn()
        print("\n" + "=" * 40)
        print(f"fecha_out={fecha_out} | historial={total} sorteos")
        if contador is None:
            print("SIN DATOS")
            continue
        print(b.formatear_super_pale(contador, fecha_out, total, etiqueta=etiqueta))
        # Sanity: el contador solo tiene pares (n<=inverso)
        assert all(k == min(k, (k % 10) * 10 + k // 10) for k in contador)
        # Sin look-ahead: ninguna fecha del historial es >= fecha
        s = __import__("pandas").to_datetime(df["fecha"])
        mask = ((s.dt.month == fecha_out.month) & (s.dt.day == fecha_out.day)
                & (s.dt.date < fecha_out))
        print(f"  filas usadas: {int(mask.sum())} | total contador: {sum(contador.values())}")
        assert int(mask.sum()) == sum(contador.values())


if __name__ == "__main__":
    main()
