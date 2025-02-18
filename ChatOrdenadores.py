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
            page_icon="💻",
            layout="wide",
        )
        st.markdown(
            "<h1 style='text-align: center; margin-bottom: 20px;'>💻 IA Computer Assistant Shop 🤖</h1>",
            unsafe_allow_html=True
        )
        
        # Barra lateral: Filtros y subida de PDF
        st.sidebar.title("Opciones de Búsqueda")
        
        # Inicializar session_state si no existen
        if "marca_select" not in st.session_state:
            st.session_state.marca_select = ""
        if "pulgadas_select" not in st.session_state:
            st.session_state.pulgadas_select = ""

        # Filtros avanzados
        with st.sidebar.expander("🔍 Filtros Avanzados"):
            marcas, pulgadas = obtener_marcas_y_pulgadas(container)
            
            selected_brand = st.selectbox("Marca", [""] + marcas, key="marca_select")
            selected_size = st.selectbox("Pulgadas", [""] + pulgadas, key="pulgadas_select")

        
        # Sección para subir PDF
        st.sidebar.header("📤 Subir Nuevo Producto")
        uploaded_file = st.sidebar.file_uploader("Subir ficha técnica (PDF)", type="pdf")
        if uploaded_file is not None:
            subir_pdf(uploaded_file, container)

       # Búsqueda principal por texto natural
        st.header("Búsqueda Inteligente")

        # Contenedor con dos columnas
        col1, col2 = st.columns([4, 1])

        with col1:
            user_input = st.text_input("Describe el ordenador que buscas:", "")

        with col2:
            # MOdificar el botón usando CSS
            st.markdown(
                """
                <style>
                .stButton button {
                    margin-top: 12px;
                }
                </style>
                """,
                unsafe_allow_html=True
            )
            buscar_natural = st.button("🔍 Buscar", help="Buscar ordenadores según la descripción proporcionada.",)


        # Sección para mostrar resultados
        st.header("Resultados de Búsqueda")
        
        # Procesar búsqueda natural
        if buscar_natural and user_input:
            # Cliente para CLU
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

            # Procesar entidades de pulgadas
            def procesar_entidades_pulgadas(entities):
                pulgadas_entities = sorted(
                    [e for e in entities if e['category'].lower() == 'pulgadas'],
                    key=lambda x: x['offset']
                )
                
                consolidated = []
                i = 0
                while i < len(pulgadas_entities):
                    current = pulgadas_entities[i]
                    merged_text = current['text']
                    
                    j = i + 1
                    while j < len(pulgadas_entities):
                        next_entity = pulgadas_entities[j]
                        if (current['offset'] + current['length']) == next_entity['offset']:
                            merged_text += next_entity['text']
                            current['length'] += next_entity['length']
                            j += 1
                        else:
                            break
                            
                    current['text'] = merged_text.replace(',', '.')
                    consolidated.append(current)
                    i = j
                    
                return [e for e in entities if e['category'].lower() != 'pulgadas'] + consolidated

            entities = procesar_entidades_pulgadas(entities)

            # Construir criterios de búsqueda
            search_criteria = {"marca": None, "pulgadas": None}
            for entity in entities:
                category = entity["category"].lower().strip()
                text = entity["text"].strip()
                
                if category == "marca":
                    search_criteria["marca"] = text.upper()
                elif category == "pulgadas":
                    search_criteria["pulgadas"] = text.replace(',', '.')

            # Construir consulta
            query_parts = []
            parameters = []
            if search_criteria["marca"]:
                query_parts.append("c.Marca = @marca")
                parameters.append({"name": "@marca", "value": search_criteria["marca"]})
            if search_criteria["pulgadas"]:
                query_parts.append("c.Pulgadas = @pulgadas")
                parameters.append({"name": "@pulgadas", "value": search_criteria["pulgadas"]})

            items = ejecutar_consulta(container, query_parts, parameters)

        # Procesar búsqueda por filtros
        if st.sidebar.button("✅ Aplicar Filtros", key="aplicar_filtros"):
            search_criteria = {
                "marca": selected_brand,
                "pulgadas": selected_size
            }
            
            query_parts = []
            parameters = []
            if search_criteria["marca"]:
                query_parts.append("c.Marca = @marca")
                parameters.append({"name": "@marca", "value": search_criteria["marca"]})
            if search_criteria["pulgadas"]:
                query_parts.append("c.Pulgadas = @pulgadas")
                parameters.append({"name": "@pulgadas", "value": search_criteria["pulgadas"]})

            items = ejecutar_consulta(container, query_parts, parameters)
            

        # Botón de Resetear debajo
        if st.sidebar.button("🔄 Resetear Filtros", key="resetear_filtros"):
            st.session_state.clear()  # Limpia todos los valores de session_state
            st.rerun()  # Recargar la interfaz para aplicar los cambios


        # Mostrar resultados
        if 'items' in locals():
            mostrar_resultados(items)

    except Exception as e:
        st.error(f"❌ Error en la aplicación: {str(e)}")

def ejecutar_consulta(container, query_parts, parameters):
    """Ejecuta la consulta en Cosmos DB"""
    try:
        if query_parts:
            query = "SELECT * FROM c WHERE " + " AND ".join(query_parts)
            return list(container.query_items(
                query=query,
                parameters=parameters,
                enable_cross_partition_query=True
            ))
        else:
            return list(container.query_items(
                query="SELECT * FROM c",
                enable_cross_partition_query=True
            ))
    except exceptions.CosmosHttpResponseError as e:
        st.error(f"🚨 Error en la base de datos: {e.message}")
        return []

def mostrar_resultados(items):
    """Muestra los resultados en formato tarjeta"""
    if items:
        st.success(f"🎉 Encontrados {len(items)} ordenadores:")
        cols = st.columns(3)
        for idx, item in enumerate(items):
            with cols[idx % 3]:
                marca = item.get("Marca", "").strip()
                modelo = item.get("Modelo", "").strip()
                procesador = item.get("Procesador", "N/A")
                pulgadas = item.get("Pulgadas", "N/A")
                ram = item.get("RAM", "N/A")
                almacenamiento = item.get("Almacenamiento", "N/A")
                precio = item.get("Precio", "N/A")

                ## Mostrar especificaciones
                st.markdown(f"""
                <div style='
                    border: 1px solid #4B5B80; 
                    border-radius: 10px;
                    padding: 15px;
                    margin-bottom: 15px;
                    height: 350px;
                    background-color: #2E3B4E; 
                '>
                    <h4 style='color: #FFD700;'>{marca}</h4>  
                    <p style='color: #B0E0E6;'>{modelo}</p>  
                    <p style='color: #FFFFFF;'>💻 Procesador: {procesador}</p>
                    <p style='color: #FFFFFF;'>🖥️ Pantalla: {pulgadas} pulgadas</p>
                    <p style='color: #FFFFFF;'>🧠 RAM: {ram} </p>
                    <p style='color: #FFFFFF;'>💾 Almacenamiento: {almacenamiento} </p>
                    <p style='color: #FFFFFF;'>💰 Precio: €{precio}</p>
                </div>
                """, unsafe_allow_html=True)

    else:
        st.warning("⚠️ No se encontraron ordenadores con esos criterios")


if __name__ == "__main__":
    main()


