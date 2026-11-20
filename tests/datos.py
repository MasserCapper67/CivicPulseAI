"""Datos de prueba compartidos por varios ficheros de tests."""
from datetime import date

HOY, ENERO_2027 = date(2026, 11, 19), date(2027, 1, 2)
SOL, ELIPTICA, RETIRO, GETAFE = (-3.7035, 40.4168), (-3.7183, 40.3853), (-3.6844, 40.4153), (-3.7326, 40.3057)
DESTINO_SOL = {"lng": SOL[0], "lat": SOL[1], "direccion": "Puerta del Sol"}
TARIFAS_RECUERDO = [  # aparcamiento Nuestra Señora del Recuerdo, servicio SOAP del Ayuntamiento (20/11/2026)
    {"desde": 0, "hasta": 30, "periodo": "minutos", "precio": 0.0409},
    {"desde": 31, "hasta": 90, "periodo": "minutos", "precio": 0.0366},
    {"desde": 91, "hasta": 660, "periodo": "minutos", "precio": 0.0489},
    {"desde": 661, "hasta": 1440, "periodo": "maximo", "precio": 31.25},
]
