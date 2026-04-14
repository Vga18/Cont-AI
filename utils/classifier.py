import re
import unicodedata

import joblib
import pandas as pd


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


def contruir_poliza_eg(xml, cuenta):

    concept = " "
    iva = xml["Retenido IVA"]
    total = xml["Total"]
    factura = xml["Serie"] + "-" + xml["Folio"] + " " + xml["Nombre Emisor"]

    aux = pd.DataFrame(
        {
            "NUM_CTA": [cuenta, "1200.001.000", "1000.000.000"],
            "CONCEPTO": [concept, "IVA acreditable", "Activo (general)"],
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


def construir_dataframe_modelo(datos_xml):
    concepto_unido = procesar_conceptos(datos_xml["Conceptos"])

    df_nuevo = pd.DataFrame(
        [
            {
                "RFC Emisor": datos_xml["RFC Emisor"],
                "UsoCFDI": datos_xml["UsoCFDI"],
                "Metodo de Pago": datos_xml["Metodo de Pago"],
                "Condicion de Pago": datos_xml["Condicion de Pago"],
                "RegimenFiscalEmisor": datos_xml["RegimenFiscalEmisor"],
                "concepto_unido": concepto_unido,
            }
        ]
    )

    return df_nuevo


def get_clasificar_xmls(datos_xml, umbral=0.65):

    pipeline = joblib.load(r"utils\classificador contable.pkl")

    df_nuevo = construir_dataframe_modelo(datos_xml)

    pred = pipeline.predict(df_nuevo)[0]
    proba = pipeline.predict_proba(df_nuevo).max()

    return pred

    # print(pred)

    # if proba >= umbral:
    #     decision = "AUTOMATICO"
    # else:
    #     decision = "REVISION"

    # return {
    #     "cuenta_predicha": pred,
    #     "confianza": round(float(proba), 4),
    #     "decision": decision,
    # }
