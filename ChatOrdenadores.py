import streamlit as st
from dotenv import load_dotenv
import os
import re
from datetime import datetime
from azure.cosmos import CosmosClient, exceptions
from azure.core.credentials import AzureKeyCredential
from azure.ai.language.conversations import ConversationAnalysisClient
from azure.ai.formrecognizer import DocumentAnalysisClient


# Cargar variables de entorno
load_dotenv()

def obtener_marcas_y_pulgadas(container):
    try:
        load_dotenv()
        # Consultas para obtener marcas y pulgadas únicas
        query_marcas = "SELECT DISTINCT c.Marca FROM c"
        query_pulgadas = "SELECT DISTINCT c.Pulgadas FROM c"

        marcas = list(container.query_items(query=query_marcas, enable_cross_partition_query=True))
        pulgadas = list(container.query_items(query=query_pulgadas, enable_cross_partition_query=True))

        # Extraer los valores, asegurándose de que no sean None
        marcas = [item['Marca'] for item in marcas if 'Marca' in item]
        pulgadas = [item['Pulgadas'] for item in pulgadas if 'Pulgadas' in item and item['Pulgadas'] is not None]

        return marcas, pulgadas
    except exceptions.CosmosHttpResponseError as e:
        st.error(f"🚨 Error al obtener marcas y pulgadas: {str(e)}")
        return [], []
    except Exception as e:
        st.error(f"❌ Error inesperado: {str(e)}")
        return [], []

def transformar_entidades(entidades):
    """
    Transforma el diccionario de entidades extraído por el modelo en un formato plano
    con las claves deseadas.
    """
    resultado = {}

    # Marca
    resultado["Marca"] = entidades.get("marca", {}).get("valor", None)
    # Modelo
    resultado["Modelo"] = entidades.get("modelo", {}).get("valor", None)
    # Procesador: quitar saltos de línea y, si hay guiones, tomar la parte antes del guión
    proc_val = entidades.get("procesador", {}).get("valor", None)
    if proc_val:
        proc_val = proc_val.replace("\n", " ")
        tokens = proc_val.split()
        nuevo_tokens = [token.split("-")[0] if "-" in token else token for token in tokens]
        resultado["Procesador"] = " ".join(nuevo_tokens)
    else:
        resultado["Procesador"] = None
    # RAM
    resultado["RAM"] = entidades.get("ram", {}).get("valor", None)
    # Almacenamiento: quitar "GB" y espacios
    almacen_val = entidades.get("almacenamiento", {}).get("valor", None)
    if almacen_val:
        resultado["Almacenamiento"] = almacen_val.replace("GB", "").strip()
    else:
        resultado["Almacenamiento"] = None
    # Tarjeta gráfica (se puede ajustar si se requiere lógica específica)
    resultado["Tarjeta gráfica"] = entidades.get("modelo", {}).get("valor", None)
    # Pulgadas: extraer dígitos y permitir coma decimal
    pulg_val = entidades.get("pulgadas", {}).get("valor", None)
    if pulg_val:
        num = re.sub(r"[^\d,]", "", pulg_val)
        resultado["Pulgadas"] = num.replace(",", ".") if num != "" else None
    else:
        resultado["Pulgadas"] = None
    # Precio: quitar símbolo de euro, separadores y convertir a entero
    precio_val = entidades.get("precio", {}).get("valor", None)
    if precio_val:
        precio_val = precio_val.replace("€", "").strip().replace(".", "").replace(",", ".")
        try:
            precio_num = float(precio_val)
            resultado["Precio"] = int(round(precio_num))
        except Exception:
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

