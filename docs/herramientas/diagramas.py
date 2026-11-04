"""Genera los diagramas del proyecto en tres formatos a partir de una misma especificacion:
  - .drawio : editable en draw.io / VS Code (extension hediet.vscode-drawio)
  - .svg    : para el Markdown y el PDF de repaso
  - .png    : para el informe Word (captura con Chrome sin ventana)

Uso: python docs/herramientas/diagramas.py            -> escribe docs/diagramas/*.drawio|svg|png
"""
import html
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent.parent
SALIDA = RAIZ / "docs" / "diagramas"
CHROME = [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
          r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"]

# Paleta (fondo, borde)
AZUL = ("#dae8fc", "#6c8ebf")
VERDE = ("#d5e8d4", "#82b366")
NARANJA = ("#ffe6cc", "#d79b00")
GRIS = ("#f5f5f5", "#666666")
ROJO = ("#f8cecc", "#b85450")
AMARILLO = ("#fff2cc", "#d6b656")
VIOLETA = ("#e1d5e7", "#9673a6")


def nodo(id_, texto, x, y, w, h, color=AZUL, forma="rect", negrita_primera=True):
    return {"id": id_, "texto": texto, "x": x, "y": y, "w": w, "h": h, "color": color, "forma": forma,
            "negrita": negrita_primera}


def caja(id_, titulo, x, y, w, h, color=GRIS):
    return {"id": id_, "titulo": titulo, "x": x, "y": y, "w": w, "h": h, "color": color}


def arco(origen, destino, etiqueta="", punteado=False):
    return {"de": origen, "a": destino, "etiqueta": etiqueta, "punteado": punteado}


# ----------------------------------------------------------------------------- especificaciones
D1 = {
    "nombre": "01-arquitectura",
    "titulo": "Arquitectura general: del entrenamiento al servicio desplegado",
    "ancho": 1180, "alto": 640,
    "cajas": [
        caja("c_host", "Maquina anfitriona (Windows): entorno virtual Python", 20, 20, 1140, 230),
        caja("c_k8s", "Kubernetes de Docker Desktop · namespace riesgo-credito", 20, 300, 760, 320, AZUL),
    ],
    "nodos": [
        nodo("datos", "datos/credito.csv\nUCI, 30.000 x 23 variables\nMD5 como tag del run", 40, 70, 200, 70, VERDE),
        nodo("entrenar", "entrenamiento/entrenar.py\n8 runs (logreg, RF, HGB)\nparams, metricas, modelo", 290, 70, 220, 70, AZUL),
        nodo("mlflow", "MLflow server :5050\ntracking + Model Registry + UI\nSQLite + artefactos", 580, 60, 240, 90, VIOLETA),
        nodo("registrar", "entrenamiento/registrar.py\ncompuerta de calidad\nv1 baseline · v2 champion", 870, 70, 250, 70, NARANJA),
        nodo("monitoreo", "monitoreo/\nvalidar_datos · data_drift · concept_drift\nlotes nuevos vs baseline", 290, 160, 290, 70, AMARILLO),
        nodo("imagen", "Imagen Docker\nriesgo-credito-api:1.0\n(codigo + dependencias, sin modelo)", 40, 340, 220, 70, GRIS),
        nodo("deploy", "Deployment riesgo-credito-api\n3 pods FastAPI\nreadiness /health · liveness /vivo", 300, 340, 250, 80, AZUL),
        nodo("svc_api", "Service riesgo-credito-api\nNodePort 30080", 300, 470, 250, 60, VERDE),
        nodo("ui", "Deployment riesgo-credito-ui\nnginx + index.html\nproxy /api/ -> Service por DNS", 580, 340, 180, 80, AZUL),
        nodo("svc_ui", "Service riesgo-credito-ui\nNodePort 30081", 580, 470, 180, 60, VERDE),
        nodo("cliente", "Navegador / curl / Swagger\nlocalhost:30080 (API)\nlocalhost:30081 (UI)", 850, 440, 270, 80, GRIS),
        nodo("resp", "Cada respuesta:\nmora, probabilidad, pod,\nversion y run_id del modelo", 850, 560, 270, 60, AMARILLO),
    ],
    "arcos": [
        arco("datos", "entrenar"), arco("entrenar", "mlflow", "log_*"),
        arco("mlflow", "registrar", "mejor run"), arco("registrar", "mlflow", "alias", True),
        arco("monitoreo", "mlflow", "carga el champion", True),
        arco("imagen", "deploy", "apply"),
        arco("deploy", "mlflow", "models:/riesgo-credito@champion\nvia host.docker.internal:5050", True),
        arco("svc_api", "deploy", "balancea"),
        arco("ui", "svc_api", "DNS del Service"),
        arco("svc_ui", "ui"), arco("cliente", "svc_api"), arco("cliente", "svc_ui"), arco("svc_api", "resp", "", True),
    ],
}

D2 = {
    "nombre": "02-ciclo-de-vida-modelo",
    "titulo": "Ciclo de vida de una version del modelo: champion, challenger, compuerta y rollback",
    "ancho": 1180, "alto": 520,
    "cajas": [],
    "nodos": [
        nodo("exp", "Experimento riesgo-credito\n8 runs comparables\n(misma particion, semilla 42)", 30, 40, 230, 70, AZUL),
        nodo("gate", "Compuerta de calidad\nroc_auc >= 0.75\ny > champion actual", 320, 40, 200, 70, NARANJA, "rombo"),
        nodo("reg", "Model Registry riesgo-credito\nv1 = logreg_C1 (0.710) alias baseline\nv2 = hgb (0.780) alias champion", 580, 30, 300, 90, VIOLETA),
        nodo("pods", "Pods en Kubernetes\ncargan models:/riesgo-credito@champion\nal arrancar (readiness)", 940, 40, 220, 80, AZUL),
        nodo("mon", "Monitoreo mensual\nvalidar_datos -> data drift ->\nconcept drift cuando llegan etiquetas", 940, 200, 220, 80, AMARILLO),
        nodo("alarma", "Alarma\nroc_auc cae > 0.05 por 3 lotes\n(o > 0.12 en uno)", 940, 340, 220, 70, ROJO),
        nodo("challenger", "Reentrenar challenger\ncon lotes recientes etiquetados\n-> version 3 en el registry", 580, 340, 300, 70, VERDE),
        nodo("promo", "Mover alias champion -> v3\nkubectl rollout restart\n(maxSurge 1 / maxUnavailable 0)", 320, 340, 200, 80, AZUL),
        nodo("rollback", "Rollback: alias -> version anterior\n+ rollout restart\n(sin reconstruir la imagen)", 30, 340, 230, 80, GRIS),
        nodo("rechazo", "RECHAZADO:\nel alias no se mueve", 320, 180, 200, 60, ROJO),
    ],
    "arcos": [
        arco("exp", "gate", "candidato"), arco("gate", "reg", "APROBADO"), arco("gate", "rechazo", "no pasa", True),
        arco("reg", "pods", "por alias"), arco("pods", "mon", "predicciones"), arco("mon", "alarma", "degradacion sostenida"),
        arco("alarma", "challenger", "CT"), arco("challenger", "gate", "pasa por la misma compuerta", True),
        arco("gate", "promo", "si gana"), arco("promo", "rollback", "si sale mal", True), arco("rollback", "reg", "", True),
    ],
}

D3 = {
    "nombre": "03-pipeline-monitoreo",
    "titulo": "Que le pasa a un lote nuevo: validacion de datos, data drift y concept drift",
    "ancho": 1180, "alto": 560,
    "cajas": [
        caja("c_sin", "Sin etiqueta: se calcula el mismo dia", 20, 20, 1140, 250, VERDE),
        caja("c_con", "Con etiqueta: llega 30-90 dias despues (ground truth delay)", 20, 300, 1140, 240, AMARILLO),
    ],
    "nodos": [
        nodo("lote", "Lote mensual\n(500-1.500 clientes)", 40, 80, 180, 60, GRIS),
        nodo("val", "validar_datos.py\nesquema, nulos, rangos,\nminimo de filas", 270, 70, 200, 80, AZUL),
        nodo("rechazo", "RECHAZADO (codigo 1)\nse detiene el flujo", 270, 180, 200, 60, ROJO),
        nodo("dd", "data_drift.py\nnumericas: KS + PSI\ncategoricas/ordinales: chi2 + PSI", 520, 70, 250, 80, AZUL),
        nodo("sem", "VERDE / AMARILLO / ROJO\nPSI 0.10 / 0.25 · alfa 0.01\nefecto minimo 0.10", 820, 70, 230, 80, NARANJA),
        nodo("psi", "Senales sin etiqueta:\nPSI del score, tasa de positivos", 520, 180, 250, 60, AMARILLO),
        nodo("rojo", "ROJO: investigar y vigilar\n(no reentrena solo)", 820, 180, 230, 60, ROJO),
        nodo("etiq", "Etiquetas reales\n(mora del mes siguiente)", 40, 360, 180, 60, GRIS),
        nodo("cd", "concept_drift.py\nroc_auc por lote vs referencia 0.780\numbral 0.730", 270, 350, 250, 80, AZUL),
        nodo("crit", "Criterio: caida > 0.05\ndurante 3 lotes seguidos\no > 0.12 en un lote", 570, 350, 230, 80, NARANJA, "rombo"),
        nodo("alarma", "ALARMA (lote 9 en la simulacion)\n-> reentrenar challenger\n-> compuerta -> alias", 850, 350, 280, 80, ROJO),
        nodo("ok", "Sin alarma: el modelo sigue sirviendo", 570, 460, 230, 50, VERDE),
    ],
    "arcos": [
        arco("lote", "val"), arco("val", "rechazo", "problemas", True), arco("val", "dd", "OK"), arco("dd", "sem"),
        arco("dd", "psi", "", True), arco("sem", "rojo", "", True),
        arco("etiq", "cd"), arco("lote", "etiq", "mismo lote, meses despues", True), arco("cd", "crit"),
        arco("crit", "alarma", "si"), arco("crit", "ok", "no"),
    ],
}

D4 = {
    "nombre": "04-kubernetes-peticion",
    "titulo": "Dentro de Kubernetes: como llega una peticion y como se mantiene el servicio",
    "ancho": 1180, "alto": 470,
    "cajas": [caja("c_ns", "namespace riesgo-credito", 240, 20, 920, 430, AZUL)],
    "nodos": [
        nodo("cli", "curl / navegador\nlocalhost:30080/predecir", 30, 190, 180, 60, GRIS),
        nodo("svc", "Service (NodePort 30080)\nIP virtual + DNS\nkube-proxy reparte cada conexion", 280, 180, 230, 80, VERDE),
        nodo("eps", "EndpointSlice\nIPs de los pods Ready\n(entran y salen solos)", 280, 320, 230, 70, AMARILLO),
        nodo("p1", "pod api-1\nmodelo v2 en memoria\nREADY", 580, 60, 170, 70, AZUL),
        nodo("p2", "pod api-2\nmodelo v2 en memoria\nREADY", 580, 180, 170, 70, AZUL),
        nodo("p3", "pod api-3\n(nuevo, cargando modelo)\nNO READY: sin trafico", 580, 300, 170, 70, NARANJA),
        nodo("rs", "ReplicaSet / Deployment\nestado deseado: 3 pods\nsi uno muere, crea otro", 800, 60, 220, 80, VIOLETA),
        nodo("probes", "readiness /health: Ready solo con\nel modelo cargado\nliveness /vivo: reinicia si no responde", 800, 190, 330, 80, GRIS),
        nodo("res", "requests 250m / 512Mi\nlimits 1 CPU / 1Gi\nrolling update maxSurge 1 / maxUnavailable 0", 800, 320, 330, 80, GRIS),
    ],
    "arcos": [
        arco("cli", "svc"), arco("svc", "p1"), arco("svc", "p2"), arco("svc", "p3", "no (no Ready)", True),
        arco("eps", "svc", "", True), arco("rs", "p1", "", True), arco("rs", "p2", "", True), arco("rs", "p3", "crea", True),
    ],
}

DIAGRAMAS = [D1, D2, D3, D4]


# ----------------------------------------------------------------------------- SVG
def _anclaje(a, b):
    """Punto del borde de la caja a en direccion al centro de b."""
    ax, ay = a["x"] + a["w"] / 2, a["y"] + a["h"] / 2
    bx, by = b["x"] + b["w"] / 2, b["y"] + b["h"] / 2
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return ax, ay
    sx = (a["w"] / 2) / abs(dx) if dx else float("inf")
    sy = (a["h"] / 2) / abs(dy) if dy else float("inf")
    s = min(sx, sy)
    return ax + dx * s, ay + dy * s


def svg(d):
    por_id = {n["id"]: n for n in d["nodos"]}
    partes = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{d["ancho"]}" height="{d["alto"] + 40}" viewBox="0 0 {d["ancho"]} {d["alto"] + 40}" font-family="Segoe UI, Calibri, Arial, sans-serif">',
              '<defs><marker id="flecha" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto"><polygon points="0 0, 10 3.5, 0 7" fill="#444"/></marker></defs>',
              f'<rect width="100%" height="100%" fill="#ffffff"/>',
              f'<text x="{d["ancho"] / 2}" y="24" text-anchor="middle" font-size="16" font-weight="bold" fill="#1f4e79">{html.escape(d["titulo"])}</text>',
              f'<g transform="translate(0,34)">']
    for c in d["cajas"]:
        partes.append(f'<rect x="{c["x"]}" y="{c["y"]}" width="{c["w"]}" height="{c["h"]}" rx="8" fill="{c["color"][0]}" fill-opacity="0.35" stroke="{c["color"][1]}" stroke-dasharray="6 4"/>')
        partes.append(f'<text x="{c["x"] + 10}" y="{c["y"] + 18}" font-size="12" font-weight="bold" fill="{c["color"][1]}">{html.escape(c["titulo"])}</text>')
    etiquetas = []
    for e in d["arcos"]:
        a, b = por_id[e["de"]], por_id[e["a"]]
        x1, y1 = _anclaje(a, b); x2, y2 = _anclaje(b, a)
        dash = ' stroke-dasharray="6 4"' if e["punteado"] else ""
        partes.append(f'<line x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}" stroke="#444" stroke-width="1.6"{dash} marker-end="url(#flecha)"/>')
        if e["etiqueta"]:
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            lineas = e["etiqueta"].split("\n")
            w = max(len(l) for l in lineas) * 6.2 + 10
            etiquetas.append(f'<rect x="{mx - w / 2:.0f}" y="{my - 8 * len(lineas) - 2:.0f}" width="{w:.0f}" height="{16 * len(lineas) + 2}" rx="3" fill="#ffffff" stroke="#bbbbbb" stroke-width="0.6"/>')
            for k, l in enumerate(lineas):
                etiquetas.append(f'<text x="{mx:.0f}" y="{my - 8 * len(lineas) + 12 + 16 * k:.0f}" text-anchor="middle" font-size="10.5" fill="#333">{html.escape(l)}</text>')
    for n in d["nodos"]:
        fill, stroke = n["color"]
        if n["forma"] == "rombo":
            cx, cy = n["x"] + n["w"] / 2, n["y"] + n["h"] / 2
            partes.append(f'<polygon points="{cx},{n["y"] - 14} {n["x"] + n["w"] + 24},{cy} {cx},{n["y"] + n["h"] + 14} {n["x"] - 24},{cy}" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')
        else:
            partes.append(f'<rect x="{n["x"]}" y="{n["y"]}" width="{n["w"]}" height="{n["h"]}" rx="7" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')
        lineas = n["texto"].split("\n")
        y0 = n["y"] + n["h"] / 2 - (len(lineas) - 1) * 8
        for k, l in enumerate(lineas):
            peso = ' font-weight="bold"' if (k == 0 and n["negrita"]) else ""
            partes.append(f'<text x="{n["x"] + n["w"] / 2}" y="{y0 + 16 * k + 4:.0f}" text-anchor="middle" font-size="11.5"{peso} fill="#1b1b1b">{html.escape(l)}</text>')
    partes += etiquetas          # las etiquetas de los arcos van encima de todo
    partes.append("</g></svg>")
    return "\n".join(partes)


