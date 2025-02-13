from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest

# Configura tu endpoint y key
endpoint = "YOUR_FORM_RECOGNIZER_ENDPOINT"
key = "YOUR_FORM_RECOGNIZER_KEY"

# URL del PDF (asegúrate de que esté en Azure Blob Storage o una URL accesible)
formUrl = "https://<tu-cuenta-de-almacenamiento>.blob.core.windows.net/<tu-contenedor>/archivo.pdf"

# Crear el cliente de Document Intelligence
document_intelligence_client = DocumentIntelligenceClient(endpoint=endpoint, credential=AzureKeyCredential(key))

# Realizar la solicitud para analizar el PDF
poller = document_intelligence_client.begin_analyze_document(
    "prebuilt-read", AnalyzeDocumentRequest(url_source=formUrl)
)
result = poller.result()

# Imprimir el contenido extraído del PDF
print("Contenido extraído del PDF:")
print(result.content)

# Mostrar el texto extraído de cada página
for page in result.pages:
    print(f"---- Página {page.page_number} ----")
    for line in page.lines:
        print(f"Línea: {line.content}")
