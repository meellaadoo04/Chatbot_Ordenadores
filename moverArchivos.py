from dotenv import load_dotenv
import os
from azure.core.credentials import AzureKeyCredential
from azure.ai.textanalytics import TextAnalyticsClient
from azure.cosmos import CosmosClient, exceptions
import uuid

def main():
    try:
        # Cargar variables de entorno
        load_dotenv()
        ai_endpoint = os.getenv('AI_SERVICE_ENDPOINT')
        ai_key = os.getenv('AI_SERVICE_KEY')
        project_name = os.getenv('PROJECT')
        deployment_name = os.getenv('DEPLOYMENT')
        cosmos_endpoint = os.getenv('COSMOS_ENDPOINT')
        cosmos_key = os.getenv('COSMOS_KEY')

        # Crear cliente de Text Analytics
        credential = AzureKeyCredential(ai_key)
        ai_client = TextAnalyticsClient(endpoint=ai_endpoint, credential=credential)

        # Crear cliente de Cosmos DB
        cosmos_client = CosmosClient(cosmos_endpoint, cosmos_key)
        database = cosmos_client.get_database_client("OrdenadoresDB")
        container = database.get_container_client("Especificaciones")

        # Leer archivos TXT
        batchedDocuments = []
        ads_folder = "C:\\Users\\Alumno_AI\\Downloads\\Textos extraídos"
        files = os.listdir(ads_folder)
        for file_name in files:
            # Leer el contenido del archivo
            text = open(os.path.join(ads_folder, file_name), encoding='utf8').read()
            batchedDocuments.append(text)

        # Extraer entidades personalizadas
        operation = ai_client.begin_recognize_custom_entities(
            batchedDocuments,
            project_name=project_name,
            deployment_name=deployment_name
        )
        document_results = operation.result()

        # Procesar resultados y guardar en Cosmos DB
        for doc, custom_entities_result in zip(files, document_results):
            print(f"Procesando: {doc}")
            if custom_entities_result.kind == "CustomEntityRecognition":
                # Crear un diccionario para almacenar las entidades
                especificaciones = {
                    "id": str(uuid.uuid4()),  # Generar un ID único
                    "Marca": None,
                    "Modelo": None,
                    "Procesador": None,
                    "RAM": None,
                    "Almacenamiento": None,
                    "Tarjeta gráfica": None,
                    "Pulgadas": None,
                    "Precio": None,
                    "Frecuencia procesador": None,
                    "tipoDeOrdenador": "Portátil"  # Campo de clave de partición añadido
                }

                # Mapear entidades reconocidas al diccionario
                for entity in custom_entities_result.entities:
                    if entity.category in especificaciones:
                        if entity.category == "Precio":
                            # Quitar símbolo de euros y convertir a float
                            especificaciones[entity.category] = float(entity.text.replace('€', '').replace('.', '').replace(',', '.'))
                        elif entity.category == "Almacenamiento":
                            # Quitar "GB"
                            especificaciones[entity.category] = entity.text.replace('GB', '').strip()
                        elif entity.category == "Frecuencia procesador":
                            # Quitar "GHz"
                            especificaciones[entity.category] = entity.text.replace('GHz', '').strip()
                        else:
                            especificaciones[entity.category] = entity.text

                # Asegurarse de que los campos vacíos se guarden como None
                for key in especificaciones:
                    if especificaciones[key] == '':
                        especificaciones[key] = None

                # Mostrar especificaciones antes de guardar
                print(f"Especificaciones antes de guardar: {especificaciones}")

                # Guardar en Cosmos DB
                try:
                    container.upsert_item(especificaciones)
                    print(f"Guardado en Cosmos DB: {especificaciones}")
                except exceptions.CosmosHttpResponseError as ex:
                    print(f"Error al guardar en Cosmos DB: {ex}")

            elif custom_entities_result.is_error is True:
                print(f"Error en el documento {doc}: {custom_entities_result.error.message}")

    except Exception as ex:
        print(ex)

if __name__ == "__main__":
    main()
