SISTEMA DE ASISTENCIA - Instrucciones de Uso
============================================

REQUISITOS:
  Python 3.8+ con las librerías: Flask, ReportLab

INSTALACIÓN (una sola vez):
  pip install flask reportlab

INICIAR EL SISTEMA:
  python app.py

Luego abre en tu navegador:  http://localhost:5000

------------------------------------------------------------
FUNCIONALIDADES:
  ✅ Modo claro / oscuro (botón en la cabecera)
  ✅ Agregar grados con nombre, sección y profesor
  ✅ Editar grado (nombre, sección, profesor)
  ✅ Agregar alumnos con copiar y pegar (uno por línea)
  ✅ Editar nombre de alumnos
  ✅ Registrar asistencia por fecha (Presente / Ausente)
  ✅ Botón "Todos Presentes" / "Todos Ausentes"
  ✅ Cambiar fecha para ver asistencia de otro día
  ✅ Descargar reporte PDF diario con:
       - Nombre del profesor
       - Tabla de presentes
       - Tabla de ausentes
       - Estadísticas del día
       - Espacio para firma y sello
  ✅ Respaldo automático en data.json (nada se borra)

NOTAS DE SEGURIDAD:
  - Todos los datos se guardan en "data.json"
  - No hay opción de borrar — solo agregar y modificar
  - Haz copias del archivo data.json para respaldo externo
