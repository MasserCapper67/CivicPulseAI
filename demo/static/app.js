"use strict";
// Todo texto que viene del servidor o de fuentes externas se pinta con textContent (nunca innerHTML).

const COLOR = { puede: "#2f9e44", solo_parking: "#e8590c", no_puede: "#e03131", sin_etiqueta: "#868e96" };
const VEREDICTO = {
  puede: "✔ Puedes entrar",
  solo_parking: "⚠ Solo puedes entrar para aparcar en un aparcamiento",
  no_puede: "✖ No puedes entrar",
};
const MENSAJE = {
  matricula_no_encontrada: "No encontramos esta matrícula en el registro de la DGT. Revísala o identifica tu coche «Por etiqueta».",
  moto: "Por ahora solo comprobamos coches.",
  direccion_no_encontrada: "No encontramos esa dirección. Revísala.",
  fuera_de_madrid: "Solo cubrimos el municipio de Madrid.",
  servicio_no_disponible: "El servicio de direcciones no responde. Inténtalo de nuevo en unos segundos.",
};
const NOMBRE_ETIQUETA = { CERO: "0 emisiones", ECO: "ECO", C: "C", B: "B", A: "sin etiqueta", H: "vehículo histórico" };
const ORIGEN = { dgt: " (según la DGT)", matricula_historica: " (por su matrícula H)", elegida: "" };

const formulario = document.getElementById("formulario");
const resultado = document.getElementById("resultado");
const botonesFiltro = document.querySelectorAll(".filtro button");

const mapa = L.map("mapa").setView([40.4168, -3.7038], 12);
L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: "© OpenStreetMap",
}).addTo(mapa);

let filtro = { etiqueta: null, padron: "fuera" };
let capaZonas = null;
let marcador = null;

function texto(etiqueta, contenido, clase) {
  const nodo = document.createElement(etiqueta);
  nodo.textContent = contenido;
  if (clase) nodo.className = clase;
  return nodo;
}

async function pintarZonas() {
  const params = new URLSearchParams({ padron: filtro.padron });
  if (filtro.etiqueta) params.set("etiqueta", filtro.etiqueta);
  const zonas = await (await fetch(`/api/zonas?${params}`)).json();
  if (capaZonas) capaZonas.remove();
  capaZonas = L.geoJSON(zonas, {
    style: (f) => ({ color: COLOR[f.properties.veredicto ?? "sin_etiqueta"], weight: 2, fillOpacity: 0.12 }),
    onEachFeature: (f, capa) => capa.bindTooltip(texto("span", f.properties.nombre)),
  }).addTo(mapa);
  capaZonas.bringToBack();
  botonesFiltro.forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.etiqueta === filtro.etiqueta)));
}

async function pintarCamaras() {
  const camaras = await (await fetch("geo/camaras.geojson")).json();
  L.geoJSON(camaras, {
    pointToLayer: (f, latlng) => L.circleMarker(latlng, { radius: 3, color: "#343a40", weight: 1, fillOpacity: 0.8 }),
    onEachFeature: (f, capa) => capa.bindTooltip(texto("span", `Cámara ${f.properties.zona}: ${f.properties.nombre}`)),
  }).addTo(mapa);
}

function mostrar(r, padron) {
  resultado.replaceChildren();
  resultado.className = "";
  if (r.estado !== "ok") {
    resultado.append(texto("p", r.motivo ?? MENSAJE[r.estado] ?? "Algo ha fallado. Inténtalo de nuevo.", "mensaje"));
    return;
  }
  resultado.className = r.veredicto;
  resultado.append(
    texto("p", VEREDICTO[r.veredicto], "veredicto"),
    texto("p", `Destino: ${r.destino.direccion}`, "destino"),  // la dirección entendida, bien visible
    texto("p", r.motivo),
    texto("p", `${r.zona.nombre} · tu coche: ${NOMBRE_ETIQUETA[r.etiqueta]}${ORIGEN[r.etiqueta_origen]}`, "detalle"),
  );
  if (r.nota) resultado.append(texto("p", r.nota, "nota"));
  resultado.append(texto("p", `${r.fuente.nombre} · ${r.fuente.articulo} · ${r.fuente.revisado}`, "fuente"));
  if (marcador) marcador.remove();
  marcador = L.marker([r.destino.lat, r.destino.lng]).addTo(mapa).bindTooltip(texto("span", r.destino.direccion));
  mapa.setView([r.destino.lat, r.destino.lng], 15);
  filtro = { etiqueta: r.etiqueta, padron };
  pintarZonas();
}

formulario.addEventListener("submit", async (e) => {
  e.preventDefault();
  const datos = Object.fromEntries(new FormData(formulario));  // solo trae el campo del modo activo
  delete datos.modo;
  resultado.className = "";
  resultado.replaceChildren(texto("p", "Comprobando…", "mensaje"));
  try {
    const respuesta = await fetch("/api/comprobar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(datos),
    });
    if (respuesta.status === 422) throw new Error("Revisa los datos del formulario.");
    if (!respuesta.ok) throw new Error("Algo ha fallado. Inténtalo de nuevo.");
    mostrar(await respuesta.json(), datos.padron);
  } catch (error) {
    resultado.replaceChildren(texto("p", error.message, "mensaje"));
  }
});

// Por etiqueta o por matrícula: se ve y se envía solo uno de los dos campos.
formulario.addEventListener("change", (e) => {
  if (e.target.name !== "modo") return;
  for (const modo of ["etiqueta", "matricula"]) {
    const activo = modo === e.target.value;
    document.getElementById(`por-${modo}`).hidden = !activo;
    document.getElementById(modo).disabled = !activo;
  }
});

botonesFiltro.forEach((b) => b.addEventListener("click", () => {
  filtro.etiqueta = b.dataset.etiqueta;
  pintarZonas();
}));

pintarZonas();
pintarCamaras();
