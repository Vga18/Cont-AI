import json

from utils.classifier import get_clasificar_xmls

get_intrinsic_value_json = {
    "name": "get_clasificar_xmls",
    "description": "Usa esta herramienta (tool) para obtener classificar  el valor intrínseco de la compañía solicitado por el usuario. \
                    Evita cálculos ajenos a la herramienta proporcionada como WACC, DFC, entre otros.\
                    Contrasta siempre con el precio final que también provee la herramienta para dar insights sin ser recomendación de compra o venta.",
    "parameters": {
        "type": "object",
        "properties": {
            "ticker": {
                "type": "string",
                "description": "El TICKER de la compañía a analizar.",
            },
        },
        "required": ["ticker"],
        "additionalProperties": False,
    },
}
