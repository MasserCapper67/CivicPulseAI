"use strict";
// Todo texto que viene del servidor o de fuentes externas se pinta con textContent (nunca innerHTML).

// Mismos colores que las señales: azul permitido, amarillo condicional, rojo prohibido.
const ESTILO_ZONA = {
  puede: { color: "#0b4ea2", fillOpacity: 0.14 },
  solo_parking: { color: "#c99400", fillOpacity: 0.16, dashArray: "8 6" },
  no_puede: { color: "#c8102e", fillOpacity: 0.14 },
  sin_etiqueta: { color: "#7a8087", fillOpacity: 0.05 },
};
const TITULAR = {
  puede: "Puedes entrar",
  solo_parking: "Puedes entrar solo para aparcar",
  no_puede: "No puedes entrar",
};
const MENSAJE = {
  matricula_no_encontrada: "No encontramos esta matrícula en el registro de la DGT. Revísala o identifica tu coche «Por etiqueta».",
  moto: "Por ahora solo comprobamos coches.",
  direccion_no_encontrada: "No encontramos esa dirección. Prueba con la calle y el número.",
  servicio_no_disponible: "El servicio de direcciones no responde. Inténtalo de nuevo en unos segundos.",
};
const FALLO = "No se ha podido completar la comprobación. Inténtalo de nuevo.";
const NOMBRE_ETIQUETA = { CERO: "0 emisiones", ECO: "ECO", C: "C", B: "B", A: "sin etiqueta", H: "vehículo histórico" };
const ORIGEN = { dgt: ", según la DGT", matricula_historica: ", por su matrícula H", elegida: "" };
const COCHE = { CERO: "un coche 0 emisiones", ECO: "un coche ECO", C: "un coche con etiqueta C", B: "un coche con etiqueta B", A: "un coche sin etiqueta", H: "un coche histórico" };
const PADRON = { fuera: "de fuera de Madrid", madrid: "empadronado en Madrid", centro: "de un vecino de Distrito Centro" };

const formulario = document.getElementById("formulario");
const resultado = document.getElementById("resultado");
const pistaMapa = document.getElementById("pista-mapa");
const plantillaSenal = document.getElementById("plantilla-senal");
const botonesFiltro = document.querySelectorAll(".filtro-mapa button");
const pestanas = { datos: document.getElementById("pestana-datos"), mapa: document.getElementById("pestana-mapa") };
const secciones = { datos: document.getElementById("seccion-datos"), mapa: document.getElementById("seccion-mapa") };

// Un solo estado para formulario, resultado y mapa: los tres dicen siempre lo mismo.
let filtro = { etiqueta: null, padron: "fuera" };
let destino = null;            // último destino comprobado (marcador del mapa)
let centrarEnDestino = false;  // al abrir el mapa desde «Ver en el mapa»
let mapa = null, capaZonas = null, capaCamaras = null, marcador = null;

function texto(etiqueta, contenido, clase) {
  const nodo = document.createElement(etiqueta);
  nodo.textContent = contenido;
  if (clase) nodo.className = clase;
  return nodo;
}

function listaDatos(pares) {
  const lista = document.createElement("dl");
  lista.className = "datos";
  for (const [nombre, valor] of pares) lista.append(texto("dt", nombre), texto("dd", valor));
  return lista;
}

// ---------- Secciones: 1 Incluir datos / 2 Ver mapa ----------

function mostrarSeccion(nombre) {
  for (const [clave, pestana] of Object.entries(pestanas)) {
    const activa = clave === nombre;
    pestana.setAttribute("aria-selected", String(activa));
    pestana.tabIndex = activa ? 0 : -1;
    secciones[clave].hidden = !activa;
  }
  if (nombre === "mapa") abrirMapa();
}

for (const [clave, pestana] of Object.entries(pestanas)) {
  pestana.addEventListener("click", () => mostrarSeccion(clave));
  pestana.addEventListener("keydown", (e) => {
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
    const otra = clave === "datos" ? "mapa" : "datos";
    mostrarSeccion(otra);
    pestanas[otra].focus();
  });
}

// ---------- Mapa (se crea la primera vez que se abre: en móvil no descarga teselas que no se miran) ----------

function abrirMapa() {
  if (!mapa) {
    mapa = L.map("mapa").setView([40.4168, -3.7038], 12);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19, attribution: "© OpenStreetMap" }).addTo(mapa);
    pintarCamaras();
  }
  mapa.invalidateSize();  // el contenedor estaba oculto: Leaflet necesita recalcular su tamaño
  if (centrarEnDestino && destino) {
    mapa.setView([destino.lat, destino.lng], 15);
    centrarEnDestino = false;
  }
  actualizarMapa();
}