# ----------------------------------------------------------------------------- draw.io
def drawio(d):
    celdas = ['<mxGraphModel adaptiveColors="auto"><root><mxCell id="0"/><mxCell id="1" parent="0"/>']
    celdas.append(f'<mxCell id="titulo" value="{html.escape(d["titulo"])}" style="text;html=1;align=center;fontSize=16;fontStyle=1;fontColor=#1f4e79;" vertex="1" parent="1"><mxGeometry x="0" y="0" width="{d["ancho"]}" height="30" as="geometry"/></mxCell>')
    for c in d["cajas"]:
        celdas.append(f'<mxCell id="{c["id"]}" value="{html.escape(c["titulo"])}" style="rounded=1;whiteSpace=wrap;html=1;dashed=1;fillColor={c["color"][0]};strokeColor={c["color"][1]};opacity=45;verticalAlign=top;align=left;spacingLeft=8;fontStyle=1;" vertex="1" parent="1"><mxGeometry x="{c["x"]}" y="{c["y"] + 40}" width="{c["w"]}" height="{c["h"]}" as="geometry"/></mxCell>')
    for n in d["nodos"]:
        texto = html.escape(n["texto"]).replace("\n", "&lt;br&gt;")
        if n["negrita"]:
            primera, _, resto = texto.partition("&lt;br&gt;")
            texto = f"&lt;b&gt;{primera}&lt;/b&gt;" + ("&lt;br&gt;" + resto if resto else "")
        forma = "rhombus;" if n["forma"] == "rombo" else "rounded=1;"
        celdas.append(f'<mxCell id="{n["id"]}" value="{texto}" style="{forma}whiteSpace=wrap;html=1;fillColor={n["color"][0]};strokeColor={n["color"][1]};fontSize=11;" vertex="1" parent="1"><mxGeometry x="{n["x"]}" y="{n["y"] + 40}" width="{n["w"]}" height="{n["h"]}" as="geometry"/></mxCell>')
    for k, e in enumerate(d["arcos"]):
        etiqueta = html.escape(e["etiqueta"]).replace("\n", "&lt;br&gt;")
        dash = "dashed=1;" if e["punteado"] else ""
        celdas.append(f'<mxCell id="e{k}" value="{etiqueta}" style="edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;{dash}fontSize=10;" edge="1" source="{e["de"]}" target="{e["a"]}" parent="1"><mxGeometry relative="1" as="geometry"/></mxCell>')
    celdas.append("</root></mxGraphModel>")
    modelo = "".join(celdas)
    return f'<mxfile host="riesgo-credito-mlops"><diagram id="{d["nombre"]}" name="{d["nombre"]}">{modelo}</diagram></mxfile>'


def png(svg_path: Path, ancho: int, alto: int) -> Path | None:
    chrome = next((c for c in CHROME if Path(c).exists()), None)
    if not chrome:
        return None
    html_path = svg_path.with_suffix(".html")
    html_path.write_text(f'<!doctype html><html><body style="margin:0;background:#fff">{svg_path.read_text(encoding="utf-8")}</body></html>', encoding="utf-8")
    destino = svg_path.with_suffix(".png")
    subprocess.run([chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--window-size={ancho},{alto + 40}",
                    "--force-device-scale-factor=2", f"--screenshot={destino.resolve()}", html_path.resolve().as_uri()],
                   check=True, capture_output=True, timeout=120)
    html_path.unlink(missing_ok=True)
    return destino


def main() -> int:
    SALIDA.mkdir(parents=True, exist_ok=True)
    for d in DIAGRAMAS:
        base = SALIDA / d["nombre"]
        base.with_suffix(".drawio").write_text(drawio(d), encoding="utf-8")
        base.with_suffix(".svg").write_text(svg(d), encoding="utf-8")
        p = png(base.with_suffix(".svg"), d["ancho"], d["alto"])
        print(f"ok: {d['nombre']} (.drawio, .svg{', .png' if p else ''})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