def init_form_recognizer():
    """
    Inicializa y retorna el cliente de Form Recognizer y el modelo custom.
    """
    AZURE_ENDPOINT_DOC = os.getenv("AZURE_ENDPOINT_DOCUMEN_INTELLIGENCE")
    AZURE_API_KEY_DOC = os.getenv("AZURE_API_KEY_DOCUMEN_INTELLIGENCE")
    MODEL_ID = os.getenv("MODEL")
    if not all([AZURE_ENDPOINT_DOC, AZURE_API_KEY_DOC, MODEL_ID]):
        raise ValueError("Faltan variables de entorno para Form Recognizer.")
    client = DocumentAnalysisClient(
        endpoint=AZURE_ENDPOINT_DOC,
        credential=AzureKeyCredential(AZURE_API_KEY_DOC)
    )
    return client, MODEL_ID

document_analysis_client, MODEL_ID = init_form_recognizer()

def subir_pdf(file, container):
    """
    Procesa el PDF subido mediante Custom Named Entity Recognition y lo inserta en la BD.
    """
    try:
        poller = document_analysis_client.begin_analyze_document(
            model_id=MODEL_ID,
            document=file
        )
        result = poller.result()
    except Exception as e:
        st.error(f"❌ Error al analizar el PDF: {e}")
        return

    st.write("📄 Se han extraído las siguientes entidades del PDF:")
    entidades_raw = {}
    for idx, (field_name, field_value) in enumerate(result.documents[0].fields.items()):
        st.write(f"{idx+1}. {field_name}: {field_value.value} (Confianza: {field_value.confidence})")
        entidades_raw[field_name] = {"valor": field_value.value, "confianza": field_value.confidence}

    # Transformar las entidades al formato deseado
    entidades_transformadas = transformar_entidades(entidades_raw)
    document_id = file.name  # Utilizamos el nombre del archivo como ID
    documento = {
        "id": document_id,
        "nombre_archivo": file.name,
        "fecha_procesamiento": datetime.now().isoformat(),
    }
    documento.update(entidades_transformadas)

    try:
        container.upsert_item(documento)
        st.success(f"✅ Documento '{file.name}' insertado en la base de datos.")
    except exceptions.CosmosHttpResponseError as e:
        st.error(f"❌ Error al insertar el documento en la base de datos: {e}")

#############################
# Función Principal
#############################

