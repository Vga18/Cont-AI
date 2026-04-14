import xml.etree.ElementTree as ET
from re import search
from typing import Dict, Optional, Union
from urllib.request import Request, urlopen

# Constants
WEBSERVICE_URL = (
    "https://consultaqr.facturaelectronica.sat.gob.mx/consultacfdiservice.svc"
)
SOAP_ACTION = "http://tempuri.org/IConsultaCFDIService/Consulta"


def get_soap_message(
    rfc_emisor: str,
    rfc_receptor: str,
    total: str,
    uuid: str,
    header_options: Optional[Dict[str, str]] = None,
    return_bytes: bool = True,
) -> Union[bytes, str]:
    """
    Builds a SOAP message to query a CFDI from the SAT web service.

    Parameters
    ----------
    rfc_emisor : str
        The issuer's RFC.
    rfc_receptor : str
        The receiver's RFC.
    total : str
        The total amount of the CFDI.
    uuid : str
        The CFDI's UUID.
    header_options : dict of str, str, optional
        Additional options to include in the SOAP header. Defaults to None.
    return_bytes : bool, default=True
        If True, returns the SOAP message as bytes. If False, returns as a string.

    Returns
    -------
    bytes or str
        The constructed SOAP message. The return type depends on `return_bytes`.

    Examples
    --------
    >>> soap = get_soap_message("AAA010101AAA", "BBB010101BBB", "1000.00", "12345678-1234-1234-1234-1234567890AB")
    >>> isinstance(soap, bytes)
    True
    """
    namespaces = {
        "soap": "http://schemas.xmlsoap.org/soap/envelope/",
        "xsd": "http://www.w3.org/2001/XMLSchema",
        "xsi": "http://www.w3.org/2001/XMLSchema-instance",
    }

    for prefix, uri in namespaces.items():
        ET.register_namespace(prefix, uri)

    envelope = ET.Element(ET.QName(namespaces["soap"], "Envelope"))
    if header_options:
        header = ET.SubElement(envelope, ET.QName(namespaces["soap"], "Header"))
        for key, value in header_options.items():
            ET.SubElement(header, key).text = value

    body = ET.SubElement(envelope, ET.QName(namespaces["soap"], "Body"))
    consulta = ET.SubElement(body, "Consulta", xmlns="http://tempuri.org/")
    expresion_impresa = ET.SubElement(consulta, "expresionImpresa")

    expresion_impresa.text = f"?re={rfc_emisor}&rr={rfc_receptor}&tt={total}&id={uuid}"

    soap_xml_bytes = ET.tostring(envelope, encoding="utf-8", method="xml")

    if return_bytes:
        return soap_xml_bytes
    else:
        return soap_xml_bytes.decode("utf-8")


def valid_cfdi(rfc_emisor: str, rfc_receptor: str, total: str, uuid: str) -> str:
    """
    Validates a CFDI with the SAT service and returns its status.

    Parameters
    ----------
    rfc_emisor : str
        The issuer's RFC.
    rfc_receptor : str
        The receiver's RFC.
    total : str
        The total amount of the CFDI.
    uuid : str
        The CFDI's UUID.

    Returns
    -------
    str
        The CFDI status returned by the SAT service, or an error message if it cannot be obtained.

    Examples
    --------
    >>> status = valid_cfdi("AAA010101AAA", "BBB010101BBB", "1000.00", "12345678-1234-1234-1234-1234567890AB")
    >>> print(status)
    "Vigente"  # or any other status returned by the SAT
    """
    headers = {
        "SOAPAction": f'"{SOAP_ACTION}"',
        "Content-type": 'text/xml; charset="UTF-8"',
    }

    soap_message = get_soap_message(
        rfc_emisor, rfc_receptor, total, uuid, return_bytes=True
    )

    request = Request(url=WEBSERVICE_URL, data=soap_message, method="POST")
    for k, v in headers.items():
        request.add_header(k, v)

    try:
        with urlopen(request, timeout=10) as f:
            response = f.read().decode("utf-8")
            match = search(r"(?s)(?<=Estado>).+?(?=</a:)", response)
            if match:
                return match.group()
            else:
                return "No status found in the response."
    except Exception as e:
        return f"Error while querying CFDI: {e}"


if __name__ == "__main__":
    # Example data
    emisor_rfc = "XXX99900XX00"
    receptor_rfc = "XXX99900XX11"
    total = "1586.80"
    uuid = "925118EB-6165-4FA0-A978-7787C70181FE"

    status_sat = valid_cfdi(emisor_rfc, receptor_rfc, total, uuid)
    print(status_sat)
