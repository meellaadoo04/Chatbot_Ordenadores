# Aplicación de Búsqueda de Ordenadores

## Resumen

Esta aplicación permite a los usuarios buscar ordenadores a través de una interfaz web intuitiva desarrollada con Streamlit. Los usuarios pueden realizar búsquedas utilizando texto natural o filtros avanzados como marca y tamaño de pantalla. La aplicación se conecta a una base de datos de Azure Cosmos DB para recuperar información sobre los ordenadores disponibles, y utiliza servicios de inteligencia artificial de Azure para mejorar la experiencia de búsqueda.

## Funcionalidades

- **Búsqueda Inteligente**: Permite a los usuarios describir el ordenador que buscan mediante texto natural.
- **Filtros Avanzados**: Los usuarios pueden aplicar filtros por marca y pulgadas para refinar su búsqueda.
- **Resetear Filtros**: Opción para restablecer los filtros a su estado por defecto y mostrar todos los resultados.
- **Resultados de Búsqueda**: Muestra los resultados de la búsqueda en función de los criterios seleccionados.
- **Subir Pdf a la base de datos**: Document Intelligence escanea el pdf y extrae los valores clave con los que los has entrenado y te los guarda en la base de datos de MongoDB

## Servicios Utilizados

1. **Streamlit**: Framework utilizado para crear la interfaz de usuario de la aplicación y poder interacturar con el chatBot.

2. **Azure Cosmos DB**: Base de datos utilizada para almacenar y recuperar información sobre los ordenadores.

3. **Azure Cognitive Services - Language**: Servicio de inteligencia artificial utilizado para reconocer las Intent y las Entities que en este caso son pulgadas y marca y poder asi reconocerlas en las consultas del usuario y darle una respuesta que se ajuste a sus requisitos.

4. **Azure Document Intelligence**: Servicio utilizado para extraer información de documentos PDF relacionados con los ordenadores.
Cosmos DB.

## Acceso
https://meellaadoo04-chatbot-ordenadores-chatordenadores-zovk2l.streamlit.app/

## Instalación

Para ejecutar la aplicación, asegúrate de tener instalado Python y Streamlit. Luego, clona este repositorio y ejecuta:

```bash
pip install -r requirements.txt
streamlit run ChatOrdenadores.py