async function actualizarMapa() {
  pistaMapa.textContent = filtro.etiqueta
    ? `Zonas para ${COCHE[filtro.etiqueta]} ${PADRON[filtro.padron]}.`
    : "Elige la etiqueta de tu coche para ver por dónde puedes circular.";
  botonesFiltro.forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.etiqueta === filtro.etiqueta)));
  if (!mapa) return;

  if (marcador) marcador.remove();
  marcador = destino ? L.marker([destino.lat, destino.lng]).addTo(mapa).bindTooltip(texto("span", destino.direccion)) : null;

  const params = new URLSearchParams({ padron: filtro.padron });
  if (filtro.etiqueta) params.set("etiqueta", filtro.etiqueta);
  const zonas = await (await fetch(`/api/zonas?${params}`)).json();
  if (capaZonas) capaZonas.remove();
  capaZonas = L.geoJSON(zonas, {
    // La ZBE general es todo el municipio (con huecos en las autovías): trazo fino para que no tape las ZBEDEP.
    style: (f) => ({ weight: f.properties.id === "zbe_madrid" ? 1.25 : 3, ...ESTILO_ZONA[f.properties.veredicto ?? "sin_etiqueta"] }),
    onEachFeature: (f, capa) => capa.bindTooltip(texto("span", f.properties.nombre)),
  }).addTo(mapa);
  capaZonas.bringToBack();
}

// Las cámaras crecen con el zoom: punto a escala de ciudad, icono de cámara al acercarse.
function iconoCamara(zoom) {
  const tamano = zoom >= 16 ? 26 : zoom >= 14 ? 18 : 10;
  return L.divIcon({ className: tamano > 10 ? "camara con-icono" : "camara", iconSize: [tamano, tamano] });
}

async function pintarCamaras() {
  const camaras = await (await fetch("geo/camaras.geojson")).json();
  let icono = iconoCamara(mapa.getZoom());
  capaCamaras = L.geoJSON(camaras, {
    // keyboard: false para no meter 603 paradas en el recorrido del tabulador
    pointToLayer: (f, latlng) => L.marker(latlng, { icon: icono, keyboard: false }),
    onEachFeature: (f, capa) => capa.bindTooltip(texto("span", `Cámara de ${f.properties.zona}: ${f.properties.nombre}`)),
  }).addTo(mapa);
  mapa.on("zoomend", () => {
    const nuevo = iconoCamara(mapa.getZoom());
    if (nuevo.options.iconSize[0] === icono.options.iconSize[0]) return;
    icono = nuevo;
    capaCamaras.eachLayer((m) => m.setIcon(icono));
  });
}

// ---------- Formulario y resultado ----------

function aplicarModo(modo) {
  // Por etiqueta o por matrícula: se ve y se envía solo uno de los dos campos.
  for (const m of ["etiqueta", "matricula"]) {
    document.getElementById(`por-${m}`).hidden = m !== modo;
    document.getElementById(m).disabled = m !== modo;
  }
}

function leerFormulario() {
  const modo = formulario.querySelector('input[name="modo"]:checked').value;
  filtro.etiqueta = modo === "etiqueta" ? formulario.querySelector('input[name="etiqueta"]:checked')?.value ?? null : null;
  filtro.padron = formulario.querySelector('input[name="padron"]:checked')?.value ?? "fuera";
}

// El resultado es lo importante: se lleva a la vista (sin animación si el usuario la ha reducido).
function verResultado() {
  const suave = !matchMedia("(prefers-reduced-motion: reduce)").matches;
  resultado.scrollIntoView({ behavior: suave ? "smooth" : "auto", block: "nearest" });
}

function mostrarError(mensaje) {
  resultado.replaceChildren(texto("p", mensaje, "mensaje error"));
  verResultado();
}

function mostrar(r, padron) {
  if (r.estado === "fuera_de_madrid") {
    mostrarError(`${r.destino.direccion} está fuera del municipio de Madrid, y por ahora solo cubrimos Madrid.`);
    return;
  }
  if (r.estado !== "ok") {
    mostrarError(r.motivo ?? MENSAJE[r.estado] ?? FALLO);
    return;
  }

  // La señal de tráfico: disco azul (puedes) o aro rojo (no puedes), con placa «Excepto…» si es solo para aparcar.
  const veredicto = document.createElement("div");
  veredicto.className = `veredicto ${r.veredicto}`;
  const cabecera = document.createElement("div");
  cabecera.append(texto("p", TITULAR[r.veredicto], "titular"), texto("p", r.destino.direccion, "destino"));
  veredicto.append(plantillaSenal.content.cloneNode(true), cabecera);
  if (r.veredicto === "solo_parking") veredicto.append(texto("p", "Excepto para aparcar en un aparcamiento", "placa"));

  const botonMapa = texto("button", "Ver en el mapa", "ver-mapa");
  botonMapa.type = "button";
  botonMapa.addEventListener("click", () => {
    mostrarSeccion("mapa");
    pestanas.mapa.focus();
  });

  resultado.replaceChildren(
    veredicto,
    texto("p", r.motivo, "motivo"),
    listaDatos([
      ["Zona", r.zona.nombre],
      ["Tu coche", `${NOMBRE_ETIQUETA[r.etiqueta]}${ORIGEN[r.etiqueta_origen]}`],
      ["Norma", `${r.fuente.nombre.split(",")[0]}, ${r.fuente.articulo}`],
    ]),
  );
  if (r.nota) resultado.append(texto("p", r.nota, "nota"));
  resultado.append(botonMapa);
  verResultado();

  // El mapa no se abre solo: queda preparado para cuando se pulse «Ver en el mapa».
  destino = r.destino;
  centrarEnDestino = true;
  filtro = { etiqueta: r.etiqueta, padron };
  actualizarMapa();
}

