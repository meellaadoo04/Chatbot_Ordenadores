import streamlit as st
from dotenv import load_dotenv
import os
from azure.cosmos import CosmosClient, exceptions
from azure.core.credentials import AzureKeyCredential
from azure.ai.language.conversations import ConversationAnalysisClient

def main():
    try:
        # Cargar variables de entorno
        load_dotenv()
        ls_prediction_endpoint = os.getenv('LS_CONVERSATIONS_ENDPOINT')
        ls_prediction_key = os.getenv('LS_CONVERSATIONS_KEY')
        cosmos_endpoint = os.getenv('COSMOS_ENDPOINT')
        cosmos_key = os.getenv('COSMOS_KEY')

        # Crear cliente de Cosmos DB
        cosmos_client = CosmosClient(cosmos_endpoint, cosmos_key)
        database = cosmos_client.get_database_client("OrdenadoresDB")
        container = database.get_container_client("Especificaciones")

        st.title("🔍 Buscador Inteligente de Ordenadores")

        # Entrada del usuario
        user_input = st.text_input("¿Qué ordenador estás buscando?", "")

        if user_input:
            # Cliente para CLU
            client = ConversationAnalysisClient(
                ls_prediction_endpoint, AzureKeyCredential(ls_prediction_key)
            )

            # Configuración de CLU
            cls_project = 'OrdenadoresConversational'
            deployment_slot = 'IntentOrdenadores'

            # Analizar consulta
            with client:
                result = client.analyze_conversation(
                    task={
                        "kind": "Conversation",
                        "analysisInput": {
                            "conversationItem": {
                                "participantId": "1",
                                "id": "1",
                                "modality": "text",
                                "language": "es",
                                "text": user_input
                            },
                            "isLoggingEnabled": False
                        },
                        "parameters": {
                            "projectName": cls_project,
                            "deploymentName": deployment_slot,
                            "verbose": True
                        }
                    }
                )

            # Mostrar respuesta de CLU en la terminal para depuración
            print("Respuesta de CLU:", result)

            entities = result["result"]["prediction"]["entities"]

            # Normalizar entidades
            search_criteria = {
                "marca": None,
                "pulgadas": None,
            }

            for entity in entities:
                category = entity["category"].lower().strip()  # Limpia espacios extra
                text = entity["text"].strip()
                
                print(f"Detectado -> Categoría: {category}, Texto: {text}")  # Debugging

                if category == "marca":
                    search_criteria["marca"] = text.upper()
                elif category == "pulgadas":
                    search_criteria["pulgadas"] = text.replace(',', '.')

            print("Criterios de búsqueda:", search_criteria)  # Depuración

            # Construcción de consulta dinámica
            query_parts = []
            parameters = []

            if search_criteria["marca"]:
                query_parts.append("c.Marca = @marca")
                parameters.append({"name": "@marca", "value": search_criteria["marca"]})
                
            if search_criteria["pulgadas"]:
                query_parts.append("c.Pulgadas = @pulgadas")
                parameters.append({"name": "@pulgadas", "value": search_criteria["pulgadas"]})

            # Ejecutar consulta
            if query_parts:
                query = "SELECT * FROM c WHERE " + " AND ".join(query_parts)
                print("Consulta SQL:", query)
                items = list(container.query_items(
                    query=query,
                    parameters=parameters,
                    enable_cross_partition_query=True
                ))
            else:
                items = list(container.query_items(
                    query="SELECT * FROM c",
                    enable_cross_partition_query=True
                ))

            # Mostrar resultados
            if items:
                st.success(f"🎉 Encontrados {len(items)} ordenadores:")
                for item in items:
                    with st.expander(f"{item['Marca']} {item['Modelo']}"):
                        st.markdown(f"""
                        **Especificaciones:**
                        - 💻 Procesador: {item.get('Procesador', 'N/A')}
                        - 🖥️ Pantalla: {item.get('Pulgadas', 'N/A')} pulgadas
                        - 🧠 RAM: {item.get('RAM', 'N/A') or 'N/A'} GB
                        - 💾 Almacenamiento: {item.get('Almacenamiento', 'N/A')}
                        - 💰 Precio: {item.get('Precio', 'N/A')} €
                        """)
            else:
                st.warning("⚠️ No se encontraron ordenadores con esos criterios")

    except exceptions.CosmosHttpResponseError as ex:
        st.error(f"🚨 Error en la base de datos: {ex.message}")
    except Exception as ex:
        st.error(f"❌ Error inesperado: {str(ex)}")

if __name__ == "__main__":
    main()
