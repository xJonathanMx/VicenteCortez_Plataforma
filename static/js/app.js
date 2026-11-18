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

  // Diálogo de confirmación con el estilo del sistema (reemplaza al confirm() del navegador)
  function dialogo(texto, textoSi, alAceptar) {
    var d = document.createElement("dialog");
    d.className = "dialogo";
    d.innerHTML = '<p class="dialogo-texto"></p><div class="dialogo-botones">' +
      '<button type="button" class="btn btn-relieve" data-no>Cancelar</button>' +
      '<button type="button" class="btn btn-negro" data-si></button></div>';
    d.querySelector(".dialogo-texto").textContent = texto;
    d.querySelector("[data-si]").textContent = textoSi || "Confirmar";
    function cerrar() { d.close(); d.remove(); }
    d.querySelector("[data-no]").addEventListener("click", cerrar);
    d.addEventListener("cancel", function () { d.remove(); });
    d.querySelector("[data-si]").addEventListener("click", function () { cerrar(); alAceptar(); });
    document.body.appendChild(d);
    d.showModal();
    d.querySelector("[data-si]").focus();
  }

  // Formularios o botones con data-confirmar="texto" piden confirmación antes de enviarse.
  // Si el texto está vacío, se envían directo (ej. iniciar servicio sin otros en curso).
  function confirmaciones() {
    document.querySelectorAll("form").forEach(function (f) {
      f.addEventListener("submit", function (e) {
        var origen = (e.submitter && e.submitter.dataset.confirmar) ? e.submitter : f;
        var texto = origen.dataset.confirmar;
        if (!texto || f.dataset.confirmado) return;
        e.preventDefault();
        var boton = e.submitter;
        dialogo(texto, origen.dataset.confirmarSi, function () {
          var campo = f.querySelector('input[name="confirmar"]');
          if (campo) campo.value = "1";
          f.dataset.confirmado = "1";
          if (f.requestSubmit) f.requestSubmit(boton); else f.submit();
        });
      });
    });
  }

  // Campos obligatorios vacíos: se marcan sin enviar, con el aviso junto al botón (form[data-validar])
  function validarAntes() {
    document.querySelectorAll("form[data-validar]").forEach(function (f) {
      var aviso = f.querySelector("[data-error-envio]");
      function limpiar(campo) {
        var caja = campo.closest(".campo-error");
        if (caja) caja.classList.remove("campo-error");
        if (caja) caja.querySelectorAll(".errorlist").forEach(function (e) { e.remove(); });
      }
      f.querySelectorAll("[required]").forEach(function (c) {
        c.addEventListener("change", function () { limpiar(c); });
      });
      f.addEventListener("submit", function (e) {
        var faltan = [];
        f.querySelectorAll("[required]").forEach(function (c) {
          var salvo = c.dataset.salvo && f.elements[c.dataset.salvo];
          if (c.value.trim() || (salvo && salvo.value)) return;
          faltan.push(c);
          var caja = c.parentElement;
          if (!caja.classList.contains("campo-error")) {
            caja.classList.add("campo-error");
            caja.insertAdjacentHTML("beforeend", '<ul class="errorlist"><li>Este campo es obligatorio.</li></ul>');
          }
        });
        if (!faltan.length) return;
        e.preventDefault();
        if (aviso) {
          aviso.querySelector("span").textContent = "Revisa los campos marcados.";
          aviso.classList.replace("d-none", "d-inline-flex");
        }
        faltan[0].focus({ preventScroll: true });
      });
    });
  }

  // Evita doble envío en conexiones lentas del salón
  function unEnvio() {
    document.querySelectorAll("form").forEach(function (f) {
      f.addEventListener("submit", function (e) {
        if (e.defaultPrevented || f.dataset.enviado) return;
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

    // Formateo automático de RUN mientras se escribe
document.querySelectorAll('[data-run]').forEach(function (input) {
  input.addEventListener('input', function () {
    if (!/^[\d.\-]+[kK]?$/.test(input.value)) return;
    var v = input.value.replace(/[^0-9kK]/g, '').toUpperCase().slice(0, 9);
    if (v.length > 1) {
      var cuerpo = v.slice(0, -1).replace(/\B(?=(\d{3})+(?!\d))/g, '.');
      v = cuerpo + '-' + v.slice(-1);
    }
    input.value = v;
  });
});

  // Lista de incentivos de la meta: agregar, quitar y mostrar el monto solo si es dinero
  function incentivos() {
    var plantilla = document.getElementById("plantilla-incentivo");
    if (!plantilla) return;
    var textos = { dinero: "Detalle (opcional)", regalo: "Ej. Kit de productos Kérastase", otro: "Ej. Día libre" };
    function preparar(fila) {
      var tipo = fila.querySelector("[data-tipo-incentivo]");
      var desc = fila.querySelector("[data-desc-incentivo]");
      var monto = fila.querySelector("[data-monto-incentivo]");
      function ajustar() {
        var esDinero = tipo.value === "dinero";
        fila.classList.toggle("sin-monto", !esDinero);
        if (!esDinero) monto.value = "";
        desc.placeholder = textos[tipo.value];
      }
      tipo.addEventListener("change", ajustar);
      fila.querySelector("[data-quitar-incentivo]").addEventListener("click", function () {
        var form = fila.closest("form");
        fila.remove();
        if (form) form.dispatchEvent(new Event("input", { bubbles: true }));
      });
      ajustar();
    }
    document.querySelectorAll(".fila-incentivo").forEach(preparar);
    document.querySelectorAll("[data-agregar-incentivo]").forEach(function (b) {
      b.addEventListener("click", function () {
        var run = b.dataset.agregarIncentivo;
        var html = plantilla.innerHTML.split("__RUN__").join(run);
        var lista = document.querySelector('[data-incentivos="' + run + '"]');
        lista.insertAdjacentHTML("beforeend", html);
        var fila = lista.lastElementChild;
        preparar(fila);
        iconos();
        fila.querySelector("[data-tipo-incentivo]").focus();
        b.closest("form").dispatchEvent(new Event("input", { bubbles: true }));
      });
    });
  }

  // Desplegables que en PC quedan siempre abiertos y en celular se abren al tocarlos
  function desplegablesMovil() {
    var pc = matchMedia("(min-width: 768px)");
    document.querySelectorAll("details.desplegable-movil").forEach(function (d) {
      function ajustar() { if (pc.matches) d.open = true; }
      d.querySelector("summary").addEventListener("click", function (e) { if (pc.matches) e.preventDefault(); });
      pc.addEventListener("change", ajustar);
      ajustar();
    });
  }

  // Encabezado fijo: agrega sombra solo cuando ya quedó pegado arriba al bajar
  function encabezadoFijo() {
    var e = document.querySelector(".encabezado-fijo");
    if (!e) return;
    function revisar() { e.classList.toggle("pegado", window.scrollY > 0 && e.getBoundingClientRect().top <= 0); }
    window.addEventListener("scroll", revisar, { passive: true });
    revisar();
  }

  // Los avisos (éxito o error) aparecen bajo el formulario que se envió, no arriba de la página.
  function avisosJuntoAlBoton() {
    var CLAVE = "vc-ultimo-formulario";
    document.addEventListener("submit", function (e) {
      var f = e.target;
      if (!(f instanceof HTMLFormElement) || (f.method || "").toLowerCase() !== "post") return;
      var dato = { ruta: location.pathname, id: f.id || "",
                   indice: Array.prototype.indexOf.call(document.querySelectorAll("form"), f) };
      try { sessionStorage.setItem(CLAVE, JSON.stringify(dato)); } catch (err) { /* sin almacenamiento */ }
    }, true);

    var guardado = null;
    try { guardado = JSON.parse(sessionStorage.getItem(CLAVE) || "null"); sessionStorage.removeItem(CLAVE); }
    catch (err) { guardado = null; }
    var avisos = document.querySelector("[data-avisos]");
    if (!avisos || !guardado || guardado.ruta !== location.pathname) return;
    var f = (guardado.id && document.getElementById(guardado.id)) || document.querySelectorAll("form")[guardado.indice];
    if (!f || f.contains(avisos)) return;
    var plegado = f.closest("details");
    if (plegado) plegado.open = true;
    if (!f.offsetParent) return;  // formulario oculto: el aviso se queda arriba
    avisos.classList.add("avisos-junto");
    f.insertAdjacentElement("afterend", avisos);
    avisos.scrollIntoView({ block: "center" });
  }

  document.addEventListener("DOMContentLoaded", function () {
    iconos(); tema(); guardables(); incentivos(); menu(); cronometros(); confirmaciones(); validarAntes(); unEnvio(); sugerencias(); encabezadoFijo(); desplegablesMovil(); avisosJuntoAlBoton();
  });
})();
