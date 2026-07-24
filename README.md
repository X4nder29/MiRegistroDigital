# MiRegistroDigital

Aplicación de escritorio para Windows que digitaliza, organiza y exporta documentos físicos del Registro Civil.

## ¿Qué hace?

MiRegistroDigital acompaña todo el flujo de digitalización: escanear o importar los documentos, corregir la imagen y reconocer automáticamente el número de serial de cada página, y exportar en PDF de forma masiva — además de cruzar lo digitalizado contra la estructura de carpetas del Registro Civil para detectar qué está completo y qué falta.

## Herramientas

### 📄 Digitalización
- Escanea directamente desde un escáner físico (compatible con dispositivos TWAIN, como el Kodak S2070) o importa PDFs e imágenes ya existentes.
- Reconocimiento óptico (OCR) que extrae automáticamente el número de serial de cada página.
- Corrección de perspectiva, enderezado y rotación manual, con zoom sobre la página actual.
- Marcadores y comentarios por página, y puntos de corte para separar grupos de "Antecedentes".
- Exportación masiva a PDF: un archivo por página, con marcadores, o agrupado por corte.

### 📋 Editor
- Reordena y organiza con arrastrar y soltar las páginas provenientes de varios PDFs importados.
- Une varios archivos PDF completos en uno solo, conservando cada origen como marcador.

### 👁️ Visualización
- Analiza la carpeta de Registros Civiles y cruza automáticamente los "Registros" con los "Antecedentes" por número de serial.
- Muestra qué está emparejado, qué falta de un lado o del otro, y detecta seriales duplicados.
- Combina un registro y su antecedente en un solo PDF con un clic.

## Empezar

Al abrir la aplicación se muestra una pantalla de inicio con las tres herramientas. Desde el menú **Archivo** se puede abrir y guardar el trabajo como un proyecto (`.miregistro`), y volver a esta pantalla en cualquier momento con **Cerrar herramienta**.

Los ajustes generales (calidad de escaneo, carpetas de destino, atajos de teclado, etc.) están disponibles desde el botón **⚙️ Ajustes**.
