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
const EUROS = new Intl.NumberFormat("es-ES", { style: "currency", currency: "EUR" });
const HORAS = [1, 2, 3, 4, 6, 8, 12, 24];
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
let mapa = null, capaZonas = null, marcador = null;
const capasDePuntos = [];      // cámaras y parkings: sus iconos crecen con el zoom
let ultimaConsulta = null;     // para repetirla al cambiar la duración

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
    pintarParkings();
    mapa.on("zoomend", () => capasDePuntos.forEach(({ capa, clase }) => {
      const icono = iconoPorZoom(clase, mapa.getZoom());
      capa.eachLayer((m) => m.setIcon(icono));
    }));
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

// Cámaras y parkings crecen con el zoom: punto a escala de ciudad, icono al acercarse.
function iconoPorZoom(clase, zoom) {
  const tamano = zoom >= 16 ? 26 : zoom >= 14 ? 18 : 10;
  return L.divIcon({ className: tamano > 10 ? `${clase} con-icono tam-${tamano}` : clase, iconSize: [tamano, tamano] });
}

function capaDePuntos(geojson, clase, textoDe) {
  const capa = L.geoJSON(geojson, {
    // keyboard: false para no meter cientos de paradas en el recorrido del tabulador
    pointToLayer: (f, latlng) => L.marker(latlng, { icon: iconoPorZoom(clase, mapa.getZoom()), keyboard: false }),
    onEachFeature: (f, punto) => punto.bindTooltip(texto("span", textoDe(f.properties))),
  }).addTo(mapa);
  capasDePuntos.push({ capa, clase });
}

async function pintarCamaras() {
  const camaras = await (await fetch("geo/camaras.geojson")).json();
  capaDePuntos(camaras, "camara", (p) => `Cámara de ${p.zona}: ${p.nombre}`);
}

async function pintarParkings() {
  const parkings = await (await fetch("/api/parkings")).json();
  capaDePuntos(parkings, "parking", (p) => {
    const plazas = p.plazas_libres === null ? "sin datos de ocupación" : `${p.plazas_libres} plazas libres`;
    const precio = p.precio_hora === null ? "" : `. Primera hora: ${EUROS.format(p.precio_hora)}`;
    return `Aparcamiento ${p.nombre}: ${plazas}${precio}`;
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

// Los enlaces a Google Maps se abren aparte; su nombre accesible dice a dónde llevan.
function enlaceRuta(href, visible, accesible, clase) {
  const enlace = texto("a", visible, clase);
  enlace.href = href;
  enlace.target = "_blank";
  enlace.rel = "noopener noreferrer";
  enlace.setAttribute("aria-label", accesible);
  return enlace;
}

function textoCoste(a) {
  if (a.coste_eur === null) return "Precio no disponible";
  return `${a.coste_desde ? "desde " : ""}${EUROS.format(a.coste_eur)}`;
}

function seccionAlternativas(r) {
  const seccion = document.createElement("section");
  seccion.className = "alternativas";
  seccion.setAttribute("aria-labelledby", "titulo-alternativas");
  const titulo = texto("h2", "Alternativas");
  titulo.id = "titulo-alternativas";
  const horas = texto("label", "Costes calculados para ", "horas");
  const selector = document.createElement("select");
  selector.id = "horas";
  for (const h of HORAS) {
    const opcion = texto("option", `${h} h`);
    opcion.value = h;
    opcion.selected = h === r.horas;
    selector.append(opcion);
  }
  horas.append(selector);
  // Cambiar la duración repite la última consulta: cambian los costes, el formulario no se toca.
  selector.addEventListener("change", () => consultar({ ...ultimaConsulta, horas: Number(selector.value) }, true));
  seccion.append(titulo, horas);

  if (!r.alternativas.length) {
    seccion.append(texto("p", "No encontramos alternativas cerca de tu destino.", "mensaje"));
    return seccion;
  }
  const lista = document.createElement("ol");
  for (const a of r.alternativas) {  // ya vienen ordenadas por tiempo
    const info = document.createElement("div");
    const nombre = texto("p", a.nombre, "alt-nombre");
    if (a.mas_barata) nombre.append(" ", texto("span", "Más barata", "insignia"));
    info.append(nombre, texto("p", `${a.minutos} min ${a.como} desde que aparcas`, "alt-detalle"));
    if (a.plazas_libres !== null) info.append(texto("p", `${a.plazas_libres} plazas libres`, "alt-detalle"));
    if (a.coste_desde) info.append(texto("p", "Billete de ida y vuelta; aparcar en la calle no está incluido.", "alt-detalle"));
    const precio = document.createElement("div");
    precio.className = "alt-precio";
    precio.append(texto("p", textoCoste(a), "alt-coste"),
      enlaceRuta(a.como_llegar, "Cómo llegar", `Cómo llegar a ${a.nombre} (abre Google Maps)`, "alt-ruta"));
    const item = document.createElement("li");
    item.className = "alternativa";
    item.append(info, precio);
    lista.append(item);
  }
  seccion.append(lista);
  return seccion;
}

function textoParadas(paradas) {
  return `Cerca de tu destino: ${paradas.map((p) => `${p.modo} ${p.nombre} (${p.lineas.join(", ")}) a ${p.metros} m`).join("; ")}.`;
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

  const acciones = document.createElement("div");
  acciones.className = "acciones";
  if (r.como_llegar) acciones.append(enlaceRuta(r.como_llegar, "Cómo llegar", `Cómo llegar a ${r.destino.direccion} (abre Google Maps)`, "ver-ruta"));
  acciones.append(botonMapa);

  resultado.replaceChildren(veredicto, texto("p", r.motivo, "motivo"));
  if (r.nota) resultado.append(texto("p", r.nota, "nota"));
  resultado.append(acciones);
  if (r.veredicto !== "puede") resultado.append(seccionAlternativas(r));
  if (r.paradas_cercanas.length) resultado.append(texto("p", textoParadas(r.paradas_cercanas), "paradas"));
  resultado.append(listaDatos([
    ["Zona", r.zona.nombre],
    ["Tu coche", `${NOMBRE_ETIQUETA[r.etiqueta]}${ORIGEN[r.etiqueta_origen]}`],
    ["Norma", `${r.fuente.nombre.split(",")[0]}, ${r.fuente.articulo}`],
  ]));
  verResultado();

  // El mapa no se abre solo: queda preparado para cuando se pulse «Ver en el mapa».
  destino = r.destino;
  centrarEnDestino = true;
  filtro = { etiqueta: r.etiqueta, padron };
  actualizarMapa();
}

async function consultar(datos, cambioDeHoras = false) {
  ultimaConsulta = datos;
  if (!cambioDeHoras) resultado.replaceChildren(texto("p", "Comprobando…", "mensaje espera"));
  try {
    const respuesta = await fetch("/api/comprobar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(datos),
    });
    if (respuesta.status === 422) throw new Error("Revisa los datos del formulario.");
    if (!respuesta.ok) throw new Error(FALLO);
    mostrar(await respuesta.json(), datos.padron);
    if (cambioDeHoras) document.getElementById("horas")?.focus();  // el selector se ha vuelto a pintar
  } catch (error) {
    mostrarError(error.message);
  }
}

formulario.addEventListener("submit", (e) => {
  e.preventDefault();
  const datos = Object.fromEntries(new FormData(formulario));  // solo trae el campo del modo activo
  delete datos.modo;
  consultar(datos);
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
