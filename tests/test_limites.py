"""Pruebas de los cálculos de límite de consultas (sin Home Assistant)."""
import importlib.util
import pathlib
import unittest

BASE = pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "itranvias_coruna"
spec = importlib.util.spec_from_file_location("itr_const", BASE / "const.py")
const = importlib.util.module_from_spec(spec)
spec.loader.exec_module(const)


class TestLimites(unittest.TestCase):
    def test_intervalo_minimo(self):
        self.assertEqual(const.intervalo_minimo(1), 55)
        self.assertEqual(const.intervalo_minimo(2), 109)
        self.assertEqual(const.intervalo_minimo(3), 163)

    def test_defecto_valido_hasta_tres_paradas_no_hasta_cuatro(self):
        self.assertFalse(const.excede_limite([const.DEFAULT_INTERVALO] * 3))
        self.assertTrue(const.excede_limite([const.DEFAULT_INTERVALO] * 4))

    def test_antiguo_defecto_60s_excede_con_dos_paradas(self):
        self.assertTrue(const.excede_limite([60, 60]))

    def test_recomendados_del_usuario(self):
        self.assertFalse(const.excede_limite([150, 150]))
        self.assertFalse(const.excede_limite([180, 180, 180]))

    def test_minimo_cumple_el_limite(self):
        for n in (1, 2, 3, 5):
            self.assertFalse(const.excede_limite([const.intervalo_minimo(n)] * n))


if __name__ == "__main__":
    unittest.main()
