import streamlit as st
from dotenv import load_dotenv
import os
from azure.cosmos import CosmosClient, exceptions

def main():
    try:
        # Cargar variables de entorno
        load_dotenv()
        cosmos_endpoint = os.getenv('COSMOS_ENDPOINT')
        cosmos_key = os.getenv('COSMOS_KEY')

        # Crear cliente de Cosmos DB
        cosmos_client = CosmosClient(cosmos_endpoint, cosmos_key)
        database = cosmos_client.get_database_client("OrdenadoresDB")
        container = database.get_container_client("Especificaciones")

        st.title("Mostrar Todos los Ordenadores")

        # Consultar todos los documentos en el contenedor
        query = "SELECT * FROM c"
        documents = container.query_items(query, enable_cross_partition_query=True)

        # Mostrar resultados
        if documents:
            st.write("Ordenadores encontrados:")
            for document in documents:
                st.json(document)  # Mostrar cada documento en formato JSON
        else:
            st.write("No se encontraron ordenadores en la base de datos.")

    except exceptions.CosmosHttpResponseError as ex:
        st.error(f"Error en Cosmos DB: {ex.message}")
    except Exception as ex:
        st.error(f"Error: {ex}")

if __name__ == "__main__":
    main()
