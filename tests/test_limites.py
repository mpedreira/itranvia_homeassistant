"""Pruebas de los cálculos de límite de consultas (sin Home Assistant)."""
import importlib.util
import pathlib
import unittest

BASE = pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "itranvias_coruna"
spec = importlib.util.spec_from_file_location("itr_const", BASE / "const.py")
const = importlib.util.module_from_spec(spec)
spec.loader.exec_module(const)


class TestLimites(unittest.TestCase):
    def test_intervalo_minimo_sin_pausa(self):
        self.assertEqual(const.intervalo_minimo(1), 55)
        self.assertEqual(const.intervalo_minimo(2), 109)
        self.assertEqual(const.intervalo_minimo(3), 163)

    def test_intervalo_minimo_con_pausa(self):
        h = const.horas_activas(const.DEFAULT_PAUSA_DESDE, const.DEFAULT_PAUSA_HASTA)
        self.assertEqual(h, 19.0)
        self.assertEqual(const.intervalo_minimo(2, h), 86)
        self.assertEqual(const.intervalo_minimo(3, h), 129)

    def test_defecto_valido_hasta_tres_paradas_no_hasta_cuatro_sin_pausa(self):
        self.assertFalse(const.excede_limite([(const.DEFAULT_INTERVALO, 24.0)] * 3))
        self.assertTrue(const.excede_limite([(const.DEFAULT_INTERVALO, 24.0)] * 4))

    def test_antiguo_defecto_60s_excede_con_dos_paradas(self):
        self.assertTrue(const.excede_limite([(60, 24.0)] * 2))

    def test_recomendados_del_usuario(self):
        self.assertFalse(const.excede_limite([(150, 24.0)] * 2))
        self.assertFalse(const.excede_limite([(180, 24.0)] * 3))
        self.assertFalse(const.excede_limite([(150, 19.0)] * 3))

    def test_minimo_cumple_el_limite(self):
        for n in (1, 2, 3, 5):
            for horas in (24.0, 19.0):
                self.assertFalse(
                    const.excede_limite([(const.intervalo_minimo(n, horas), horas)] * n)
                )


class TestPausa(unittest.TestCase):
    D, H = "00:30:00", "05:30:00"

    def test_dentro_y_fuera(self):
        m = const.a_minutos
        self.assertFalse(const.en_pausa(m("00:29"), self.D, self.H))
        self.assertTrue(const.en_pausa(m("00:30"), self.D, self.H))
        self.assertTrue(const.en_pausa(m("03:00"), self.D, self.H))
        self.assertTrue(const.en_pausa(m("05:29"), self.D, self.H))
        self.assertFalse(const.en_pausa(m("05:30"), self.D, self.H))
        self.assertFalse(const.en_pausa(m("12:00"), self.D, self.H))

    def test_cruza_medianoche(self):
        m = const.a_minutos
        self.assertTrue(const.en_pausa(m("23:30"), "23:00", "06:00"))
        self.assertTrue(const.en_pausa(m("02:00"), "23:00", "06:00"))
        self.assertFalse(const.en_pausa(m("12:00"), "23:00", "06:00"))
        self.assertEqual(const.horas_activas("23:00", "06:00"), 17.0)

    def test_iguales_no_hay_pausa(self):
        self.assertFalse(const.en_pausa(0, "03:00", "03:00"))
        self.assertEqual(const.horas_activas("03:00", "03:00"), 24.0)

    def test_acepta_hhmm_y_hhmmss(self):
        self.assertEqual(const.a_minutos("05:30"), const.a_minutos("05:30:00"))


if __name__ == "__main__":
    unittest.main()
