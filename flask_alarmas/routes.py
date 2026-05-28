from flask import render_template, request, jsonify
import Modulos.Crear_Excel as Crear_Excel
import Modulos.Modificación_Correos as Modificación_Correos
import Modulos.SMTP as SMTP
import os
from datetime import datetime, timedelta
from pymongo import MongoClient

def registrar_rutas(app):

    @app.route('/')
    def index():
        return render_template('index.html', title='Inicio - Sistema de Alarmas')

    @app.route("/monitor")
    def monitor():
        """Muestra la interfaz del monitor. 
        El JavaScript en el navegador recibirá los datos vía SocketIO."""
        return render_template("monitor.html", title='Monitor en Tiempo Real')

    @app.route('/administrar_correos', methods=['GET', 'POST'])
    def administrar_correos():
        mensaje = None
        dfCorreos = Crear_Excel.obtener_df_correos()

        if request.method == 'POST':
            action = request.form.get('action')

            if action == 'add':
                Correo = request.form.get('Correo')
                Nombre = request.form.get('Nombre')
                if Correo and Nombre:
                    mensaje, dfCorreos = Modificación_Correos.agregar_correo(dfCorreos, Nombre, Correo)

            elif action == 'delete':
                correo_a_eliminar = request.form.get('correo_a_eliminar')
                if correo_a_eliminar:
                    mensaje, dfCorreos = Modificación_Correos.quitar_correo(dfCorreos, correo_a_eliminar)

            elif action == 'send_emails':
                SMTP.ejecutar_envio_alertas()
                mensaje = "Se ha iniciado el proceso de envío de alertas por correo."

        return render_template(
            'administrar_correos.html',
            title='Administración de correos',
            correos_df=dfCorreos,
            resultado=mensaje
        )

    @app.route('/api/ultimo', methods=['GET'])
    def api_ultimo():
        """Retorna el registro más reciente de MongoDB con todos sus campos."""
        try:
            mongo_uri = os.getenv('IOT_MONGO_URI')
            mongo_db  = os.getenv('IOT_MONGO_DB')
            mongo_col = os.getenv('IOT_MONGO_COLECCION')

            client    = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
            coleccion = client[mongo_db][mongo_col]

            ultimo = coleccion.find_one({}, {'_id': 0}, sort=[('fecha_registro', -1)])

            if not ultimo:
                return jsonify({"estado": "sin_datos", "datos": None}), 200

            return jsonify({"estado": "exitoso", "datos": ultimo}), 200

        except Exception as e:
            return jsonify({"estado": "error", "mensaje": str(e)}), 500

    @app.route('/api/historico', methods=['GET'])
    def api_historico():
        try:
            # 1. Obtener parámetros de conexión
            mongo_uri = os.getenv('IOT_MONGO_URI')
            mongo_db = os.getenv('IOT_MONGO_DB')
            mongo_col = os.getenv('IOT_MONGO_COLECCION')
            
            if not mongo_uri or not mongo_db or not mongo_col:
                return jsonify({
                    "estado": "error",
                    "mensaje": "Variables de entorno de MongoDB no configuradas."
                }), 500
                
            client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
            db = client[mongo_db]
            coleccion = db[mongo_col]
            
            # Asegurar índice en fecha_registro para búsquedas ultra rápidas
            coleccion.create_index([("fecha_registro", -1)])
            
            # 2. Definir rango de fechas
            rango = request.args.get('rango', '24h') # Opciones: 24h, 7d, 30d, custom
            inicio = request.args.get('inicio')       # Formato: YYYY-MM-DD
            fin = request.args.get('fin')             # Formato: YYYY-MM-DD
            
            ahora = datetime.utcnow()
            
            if inicio:
                # Caso rango personalizado (inicio y opcionalmente fin)
                try:
                    inicio_dt = datetime.strptime(inicio, "%Y-%m-%d")
                    if fin:
                        # Extender hasta el final del día fin (23:59:59)
                        fin_dt = datetime.strptime(fin, "%Y-%m-%d") + timedelta(days=1) - timedelta(seconds=1)
                    else:
                        fin_dt = ahora
                except ValueError:
                    return jsonify({
                        "estado": "error",
                        "mensaje": "Formato de fecha inválido. Utilice YYYY-MM-DD."
                    }), 400
            else:
                # Caso de rangos rápidos predefinidos
                if rango == '24h':
                    inicio_dt = ahora - timedelta(hours=24)
                elif rango == '7d':
                    inicio_dt = ahora - timedelta(days=7)
                elif rango == '30d':
                    inicio_dt = ahora - timedelta(days=30)
                else:
                    inicio_dt = ahora - timedelta(hours=24)
                fin_dt = ahora
                
            # 3. Consultar MongoDB
            query = {
                "fecha_registro": {
                    "$gte": inicio_dt,
                    "$lte": fin_dt
                }
            }
            
            # Traer los datos ordenados del más antiguo al más nuevo (ideal para graficar series temporales)
            # Excluimos '_id' para evitar problemas de serialización de ObjectId en JSON
            registros = list(coleccion.find(query, {"_id": 0}).sort("fecha_registro", 1))
            
            # Obtener usuarios del Excel
            df_usuarios = Crear_Excel.obtener_df_correos()
            usuarios = []
            if not df_usuarios.empty and 'Nombre' in df_usuarios.columns and 'Correo' in df_usuarios.columns:
                # Retornamos una lista de diccionarios con 'Nombre' y 'Correo'
                usuarios = df_usuarios[['Nombre', 'Correo']].to_dict('records')
            
            return jsonify({
                "estado": "exitoso",
                "rango_aplicado": {
                    "tipo": "personalizado" if inicio else rango,
                    "inicio": inicio_dt.isoformat() + "Z",
                    "fin": fin_dt.isoformat() + "Z",
                    "total_registros": len(registros)
                },
                "datos": registros,
                "Usuarios": usuarios
            }), 200
            
        except Exception as e:
            return jsonify({
                "estado": "error",
                "mensaje": f"Ocurrió un error al consultar el histórico: {str(e)}"
            }), 500

    @app.route('/api/solo_historico', methods=['GET'])
    def api_solo_historico():
        """Retorna únicamente el histórico de datos de MongoDB filtrado por rango."""
        try:
            mongo_uri = os.getenv('IOT_MONGO_URI')
            mongo_db = os.getenv('IOT_MONGO_DB')
            mongo_col = os.getenv('IOT_MONGO_COLECCION')
            
            if not mongo_uri or not mongo_db or not mongo_col:
                return jsonify({"estado": "error", "mensaje": "Configuración de Mongo incompleta."}), 500
                
            client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
            coleccion = client[mongo_db][mongo_col]
            
            # Asegurar índice para optimizar la consulta
            coleccion.create_index([("fecha_registro", -1)])
            
            rango = request.args.get('rango', '24h')
            inicio = request.args.get('inicio')
            fin = request.args.get('fin')
            ahora = datetime.utcnow()
            
            if inicio:
                try:
                    inicio_dt = datetime.strptime(inicio, "%Y-%m-%d")
                    if fin:
                        fin_dt = datetime.strptime(fin, "%Y-%m-%d") + timedelta(days=1) - timedelta(seconds=1)
                    else:
                        fin_dt = ahora
                except ValueError:
                    return jsonify({"estado": "error", "mensaje": "Formato de fecha inválido (YYYY-MM-DD)."}), 400
            else:
                if rango == '24h':
                    inicio_dt = ahora - timedelta(hours=24)
                elif rango == '7d':
                    inicio_dt = ahora - timedelta(days=7)
                elif rango == '30d':
                    inicio_dt = ahora - timedelta(days=30)
                else:
                    inicio_dt = ahora - timedelta(hours=24)
                fin_dt = ahora
                
            query = {"fecha_registro": {"$gte": inicio_dt, "$lte": fin_dt}}
            registros = list(coleccion.find(query, {"_id": 0}).sort("fecha_registro", 1))
            
            return jsonify({
                "estado": "exitoso",
                "rango_aplicado": {
                    "inicio": inicio_dt.isoformat() + "Z",
                    "fin": fin_dt.isoformat() + "Z",
                    "total": len(registros)
                },
                "datos": registros
            }), 200
            
        except Exception as e:
            return jsonify({
                "estado": "error",
                "mensaje": f"Error al obtener histórico: {str(e)}"
            }), 500

    @app.route('/api/usuarios', methods=['GET'])
    def api_usuarios():
        """Retorna únicamente la lista de usuarios registrados en el Excel."""
        try:
            df_usuarios = Crear_Excel.obtener_df_correos()
            usuarios = []
            
            if not df_usuarios.empty:
                # Verificar que las columnas existan antes de filtrar
                columnas_requeridas = ['Nombre', 'Correo']
                if all(col in df_usuarios.columns for col in columnas_requeridas):
                    usuarios = df_usuarios[columnas_requeridas].to_dict('records')
                else:
                    usuarios = df_usuarios.to_dict('records')
            
            return jsonify({
                "estado": "exitoso",
                "total_usuarios": len(usuarios),
                "usuarios": usuarios
            }), 200
            
        except Exception as e:
            return jsonify({
                "estado": "error",
                "mensaje": f"Error al obtener usuarios: {str(e)}"
            }), 500
