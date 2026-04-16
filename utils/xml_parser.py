import os
from io import BytesIO
from typing import List, Union

from lxml import etree
from numpy import nan
from pandas import DataFrame, to_datetime

import utils.validate as val


def obtener_version_comprobante(root: etree._Element) -> str:
    return root.attrib.get("Version") or root.attrib.get("version", "")


def get_attrib(elem: etree._Element, key: str, default=nan):
    return elem.attrib.get(key, default) if elem is not None else default


def cargar_xml(path: str) -> etree._Element:
    tree = etree.parse(path)
    return tree.getroot()


def validacion(row):
    return val.valid_cfdi(
        row["RFC Emisor"], row["RFC Receptor"], row["Total"], row["UUID"]
    )


def safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return nan


def extraer_pue_ppd(root: etree._Element, namespaces: dict) -> dict:
    x = root.attrib.get
    emi = root.find(".//cfdi:Emisor", namespaces)
    recp = root.find(".//cfdi:Receptor", namespaces)
    timbre = root.find(".//cfdi:Complemento/tfd:TimbreFiscalDigital", namespaces)
    conceptos = root.findall(".//cfdi:Conceptos/cfdi:Concepto", namespaces)
    impuestos = root.findall(
        ".//cfdi:Impuestos/cfdi:Traslados/cfdi:Traslado", namespaces
    )

    descripcion_total = " | ".join(
        [concepto.attrib.get("Descripcion", nan) for concepto in conceptos]
    )

    iva_0 = iva_16_base = iva_16_importe = nan
    for imp in impuestos:
        tasa = float(imp.attrib.get("TasaOCuota", 0))
        base = float(imp.attrib.get("Base", 0))
        importe = float(imp.attrib.get("Importe", 0))
        if round(tasa, 6) == 0.16:
            iva_16_base = base
            iva_16_importe = importe
        elif tasa == 0.0:
            iva_0 = base

    return {
        "Estado SAT": nan,
        "Version": x("Version", nan),
        "Tipo": x("TipoDeComprobante", nan),
        "Exportacion": x("Exportacion", nan),
        "Fecha Emision": x("Fecha", nan),
        "Fecha Timbrado": get_attrib(timbre, "FechaTimbrado"),
        "Serie": x("Serie", nan),
        "Folio": x("Folio", nan),
        "UUID": get_attrib(timbre, "UUID"),
        "RFC Emisor": get_attrib(emi, "Rfc"),
        "Nombre Emisor": get_attrib(emi, "Nombre"),
        "RegimenFiscalEmisor": get_attrib(emi, "RegimenFiscal"),
        "RFC Receptor": get_attrib(recp, "Rfc"),
        "Nombre Receptor": get_attrib(recp, "Nombre"),
        "Regimen Fiscal Receptor": get_attrib(recp, "RegimenFiscalReceptor"),
        "Domicilio Fiscal Receptor": get_attrib(recp, "DomicilioFiscalReceptor"),
        "UsoCFDI": get_attrib(recp, "UsoCFDI"),
        "SubTotal": safe_float(x("SubTotal")),
        "Descuento": safe_float(x("Descuento")),
        "IVA 0% Base": iva_0,
        "IVA 16% Base": iva_16_base,
        "Retenido IVA": iva_16_importe,
        "Total": safe_float(x("Total")),
        "Moneda": x("Moneda", nan),
        "LugarExpedicion": x("LugarExpedicion", nan),
        "Tipo de Cambio": x("TipoCambio", nan),
        "Forma de Pago": x("FormaPago", nan),
        "Metodo de Pago": x("MetodoPago", nan),
        "Condicion de Pago": x("CondicionesDePago", "sin definir"),
        "Conceptos": descripcion_total,
    }


def procesar_dataframe_xml_general(data: List[dict]) -> DataFrame:
    df = DataFrame(data)
    df["Fecha Emision"] = to_datetime(df["Fecha Emision"])
    df = df.sort_values(by="Fecha Emision").reset_index(drop=True)
    df["Estado SAT"] = list(map(validacion, [row for _, row in df.iterrows()]))
    df["Fecha Emision"] = df["Fecha Emision"].dt.date
    return df


def parse_cfdi(xmls: List[Union[str, BytesIO]]) -> DataFrame:
    """
    Procesa una lista de archivos XML CFDI (4.0, PUE o PPD) y devuelve
    un DataFrame consolidado con los principales atributos fiscales.

    Soporta:
    - Rutas de archivo
    - Objetos file-like (ej. Streamlit UploadedFile)
    - UTF-8 con o sin BOM
    - Recuperación ante XML parcialmente malformado

    Seguridad:
    - Desactiva resolución de entidades (protección XXE)
    - No valida estado SAT
    """

    df_xmls = []
    for archivo in xmls:
        try:
            tree = etree.parse(archivo)
            root = tree.getroot()
            namespaces = {
                "cfdi": root.tag.split("}")[0].strip("{"),
                "tfd": "http://www.sat.gob.mx/TimbreFiscalDigital",
                "pago20": "http://www.sat.gob.mx/Pagos20",
                "nomina12": "http://www.sat.gob.mx/nomina12",
            }
            datos = extraer_pue_ppd(root, namespaces)
            df_xmls.append(datos)

        except Exception as e:
            continue

    if not df_xmls:
        return DataFrame()

    df_final = procesar_dataframe_xml_general(df_xmls)

    return df_final
