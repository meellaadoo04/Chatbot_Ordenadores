import os
import re
from datetime import datetime
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential
from azure.cosmos import CosmosClient, exceptions
from dotenv import load_dotenv

# Cargar variables de entorno desde el archivo .env
load_dotenv()

# -------------------------
# Configuración Form Recognizer
# -------------------------
AZURE_ENDPOINT_DOC = os.getenv("AZURE_ENDPOINT_DOCUMEN_INTELLIGENCE")
AZURE_API_KEY_DOC = os.getenv("AZURE_API_KEY_DOCUMEN_INTELLIGENCE")
MODEL_ID = os.getenv("MODEL")
PDF_DIRECTORY = "C:\\Users\\Alumno_AI\\Downloads\\Fichas técnicas"  # Ajusta la ruta según corresponda

if not all([AZURE_ENDPOINT_DOC, AZURE_API_KEY_DOC, MODEL_ID]):
    raise ValueError("Faltan variables de entorno para Form Recognizer. Verifica tu archivo .env")

# Inicializar el cliente de Form Recognizer
document_analysis_client = DocumentAnalysisClient(
    endpoint=AZURE_ENDPOINT_DOC,
    credential=AzureKeyCredential(AZURE_API_KEY_DOC)
)

# -------------------------
# Configuración Cosmos DB
# -------------------------
COSMOS_ENDPOINT = os.getenv("COSMOS_ENDPOINT")
COSMOS_KEY = os.getenv("COSMOS_KEY")
DB_NAME = "OrdenadoresDB"
CONTAINER_NAME = "Especificaciones"

if not all([COSMOS_ENDPOINT, COSMOS_KEY, DB_NAME, CONTAINER_NAME]):
    raise ValueError("Faltan variables de entorno para Cosmos DB. Verifica tu archivo .env")

# Inicializar el cliente de Cosmos DB
cosmos_client = CosmosClient(COSMOS_ENDPOINT, COSMOS_KEY)
database = cosmos_client.get_database_client(DB_NAME)
container = database.get_container_client(CONTAINER_NAME)

def transformar_entidades(entidades):
    """
    Transforma el diccionario de entidades extraído por Form Recognizer en un formato plano
    con las claves deseadas y aplicando algunas conversiones:
      - "Marca": cadena tal como viene en 'marca'
      - "Modelo": cadena tal como viene en 'modelo'
      - "Procesador": se procesa la cadena para remover saltos de línea y tomar sólo la parte relevante
      - "RAM": se obtiene el valor extraído de 'ram'
      - "Almacenamiento": se elimina la unidad "GB"
      - "Tarjeta gráfica": se establece a None (puedes ajustarlo si deseas extraer este valor)
      - "Pulgadas": se extrae el número (quitando caracteres no numéricos)
      - "Precio": se procesa el texto para convertirlo a número (ej. de "2.205,78 €" a 2206)
      - "Frecuencia procesador": se elimina la unidad "GHZ"
    """
    resultado = {}

    # Marca
    resultado["Marca"] = entidades.get("marca", {}).get("valor", None)
    
    # Modelo
    resultado["Modelo"] = entidades.get("modelo", {}).get("valor", None)
    
    # Procesador: quitar saltos de línea y, si hay un guión, tomar la parte antes del guión en el segundo componente
    proc_val = entidades.get("procesador", {}).get("valor", None)
    if proc_val:
        proc_val = proc_val.replace("\n", " ")
        tokens = proc_val.split()
        nuevo_tokens = []
        for token in tokens:
            if "-" in token:
                nuevo_tokens.append(token.split("-")[0])
            else:
                nuevo_tokens.append(token)
        resultado["Procesador"] = " ".join(nuevo_tokens)
    else:
        resultado["Procesador"] = None

    # RAM: se extrae el valor de 'ram'
    resultado["RAM"] = entidades.get("ram", {}).get("valor", None)

    # Almacenamiento: quitar "GB" y espacios
    almacen_val = entidades.get("almacenamiento", {}).get("valor", None)
    if almacen_val:
        almacen_val = almacen_val.replace("GB", "").strip()
        resultado["Almacenamiento"] = almacen_val
    else:
        resultado["Almacenamiento"] = None

    # Tarjeta gráfica: se establece a None (o procesa si tienes lógica)
    resultado["Tarjeta gráfica"] = entidades.get("modelo", {}).get("valor", None)

    # Pulgadas: extraer dígitos y convertir la coma a punto para valores decimales
    pulg_val = entidades.get("pulgadas", {}).get("valor", None)
    if pulg_val:
        # Primero, eliminamos cualquier carácter no numérico excepto la coma
        num = re.sub(r"[^\d,]", "", pulg_val)
        # Reemplazamos la coma por un punto para manejar correctamente el valor decimal
        num = num.replace(",", ".")
        resultado["Pulgadas"] = num if num != "" else None
    else:
        resultado["Pulgadas"] = None


    # Precio: quitar el símbolo de euro, eliminar separadores de miles y convertir la coma decimal a punto
    precio_val = entidades.get("precio", {}).get("valor", None)
    if precio_val:
        precio_val = precio_val.replace("€", "").strip()
        # Eliminar el punto que se usa como separador de miles y reemplazar la coma decimal por punto
        precio_val = precio_val.replace(".", "").replace(",", ".")
        try:
            precio_num = float(precio_val)
            # Redondea y convierte a entero
            resultado["Precio"] = int(round(precio_num))
        except Exception as e:
            resultado["Precio"] = None
    else:
        resultado["Precio"] = None

    # Frecuencia procesador: quitar "GHZ" y espacios
    freq_val = entidades.get("frecuencia procesador", {}).get("valor", None)
    if freq_val:
        resultado["Frecuencia procesador"] = freq_val.replace("GHZ", "").strip()
    else:
        resultado["Frecuencia procesador"] = None

    return resultado

