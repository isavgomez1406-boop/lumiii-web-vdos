"""
Genera catalogo/catalogo.json a partir del Excel del catálogo, y coloca un
README.txt dentro de cada subcarpeta (catalogo/<categoria>/<codigo>/) con la
lista exacta de SKUs que van ahí, para que sepas cómo nombrar cada PNG.

CÓMO USARLO:
1. Coloca este archivo junto a tu Excel de catálogo
   (por defecto busca "Catálogo_Codificado_de_LUMIII.xlsx" en la misma carpeta;
   cámbialo abajo en RUTA_EXCEL si tu archivo se llama distinto).
2. Corre: python generar_catalogo_json.py
3. Cada vez que edites el Excel (agregues/quites modelos), vuelve a correr
   este script para regenerar catalogo/catalogo.json.

Convención de SKU esperada: <PREFIJO_PRODUCTO>-<CODIGO_RESULTADO>-<NUM>
  Ej: LEN-CIN-01  ->  Lentes, resultado "CIN" (Colorimetría Invierno), variante 01
Las hojas del Excel deben llamarse igual que la carpeta de categoría
(con mayúscula inicial): Lentes, Bufandas, Cintillo, Chaqueta, Franelas.
"""

import os
import json
import openpyxl

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RUTA_EXCEL = os.path.join(BASE_DIR, "Catálogo_Codificado_de_LUMIII.xlsx")
CARPETA_CATALOGO = os.path.join(BASE_DIR, "catalogo")

# Nombre de hoja de Excel -> nombre de carpeta en catalogo/ (minúsculas)
HOJA_A_CARPETA = {
    "Lentes": "lentes",
    "Bufandas": "bufandas",
    "Cintillo": "cintillo",
    "Chaqueta": "chaqueta",
    "Franelas": "franelas",
}

CODIGOS_VALIDOS = {"CIN", "CVE", "COT", "CPR", "MRE", "MCU", "MDI", "MOV"}


def main():
    wb = openpyxl.load_workbook(RUTA_EXCEL, data_only=True)
    catalogo = {}
    por_carpeta = {}  # (categoria, codigo) -> lista de (sku, descripcion)

    for nombre_hoja, carpeta in HOJA_A_CARPETA.items():
        if nombre_hoja not in wb.sheetnames:
            print(f"⚠️  No se encontró la hoja '{nombre_hoja}' en el Excel, se omite.")
            continue

        ws = wb[nombre_hoja]
        filas = list(ws.iter_rows(min_row=2, values_only=True))  # salta encabezado
        for fila in filas:
            if not fila or not fila[0]:
                continue
            sku, enfoque, descripcion = fila[0], fila[1], fila[2]
            partes = str(sku).split("-")
            if len(partes) != 3 or partes[1] not in CODIGOS_VALIDOS:
                print(f"⚠️  SKU con formato inesperado, se omite: {sku}")
                continue
            codigo = partes[1]

            catalogo[sku] = {
                "categoria": carpeta,
                "codigo": codigo,
                "enfoque": enfoque,
                "descripcion": descripcion,
            }
            por_carpeta.setdefault((carpeta, codigo), []).append((sku, descripcion))

    # Guardar catalogo.json
    os.makedirs(CARPETA_CATALOGO, exist_ok=True)
    ruta_json = os.path.join(CARPETA_CATALOGO, "catalogo.json")
    with open(ruta_json, "w", encoding="utf-8") as f:
        json.dump(catalogo, f, ensure_ascii=False, indent=2)
    print(f"✅ Generado {ruta_json} con {len(catalogo)} SKUs.")

    # Generar un README.txt por subcarpeta con la lista esperada de PNGs
    total_readmes = 0
    for (carpeta, codigo), items in por_carpeta.items():
        ruta_carpeta = os.path.join(CARPETA_CATALOGO, carpeta, codigo)
        os.makedirs(ruta_carpeta, exist_ok=True)
        ruta_readme = os.path.join(ruta_carpeta, "README.txt")
        with open(ruta_readme, "w", encoding="utf-8") as f:
            f.write(f"Modelos esperados en catalogo/{carpeta}/{codigo}/\n")
            f.write("Guarda cada uno como <SKU>.png (ej: " + items[0][0] + ".png)\n\n")
            for sku, descripcion in items:
                f.write(f"- {sku}.png  ->  {descripcion}\n")
        total_readmes += 1
    print(f"✅ Generados {total_readmes} archivos README.txt (uno por subcarpeta).")


if __name__ == "__main__":
    main()
