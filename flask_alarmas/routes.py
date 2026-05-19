from flask import render_template, request, jsonify
import Modulos.Crear_Excel as Crear_Excel
import Modulos.Modificación_Correos as Modificación_Correos
import Modulos.SMTP as SMTP

def registrar_rutas(app):

    @app.route('/')
    def index():
        return render_template('index.html', title='Inicio - Sistema de Alarmas')

    @app.route("/monitor")
    def monitor():
        # TODO: Aquí deberías leer el último dato directamente desde MongoDB
        # Por ahora enviamos un diccionario vacío o datos de prueba
        data = {"mensaje": "Conexión a base de datos pendiente"}
        return render_template("monitor.html", data=data)

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
