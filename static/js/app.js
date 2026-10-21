(function () {
  "use strict";

  function iconos() { if (window.lucide) window.lucide.createIcons({ attrs: { "stroke-width": 1.7 } }); }

  // Menú lateral en celular
  function menu() {
    var lateral = document.querySelector(".lateral");
    var velo = document.querySelector(".velo");
    if (!lateral) return;
    function abrir(si) {
      lateral.classList.toggle("abierto", si);
      if (velo) velo.classList.toggle("visible", si);
      document.body.style.overflow = si ? "hidden" : "";
    }
    document.querySelectorAll("[data-abrir-menu]").forEach(function (b) {
      b.addEventListener("click", function () { abrir(!lateral.classList.contains("abierto")); });
    });
    if (velo) velo.addEventListener("click", function () { abrir(false); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") abrir(false); });
  }

  // Cronómetro de servicios en proceso
  function cronometros() {
    var els = document.querySelectorAll("[data-desde]");
    if (!els.length) return;
    function pintar() {
      var ahora = Date.now();
      els.forEach(function (el) {
        var seg = Math.max(0, Math.floor((ahora - new Date(el.dataset.desde).getTime()) / 1000));
        var h = Math.floor(seg / 3600), m = Math.floor((seg % 3600) / 60), s = seg % 60;
        el.textContent = (h ? h + ":" : "") + String(m).padStart(h ? 2 : 1, "0") + ":" + String(s).padStart(2, "0");
        var est = parseInt(el.dataset.estimado || "0", 10);
        if (est && seg / 60 > est) el.classList.add("text-danger");
      });
    }
    pintar();
    setInterval(pintar, 1000);
  }

  // Confirmación simple antes de acciones irreversibles
  function confirmaciones() {
    document.querySelectorAll("form[data-confirmar]").forEach(function (f) {
      f.addEventListener("submit", function (e) { if (!confirm(f.dataset.confirmar)) e.preventDefault(); });
    });
  }

  // Evita doble envío en conexiones lentas del salón
  function unEnvio() {
    document.querySelectorAll("form").forEach(function (f) {
      f.addEventListener("submit", function () {
        if (f.dataset.enviado) return;
        f.dataset.enviado = "1";
        setTimeout(function () {
          f.querySelectorAll("button[type=submit]").forEach(function (b) { b.disabled = true; });
        }, 0);
      });
    });
  }

  // Al elegir servicio, sugiere peluqueros (estilista fijo y especialistas primero)
  function sugerencias() {
    var servicio = document.querySelector("[data-sugerir-url]");
    var destino = document.getElementById("id_peluquero");
    if (!servicio || !destino) return;
    function cargar() {
      if (!servicio.value) return;
      var url = servicio.dataset.sugerirUrl + "?servicio=" + encodeURIComponent(servicio.value) +
        (servicio.dataset.cliente ? "&cliente=" + encodeURIComponent(servicio.dataset.cliente) : "");
      fetch(url, { headers: { "X-Requested-With": "fetch" } })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          var actual = destino.value;
          destino.innerHTML = "";
          if (!data.peluqueros.length) {
            destino.add(new Option("Nadie tiene habilitado este servicio", ""));
            return;
          }
          data.peluqueros.forEach(function (p) {
            var etiqueta = p.nombre;
            var notas = [];
            if (p.fijo) notas.push("estilista fijo");
            if (p.especialista) notas.push("especialista");
            notas.push(p.ocupado ? "ocupado" : "disponible");
            destino.add(new Option(etiqueta + " (" + notas.join(", ") + ")", p.run));
          });
          if (actual && destino.querySelector('option[value="' + actual + '"]')) destino.value = actual;
        });
    }
    servicio.addEventListener("change", cargar);
    cargar();
  }

  // Cambio entre modo claro y oscuro; la elección queda guardada en este dispositivo
  function tema() {
    document.querySelectorAll("[data-cambiar-tema]").forEach(function (b) {
      b.addEventListener("click", function () {
        var nuevo = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
        // Sin transiciones durante el cambio, para que todo cambie de una vez
        document.documentElement.classList.add("sin-transicion");
        setTimeout(function () { document.documentElement.classList.remove("sin-transicion"); }, 50);
        document.documentElement.dataset.theme = nuevo;
        document.documentElement.setAttribute("data-bs-theme", nuevo);
        var meta = document.querySelector('meta[name="theme-color"]');
        if (meta) meta.content = nuevo === "dark" ? "#26262b" : "#e6e6e9";
        try { localStorage.setItem("tema", nuevo); } catch (e) {}
      });
    });
  }

  // Formularios con confirmación junto al botón: "Guardado" tras guardar, "Cambios sin guardar" al editar
  function guardables() {
    var clave = new URLSearchParams(location.search).get("guardado");
    if (clave) {
      var marca = document.querySelector('[data-clave="' + clave + '"]');
      if (marca) {
        marca.classList.remove("d-none");
        var det = marca.closest("details");
        if (det) det.open = true;
      }
      // Limpia el parámetro para que al recargar no vuelva a decir "Guardado".
      history.replaceState(null, "", location.pathname + location.hash);
    }
    var pendientes = 0;
    document.querySelectorAll("form[data-guardable]").forEach(function (f) {
      var sucio = false;
      f.addEventListener("input", function () {
        if (!sucio) { sucio = true; pendientes++; }
        f.querySelectorAll("[data-guardado]").forEach(function (e) { e.classList.add("d-none"); });
        f.querySelectorAll("[data-sin-guardar]").forEach(function (e) { e.classList.remove("d-none"); });
      });
      f.addEventListener("submit", function () { if (sucio) { sucio = false; pendientes--; } });
    });
    // Avisa antes de salir de la página si quedó algo escrito sin guardar.
    window.addEventListener("beforeunload", function (e) {
      if (pendientes > 0) { e.preventDefault(); e.returnValue = ""; }
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    iconos(); tema(); guardables(); menu(); cronometros(); confirmaciones(); unEnvio(); sugerencias();
  });
})();
