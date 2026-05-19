const IMAGENES_VISCOSIDAD = JSON.parse(
    document.getElementById('imagenes-data').textContent
);

let images = Array.isArray(IMAGENES_VISCOSIDAD) ? IMAGENES_VISCOSIDAD : [];
let index = 0;


document.addEventListener("DOMContentLoaded", () => {

    // Obtener referencias a elementos del carousel
    const img = document.getElementById("imgViscosidad");
    const btnNext = document.getElementById("btnNext");
    const btnPrev = document.getElementById("btnPrev");

    // Si no hay imagen o el array está vacío, no hacer nada
    if (!img || images.length === 0) return;

    // Función para mostrar la imagen en la posición `i`
    function show(i) {
        // img.src se actualiza con la ruta correcta dentro de /static/Graficas/
        img.src = `/static/Graficas/${images[i]}`;
    }

    // Botón Siguiente
    btnNext.addEventListener("click", () => {
        index = (index + 1) % images.length; // Avanzar y volver al inicio si es necesario
        show(index);
    });

    // 6️⃣ Botón Anterior
    btnPrev.addEventListener("click", () => {
        index = (index - 1 + images.length) % images.length; // Retroceder y wrap-around
        show(index);
    });

    // 7️⃣ Mostrar la primera imagen al cargar
    show(index);
});

