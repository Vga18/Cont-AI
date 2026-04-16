import re
import unicodedata

import joblib
import pandas as pd
from numpy import nan


def limpiar_texto(texto: str) -> str:

    if texto is None:
        return ""

    texto = str(texto)
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = texto.lower()
    texto = re.sub(r"[^a-z0-9\s]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()

    return texto


def clean_text(text, pattern="[^a-zA-Z0-9 ]"):
    cleaned_text = unicodedata.normalize("NFD", text).encode("ascii", "ignore")
    cleaned_text = re.sub(pattern, " ", cleaned_text.decode("utf-8"), flags=re.UNICODE)
    cleaned_text = " ".join(cleaned_text.lower().split())
    return cleaned_text


def normalizar_condicion(x):
    if pd.isna(x):
        return "sin definir"

    x = str(x).strip(" ")

    if "credito" in x:
        return "credito"

    if any(p in x for p in ["contado", "0 dias", "inmediato", "efectivo"]):
        return "contado"

    else:
        return "otros"


def contruir_poliza_eg(xml, cuenta, catalogo):

    aux = cuenta[:4] + "." + cuenta[4:7] + "." + cuenta[-4:]
    resultado = catalogo.loc[catalogo["NUM_CTA"] == aux, "NOMBRE"]

    if not resultado.empty:
        concept = resultado.iloc[0]
    else:
        concept = "Sin definir"

    iva = xml["Retenido IVA"]
    total = xml["Total"]
    factura = (
        str(xml["Serie"]) + "-" + str(xml["Folio"]) + " " + str(xml["Nombre Emisor"])
    )

    aux = pd.DataFrame(
        {
            "NUM_CTA": [aux, "1200.001.0002", "1000.000.000"],
            "CONCEPTO": [concept, "IVA ACREDITABLE PAGADO", "Activo (general)"],
            "NOMBRE_POL": [
                f"FACTURA {factura}",
                f"FACTURA {factura}",
                f"FACTURA {factura}",
            ],
            "CARGO_ABONO": ["C", "C", "A"],
            "Monto": [total - iva, iva, total],
        }
    )

    return aux


def procesar_conceptos(texto):
    lista = str(texto).split("|")
    lista_limpia = [limpiar_texto(x) for x in lista if limpiar_texto(x)]
    return " ".join(lista_limpia)


def eliminar_null(row):
    if pd.isna(row):
        return "sin definir"
    else:
        return row


def construir_dataframe_modelo(datos_xml):
    concepto_unido = procesar_conceptos(datos_xml["Conceptos"])

    Condicion_de_Pago = clean_text(datos_xml["Condicion de Pago"])
    Condicion_de_Pago = normalizar_condicion(datos_xml["Condicion de Pago"])

    df_nuevo = pd.DataFrame(
        [
            {
                "RFC Emisor": eliminar_null(datos_xml["RFC Emisor"]),
                "UsoCFDI": eliminar_null(datos_xml["UsoCFDI"]),
                "Metodo de Pago": eliminar_null(datos_xml["Metodo de Pago"]),
                "Condicion de Pago": Condicion_de_Pago,
                "RegimenFiscalEmisor": eliminar_null(datos_xml["RegimenFiscalEmisor"]),
                "concepto_unido": concepto_unido,
            }
        ]
    )

    return df_nuevo


def get_clasificar_xmls(datos_xml, umbral=0.65):

    pipeline = joblib.load(r"utils\classificador contable.pkl")

    df_nuevo = construir_dataframe_modelo(datos_xml)

    pred = pipeline.predict(df_nuevo)[0]

    return pred