def analizar_pdf(pdf_path):
    # Generar el id único basado solo en el nombre del archivo
    document_id = os.path.basename(pdf_path)
    
    # Comprobar si el documento ya existe en la base de datos
    try:
        query = f"SELECT * FROM c WHERE c.id = @id"
        parameters = [{"name": "@id", "value": document_id}]
        
        existing_item = list(container.query_items(
            query=query,
            parameters=parameters,
            enable_cross_partition_query=True
        ))
        
        if existing_item:
            print(f"⚠️ El documento {os.path.basename(pdf_path)} ya está en la base de datos. Se omite la inserción.")
            return  # Si el documento ya existe, no lo insertamos
        
    except exceptions.CosmosHttpResponseError as e:
        print(f"❌ Error al comprobar si el documento existe en Cosmos DB: {str(e)}")
        return

    with open(pdf_path, "rb") as pdf_file:
        poller = document_analysis_client.begin_analyze_document(
            model_id=MODEL_ID,
            document=pdf_file
        )
        result = poller.result()

    # Imprimir las entidades detectadas (formato original)
    print(f"\n--- Entidades detectadas en {pdf_path} ---\n")
    entidades_raw = {}
    for idx, (field_name, field_value) in enumerate(result.documents[0].fields.items()):
        print(f"{idx+1}. {field_name}: {field_value.value} (Confianza: {field_value.confidence})")
        entidades_raw[field_name] = {
            "valor": field_value.value,
            "confianza": field_value.confidence
        }

    # Transformar las entidades al formato deseado
    entidades_transformadas = transformar_entidades(entidades_raw)
    
    # Construir el documento final a insertar en Cosmos DB
    documento = {
        "id": document_id,  # Usamos solo el nombre del archivo como ID
        "nombre_archivo": os.path.basename(pdf_path),
        "fecha_procesamiento": datetime.now().isoformat(),
    }
    documento.update(entidades_transformadas)  # Se agregan las claves planas (Marca, Modelo, etc.)
    
    # Insertar el documento en Cosmos DB
    try:
        container.upsert_item(documento)
        print(f"✅ Documento insertado en Cosmos DB: {documento['nombre_archivo']}")
    except exceptions.CosmosHttpResponseError as e:
        print(f"❌ Error al insertar el documento en Cosmos DB: {str(e)}")

if __name__ == "__main__":
    # Procesar cada PDF en la carpeta
    for filename in os.listdir(PDF_DIRECTORY):
        if filename.lower().endswith(".pdf"):
            pdf_path = os.path.join(PDF_DIRECTORY, filename)
            if os.path.exists(pdf_path):
                analizar_pdf(pdf_path)
            else:
                print(f"⚠️ No se encontró el archivo PDF: {pdf_path}")