formulario.addEventListener("submit", async (e) => {
  e.preventDefault();
  const datos = Object.fromEntries(new FormData(formulario));  // solo trae el campo del modo activo
  delete datos.modo;
  resultado.replaceChildren(texto("p", "Comprobando…", "mensaje espera"));
  try {
    const respuesta = await fetch("/api/comprobar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(datos),
    });
    if (respuesta.status === 422) throw new Error("Revisa los datos del formulario.");
    if (!respuesta.ok) throw new Error(FALLO);
    mostrar(await respuesta.json(), datos.padron);
  } catch (error) {
    mostrarError(error.message);
  }
});

// Si cambia cualquier dato, el resultado anterior ya no corresponde: se borra.
// «input» y no «change»: change salta al perder el foco y borraría el resultado recién mostrado.
formulario.addEventListener("input", (e) => {
  resultado.replaceChildren();
  if (e.target.name === "modo") aplicarModo(e.target.value);
  const antes = JSON.stringify(filtro);
  leerFormulario();
  if (JSON.stringify(filtro) !== antes) actualizarMapa();  // escribir la dirección no cambia el mapa
});

// ---------- Autocompletar la dirección (patrón ARIA combobox) ----------

const campoDireccion = document.getElementById("direccion");
const listaSugerencias = document.getElementById("sugerencias");
let sugerencias = [];
let activa = -1;              // sugerencia resaltada con las flechas
let temporizador = null;
let ultimaPeticion = 0;       // para descartar respuestas que llegan tarde

function pintarSugerencias() {
  listaSugerencias.replaceChildren(...sugerencias.map((s, i) => {
    const opcion = texto("li", s);
    opcion.id = `sugerencia-${i}`;
    opcion.setAttribute("role", "option");
    opcion.setAttribute("aria-selected", String(i === activa));
    return opcion;
  }));
  const abierta = sugerencias.length > 0;
  listaSugerencias.hidden = !abierta;
  campoDireccion.setAttribute("aria-expanded", String(abierta));
  if (activa >= 0) campoDireccion.setAttribute("aria-activedescendant", `sugerencia-${activa}`);
  else campoDireccion.removeAttribute("aria-activedescendant");
}

function cerrarSugerencias() {
  sugerencias = [];
  activa = -1;
  pintarSugerencias();
}

function elegirSugerencia(i) {
  campoDireccion.value = sugerencias[i];
  cerrarSugerencias();
  resultado.replaceChildren();  // la dirección ha cambiado
}

campoDireccion.addEventListener("input", () => {
  clearTimeout(temporizador);
  const escrito = campoDireccion.value.trim();
  if (escrito.length < 3) return cerrarSugerencias();
  temporizador = setTimeout(async () => {  // espera a que se deje de teclear
    const peticion = ++ultimaPeticion;
    try {
      const respuesta = await fetch("/api/direcciones", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ texto: escrito }),
      });
      const datos = respuesta.ok ? await respuesta.json() : { sugerencias: [] };
      if (peticion !== ultimaPeticion || document.activeElement !== campoDireccion) return;
      sugerencias = datos.sugerencias;
      activa = -1;
      pintarSugerencias();
    } catch {
      // sin sugerencias se puede seguir escribiendo la dirección a mano
    }
  }, 250);
});

campoDireccion.addEventListener("keydown", (e) => {
  if (listaSugerencias.hidden) return;
  if (e.key === "ArrowDown" || e.key === "ArrowUp") {
    e.preventDefault();
    const paso = e.key === "ArrowDown" ? 1 : -1;
    activa = (activa + paso + sugerencias.length) % sugerencias.length;
    pintarSugerencias();
  } else if (e.key === "Enter" && activa >= 0) {
    e.preventDefault();  // elige la sugerencia en vez de enviar el formulario
    elegirSugerencia(activa);
  } else if (e.key === "Escape") {
    e.preventDefault();
    cerrarSugerencias();
  }
});

// mousedown (y no click) para elegir antes de que el campo pierda el foco
listaSugerencias.addEventListener("mousedown", (e) => {
  const opcion = e.target.closest("li");
  if (!opcion) return;
  e.preventDefault();
  elegirSugerencia([...listaSugerencias.children].indexOf(opcion));
});
campoDireccion.addEventListener("blur", cerrarSugerencias);

// Elegir una pegatina en el mapa es elegirla en el formulario.
botonesFiltro.forEach((b) => b.addEventListener("click", () => {
  formulario.querySelector('input[name="modo"][value="etiqueta"]').checked = true;
  aplicarModo("etiqueta");
  formulario.querySelector(`input[name="etiqueta"][value="${b.dataset.etiqueta}"]`).checked = true;
  resultado.replaceChildren();
  leerFormulario();
  actualizarMapa();
}));

actualizarMapa();
