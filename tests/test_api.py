"""Pruebas del parser (sin Home Assistant). Ejecutar: python -m unittest discover tests

Los datos son SINTÉTICOS, escritos a partir de la descripción del contrato de la API
(no son una captura real del servicio).
"""
import importlib.util
import pathlib
import sys
import types
import unittest

BASE = pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "itranvias_coruna"
pkg = types.ModuleType("itr")
pkg.__path__ = [str(BASE)]
sys.modules["itr"] = pkg
for nombre in ("const", "api"):
    spec = importlib.util.spec_from_file_location(f"itr.{nombre}", BASE / f"{nombre}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"itr.{nombre}"] = mod
    spec.loader.exec_module(mod)
api = sys.modules["itr.api"]

LLEGADAS = {
    "resultado": "OK",
    "buses": {
        "parada": 123,
        "lineas": [
            {"linea": 2000, "buses": [
                {"bus": 369, "tiempo": "26", "distancia": "7112", "estado": 0, "ult_parada": 370},
                {"bus": 392, "tiempo": "3", "distancia": "974", "estado": 1, "ult_parada": 119},
            ]},
            {"linea": 1500, "buses": [
                {"bus": 367, "tiempo": "<1", "distancia": "50", "estado": 0, "ult_parada": 10},
                {"bus": 373, "tiempo": "x", "distancia": None, "estado": 1, "ult_parada": None},
            ]},
            {"linea": 1400, "buses": []},
        ],
    },
}

CATALOGO = {
    "resultado": "OK",
    "iTranvias": {"actualizacion": {
        "fecha": "20260101T000000",
        "lineas": [
            {"id": 1400, "lin_comer": "14", "nombre_orig": "A", "nombre_dest": "B", "color": "ff0000", "rutas": []},
            {"id": 1500, "lin_comer": "12A", "nombre_orig": "C", "nombre_dest": "D", "color": "#00FF00", "rutas": []},
            {"id": 2000, "lin_comer": "20", "nombre_orig": "E", "nombre_dest": "F", "color": "zz", "rutas": []},
            {"id": 1801, "lin_comer": "BUH", "nombre_orig": "G", "nombre_dest": "H", "color": "0000ff", "rutas": []},
        ],
        "paradas": [
            {"id": 123, "nombre": "Rda. de Outeiro, 212", "posx": 1, "posy": 2, "enlaces": [1500, 1400, 2000, 1801]},
        ],
    }},
}


class TestTiempo(unittest.TestCase):
    def test_valores(self):
        self.assertEqual(api.parse_tiempo("<1"), (None, True))
        self.assertEqual(api.parse_tiempo("12"), (12, False))
        self.assertEqual(api.parse_tiempo(7), (7, False))
        self.assertEqual(api.parse_tiempo("x"), (None, False))
        self.assertEqual(api.parse_tiempo(None), (None, False))
        self.assertEqual(api.parse_tiempo("-3"), (None, False))


class TestLlegadas(unittest.TestCase):
    def test_parse_y_orden(self):
        r = api.parse_llegadas(LLEGADAS)
        self.assertEqual(set(r), {2000, 1500})  # 1400 sin buses no aparece
        self.assertEqual([b["vehiculo"] for b in r[2000]], [392, 369])
        # "<1" primero, desconocido al final, dentro de la línea
        self.assertEqual([api.texto_tiempo(b) for b in r[1500]], ["<1", "?"])
        self.assertTrue(r[1500][0]["menor_que_1"])
        self.assertIsNone(r[1500][0]["minutos"])
        self.assertEqual(r[2000][1]["distancia"], 7112)

    def test_orden_global(self):
        r = api.parse_llegadas(LLEGADAS)
        todos = sorted((b for bs in r.values() for b in bs), key=api.clave_orden)
        self.assertEqual([api.texto_tiempo(b) for b in todos], ["<1", "3", "26", "?"])

    def test_lista_vacia_no_es_error(self):
        self.assertEqual(api.parse_llegadas({"resultado": "OK", "buses": {"parada": 1, "lineas": []}}), {})
        self.assertEqual(api.parse_llegadas({"resultado": "OK", "buses": None}), {})

    def test_errores(self):
        for malo in (None, [], {"resultado": "KO"}, "texto"):
            with self.assertRaises(api.ItranviasError):
                api.parse_llegadas(malo)


class TestCatalogo(unittest.TestCase):
    def test_parse(self):
        c = api.parse_catalogo(CATALOGO)
        self.assertEqual(c["lineas"][1500]["nombre"], "12A")
        self.assertEqual(c["lineas"][1801]["nombre"], "BUH")
        self.assertEqual(c["lineas"][1400]["color"], "FF0000")
        self.assertEqual(c["lineas"][1500]["color"], "00FF00")
        self.assertIsNone(c["lineas"][2000]["color"])
        self.assertEqual(c["paradas"][123]["nombre"], "Rda. de Outeiro, 212")
        self.assertEqual(c["paradas"][123]["enlaces"], [1500, 1400, 2000, 1801])
        self.assertEqual(c["fecha"], "20260101T000000")

    def test_clave_con_punto(self):
        data = {"iTranvias.actualizacion": CATALOGO["iTranvias"]["actualizacion"]}
        self.assertIn(1400, api.parse_catalogo(data)["lineas"])

    def test_errores(self):
        for malo in (None, {}, {"iTranvias": {"actualizacion": {"lineas": [], "paradas": []}}}):
            with self.assertRaises(api.ItranviasError):
                api.parse_catalogo(malo)


if __name__ == "__main__":
    unittest.main()
