import pymongo
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()
cosmos_endpoint = os.getenv('COSMOS_ENDPOINT').replace("https://", "").replace(":443", "")
cosmos_key = os.getenv('COSMOS_KEY')

# Construcción de la URI
uri = f"mongodb://{cosmos_endpoint}:{cosmos_key}@{cosmos_endpoint}/?ssl=true&replicaSet=globaldb"

try:
    # Conectar a MongoDB
    mongo_client = pymongo.MongoClient(uri)
    db = mongo_client['OrdenadoresDB']  # Base de datos

    # Verificar conexión con 'ping'
    mongo_client.admin.command('ping')
    print("✅ Conexión exitosa a MongoDB")

    # Listar colecciones disponibles
    collections = db.list_collection_names()
    print("Colecciones disponibles:", collections)

    # Verificar si la colección "Especificaciones" existe
    if "Especificaciones" in collections:
        print("✅ La colección 'Especificaciones' está disponible.")

        # Obtener un documento de prueba de la colección
        collection = db["Especificaciones"]
        test_doc = collection.find_one()

        if test_doc:
            print("✅ Documento encontrado en 'Especificaciones':")
            print(test_doc)  # Mostrar documento encontrado
        else:
            print("⚠️ La colección 'Especificaciones' está vacía.")
    else:
        print("🚨 La colección 'Especificaciones' NO existe en la base de datos.")

except Exception as e:
    print(f"🚨 ERROR en la conexión a MongoDB: {e}")