def main():
    try:
        load_dotenv()
        ls_prediction_endpoint = os.getenv('LS_CONVERSATIONS_ENDPOINT')
        ls_prediction_key = os.getenv('LS_CONVERSATIONS_KEY')
        cosmos_endpoint = os.getenv('COSMOS_ENDPOINT')
        cosmos_key = os.getenv('COSMOS_KEY')

        # Crear cliente de Cosmos DB y obtener el contenedor
        cosmos_client = CosmosClient(cosmos_endpoint, cosmos_key)
        database = cosmos_client.get_database_client("OrdenadoresDB")
        container = database.get_container_client("Especificaciones")

        st.set_page_config(
        page_icon="💻",  # Puedes usar un emoji como icono
        layout="wide",  # Opcional: cambia el diseño a ancho completo
        )
        st.markdown(
        "<h1 style='text-align: center;'>🔍 IA Computer Assistant Shop</h1>",
        unsafe_allow_html=True
        )
        
        # Barra lateral: Guía informativa y botón para subir PDF
        marcas, pulgadas = obtener_marcas_y_pulgadas(container)
        st.sidebar.title("Guía de Filtros Disponibles")
        with st.sidebar.expander("📌 Marcas Disponibles"):
            if marcas:
                for m in marcas:
                    st.write(m)
            else:
                st.write("No se encontraron marcas.")

        with st.sidebar.expander("📏 Pulgadas Disponibles"):
            if pulgadas:
                for p in pulgadas:
                    st.write(f"{p} pulgadas")
            else:
                st.write("No se encontraron pulgadas.")

        st.sidebar.header("Subir PDF")
        uploaded_file = st.sidebar.file_uploader("Selecciona un PDF para analizar", type=["pdf"])
        if uploaded_file is not None:
            subir_pdf(uploaded_file, container)

        # Entrada principal para la búsqueda
        user_input = st.text_input("¿Qué ordenador estás buscando?", "")
        if user_input:
            # Cliente para CLU (Conversation Language Understanding)
            client = ConversationAnalysisClient(ls_prediction_endpoint, AzureKeyCredential(ls_prediction_key))
            cls_project = 'OrdenadoresConversational'
            deployment_slot = 'IntentOrdenadores'
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

            entities = result["result"]["prediction"]["entities"]

            # Mostrar las entidades detectadas en la consola
            print("Entidades detectadas:", entities)

            def procesar_entidades_pulgadas(entities):
                # Filtrar solo entidades de pulgadas y ordenar por posición en el texto
                pulgadas_entities = sorted(
                    [e for e in entities if e['category'].lower() == 'pulgadas'],
                    key=lambda x: x['offset']
                )
                
                # Consolidar entidades adyacentes
                consolidated = []
                i = 0
                while i < len(pulgadas_entities):
                    current = pulgadas_entities[i]
                    merged_text = current['text']
                    
                    # Buscar entidades siguientes adyacentes
                    j = i + 1
                    while j < len(pulgadas_entities):
                        next_entity = pulgadas_entities[j]
                        # Verificar si son adyacentes (offset actual + length = offset siguiente)
                        if (current['offset'] + current['length']) == next_entity['offset']:
                            merged_text += next_entity['text']
                            current['length'] += next_entity['length']
                            j += 1
                        else:
                            break
                            
                    # Actualizar la entidad consolidada
                    current['text'] = merged_text.replace(',', '.')
                    consolidated.append(current)
                    i = j
                    
                # Reemplazar las entidades originales de pulgadas
                return [e for e in entities if e['category'].lower() != 'pulgadas'] + consolidated

            # Dentro de la función main, modifica esta sección:
            entities = result["result"]["prediction"]["entities"]

            # Aplicar procesamiento especial para pulgadas
            entities = procesar_entidades_pulgadas(entities)

            # Mostrar las entidades detectadas en la consola
            print("Entidades detectadas (procesadas):", entities)

            # Normalizar entidades obtenidas
            search_criteria = {"marca": None, "pulgadas": None}
            for entity in entities:
                category = entity["category"].lower().strip()
                text = entity["text"].strip()
                # Se pueden dejar estos prints en la consola para depuración, pero no en la interfaz:
                # print(f"Detectado -> Categoría: {category}, Texto: {text}")
                if category == "marca":
                    if text.lower() == "samsung":  # Si es "samsung", convertir a mayúsculas
                        search_criteria["marca"] = text.upper()
                    else:
                        search_criteria["marca"] = text  # Mantener el formato original
                elif category == "pulgadas":
                    search_criteria["pulgadas"] = text.replace(',', '.')
            # Tampoco mostramos los criterios en la interfaz
            # print("Criterios de búsqueda:", search_criteria)

            # Construcción de consulta dinámica basada en los criterios de CLU
            query_parts = []
            parameters = []
            if search_criteria["marca"]:
                query_parts.append("c.Marca = @marca")
                parameters.append({"name": "@marca", "value": search_criteria["marca"]})
            if search_criteria["pulgadas"]:
                query_parts.append("c.Pulgadas = @pulgadas")
                parameters.append({"name": "@pulgadas", "value": search_criteria["pulgadas"]})
            if query_parts:
                query = "SELECT * FROM c WHERE " + " AND ".join(query_parts)
                print(parameters)  
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
            if items:
                st.success(f"🎉 Encontrados {len(items)} ordenadores:")
                for item in items:
                    marca = item.get("Marca", "").strip()
                    modelo = item.get("Modelo", "").strip()
                    display_title = modelo if modelo.upper().startswith(marca.upper()) else f"{marca} {modelo}"
                    with st.expander(display_title):
                        st.markdown(f"""
                        **Especificaciones:**
                        - 💻 Procesador: {item.get('Procesador', 'N/A')}
                        - 🖥️ Pantalla: {item.get('Pulgadas', 'N/A')} pulgadas
                        - 🧠 RAM: {item.get('RAM', 'N/A')} 
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


