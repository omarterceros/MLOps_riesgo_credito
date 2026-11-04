// Genera docs/Informe_ProyectoFinal_MLOps.docx a partir de los resultados reales del repositorio:
//   entrenamiento/modelo_desplegado.json, monitoreo/salidas/*.json|csv, docs/evidencia/salidas/*.txt
//   y las capturas docs/evidencia/capturas/*.png.
// Uso (desde docs/herramientas, donde esta instalado el paquete npm "docx"):  node build_informe.js
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, ImageRun, AlignmentType, ShadingType,
  BorderStyle, Table, TableRow, TableCell, WidthType, PageBreak,
} = require("docx");

const RAIZ = path.resolve(__dirname, "..", "..");
const CAP = path.join(RAIZ, "docs", "evidencia", "capturas");
const SAL = path.join(RAIZ, "docs", "evidencia", "salidas");
const OUT = path.join(RAIZ, "docs", "Informe_ProyectoFinal_MLOps.docx");
// La URL del repositorio se lee de docs/REPO_URL.txt (la escribe scripts/publicar_repo.ps1 al publicar).
const ARCHIVO_URL = path.join(RAIZ, "docs", "REPO_URL.txt");
const REPO_URL = process.env.REPO_URL || (fs.existsSync(ARCHIVO_URL) ? fs.readFileSync(ARCHIVO_URL, "utf-8").trim() : "")
  || "(pendiente: se completa al publicar el repositorio con scripts/publicar_repo.ps1)";
const PAGE_W_PX = 696;

// ----------------------------------------------------------------------------- datos reales
const leer = (f) => fs.readFileSync(path.join(RAIZ, f), "utf-8").replace(/\r/g, "");
const json = (f) => JSON.parse(leer(f));
const existe = (f) => fs.existsSync(path.join(RAIZ, f));

const M = json("entrenamiento/modelo_desplegado.json");
const CD = existe("monitoreo/salidas/concept_drift.json") ? json("monitoreo/salidas/concept_drift.json") : {};
const csv = (f) => {
  const [cab, ...filas] = leer(f).trim().split("\n");
  const cols = cab.split(",");
  return filas.map((l) => Object.fromEntries(l.split(",").map((v, i) => [cols[i], v])));
};
const LOTES = existe("monitoreo/salidas/concept_drift.csv") ? csv("monitoreo/salidas/concept_drift.csv") : [];
// Los reportes de data drift se leen del JSON (el CSV tiene comas dentro de "detalle").
const DD_ROJO = existe("monitoreo/salidas/data_drift_lote_derivado.json") ? json("monitoreo/salidas/data_drift_lote_derivado.json").variables : [];
const DD_VERDE = existe("monitoreo/salidas/data_drift_lote_normal.json") ? json("monitoreo/salidas/data_drift_lote_normal.json").variables : [];
const FRACCIONES = (CD.fraccion_reasignada || []).map((f) => `${Math.round(f * 100)} %`);
const FRACCIONES_TXT = FRACCIONES.length ? FRACCIONES.slice(0, -1).join(", ") + " y " + FRACCIONES[FRACCIONES.length - 1] : "";

// tabla de runs desde la salida del entrenamiento
function runsDesdeSalida() {
  const txt = leer("docs/evidencia/salidas/01-entrenar.txt");
  const ini = txt.indexOf("Runs ordenados por roc_auc");
  if (ini < 0) return [];
  const lineas = txt.slice(ini).split("\n").slice(2).filter((l) => l.trim() && !l.startsWith("Mejor run"));
  return lineas.map((l) => {
    const t = l.trim().split(/\s+/);
    return { run_name: t[0], familia: t[1], roc_auc: t[2], pr_auc: t[3], f1: t[4], accuracy: t[5], segundos: t[6], run_id: t[7] };
  });
}
const RUNS = runsDesdeSalida();
const f4 = (v) => (v === undefined || v === null || v === "" ? "" : Number(v).toFixed(4));
const f3 = (v) => (v === undefined || v === null || v === "" ? "" : Number(v).toFixed(3));

// ----------------------------------------------------------------------------- helpers docx
function pngSize(buf) { return { w: buf.readUInt32BE(16), h: buf.readUInt32BE(20) }; }
function h1(t) { return new Paragraph({ text: t, heading: HeadingLevel.HEADING_1, spacing: { before: 340, after: 160 } }); }
function h2(t) { return new Paragraph({ text: t, heading: HeadingLevel.HEADING_2, spacing: { before: 240, after: 120 } }); }
function h3(t) { return new Paragraph({ text: t, heading: HeadingLevel.HEADING_3, spacing: { before: 180, after: 100 } }); }
function p(t, o = {}) { return new Paragraph({ children: [new TextRun({ text: t, ...o })], spacing: { after: 140 } }); }
function pr(runs) { return new Paragraph({ children: runs.map((r) => (typeof r === "string" ? new TextRun(r) : new TextRun(r))), spacing: { after: 140 } }); }
function b(t) { return { text: t, bold: true }; }
function i(t) { return { text: t, italics: true }; }
function mono(t) { return { text: t, font: "Consolas", size: 19 }; }
function bullet(t, level = 0) { return new Paragraph({ text: t, bullet: { level }, spacing: { after: 80 } }); }
function bulletRuns(runs) { return new Paragraph({ children: runs.map((r) => new TextRun(typeof r === "string" ? { text: r } : r)), bullet: { level: 0 }, spacing: { after: 80 } }); }
function code(lines) {
  const runs = [];
  lines.forEach((l, k) => {
    if (k > 0) runs.push(new TextRun({ text: "", break: 1 }));
    runs.push(new TextRun({ text: l, font: "Consolas", size: 17, color: "D4D4D4" }));
  });
  const borde = { style: BorderStyle.SINGLE, size: 2, color: "333333" };
  return new Paragraph({ children: runs, shading: { type: ShadingType.CLEAR, fill: "1E1E1E" },
    spacing: { before: 60, after: 160 }, border: { top: borde, bottom: borde, left: borde, right: borde } });
}
function archivo(f, max = 400) {
  const lineas = leer(f).split("\n");
  return code(lineas.slice(0, max));
}
let nFig = 0;
const FIGS = [];
function figure(file, caption, maxW = PAGE_W_PX) {
  const fp = path.join(CAP, file);
  nFig += 1;
  FIGS.push({ n: nFig, file, caption });
  if (!fs.existsSync(fp)) {
    console.warn("AVISO: falta captura", file);
    return [p(`[Figura ${nFig}: falta la captura ${file}]`, { italics: true, color: "C00000" })];
  }
  const buf = fs.readFileSync(fp);
  const { w, h } = pngSize(buf);
  const width = Math.min(maxW, w);
  const height = Math.round(h * (width / w));
  return [
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 100, after: 60 },
      children: [new ImageRun({ type: "png", data: buf, transformation: { width, height } })] }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 220 },
      children: [new TextRun({ text: `Figura ${nFig}. ${caption}`, italics: true, size: 19 })] }),
  ];
}
function celda(t, opts = {}) {
  return new TableCell({
    children: [new Paragraph({ children: [new TextRun({ text: String(t), size: 18, bold: !!opts.bold, font: opts.mono ? "Consolas" : undefined })], spacing: { after: 0 } })],
    shading: opts.fill ? { type: ShadingType.CLEAR, fill: opts.fill } : undefined,
    margins: { top: 40, bottom: 40, left: 80, right: 80 },
  });
}
function tabla(encabezados, filas, anchos) {
  const rows = [new TableRow({ tableHeader: true, children: encabezados.map((e) => celda(e, { bold: true, fill: "DCE6F1" })) })];
  for (const fila of filas) rows.push(new TableRow({ children: fila.map((v, k) => celda(v, { mono: !!(anchos && anchos.mono && anchos.mono.includes(k)) })) }));
  return new Table({ rows, width: { size: 100, type: WidthType.PERCENTAGE }, columnWidths: anchos && anchos.cols });
}
const espacio = () => new Paragraph({ text: "", spacing: { after: 120 } });
const salto = () => new Paragraph({ children: [new PageBreak()] });

// ----------------------------------------------------------------------------- contenido
const alarma = CD.alarma_en_lote;
const loteRef = (k) => LOTES.find((l) => Number(l.lote) === k) || {};
const rojas = DD_ROJO.filter((r) => r.estado === "rojo").map((r) => r.variable);
const amarillasVerde = DD_VERDE.filter((r) => r.estado !== "verde").map((r) => r.variable);

const children = [];
const add = (...x) => x.flat().forEach((e) => children.push(e));

add(
  new Paragraph({ text: "Proyecto final: un modelo de riesgo crediticio llevado a producción con MLflow, Docker y Kubernetes, con pruebas de data drift y concept drift", heading: HeadingLevel.TITLE, spacing: { after: 120 } }),
  p("MIAV1E414 — ML-Ops y Puesta en Producción · Semana 4 · Proyecto final", { italics: true, size: 22 }),
  p("Omar Terceros Vallejos · trabajo individual", { size: 22 }),
  pr([b("Repositorio: "), mono(REPO_URL)]),
  pr([b("Modelo desplegado: "), mono(`${M.uri} = versión ${M.version}, run ${M.run_id} (${M.run_name}), roc_auc ${f4(M.roc_auc)}`)]),
  espacio(),

  h1("1. Resumen"),
  p(`El proyecto lleva un modelo de clasificación (¿el cliente de tarjeta de crédito entrará en mora el mes siguiente?) desde el entrenamiento hasta un despliegue reproducible y observable. Todo el ciclo de experimentación pasa por MLflow: ${RUNS.length} ejecuciones comparables en el experimento riesgo-credito, un Model Registry con dos versiones y el alias champion que marca la versión en producción (versión ${M.version}, run ${M.run_id}). El servicio de inferencia es una API FastAPI empaquetada en una imagen Docker propia que, al arrancar, carga el modelo por esa referencia del registro y no por una ruta de archivo. La imagen se despliega en el Kubernetes de Docker Desktop con un Deployment de 3 réplicas y un Service; se demostraron las réplicas en Running, el balanceo entre pods (cada respuesta dice qué pod la atendió), la autorreparación y el escalado. Por último, dos familias de pruebas automatizadas vigilan la degradación: data drift (Kolmogorov-Smirnov, chi-cuadrado y PSI por variable, en verde con datos del mismo origen y en rojo con datos derivados) y concept drift (12 lotes mensuales simulados, gráfica temporal de roc_auc y un criterio explícito de reentrenamiento${alarma ? `, que disparó la alarma en el lote ${alarma}` : ""}). Como extra, una interfaz web servida dentro del clúster consume la API a través del Service.`),
  p("El énfasis, como pide el enunciado, está en la ingeniería alrededor del modelo (empaquetado, alta disponibilidad, trazabilidad y detección de degradación) y no en la exactitud del modelo."),
  figure("diagrama-01-arquitectura.png", "Arquitectura general: entrenamiento y registro en MLflow en la máquina anfitriona; API en Kubernetes con 3 réplicas que cargan el modelo por alias; interfaz web que consume el Service; monitoreo de drift fuera del camino de la petición."),
  p("Cómo leer el diagrama: la zona superior es la máquina anfitriona (datos, entrenamiento, el servidor de MLflow con tracking, registry e interfaz, y el monitoreo); la inferior es el clúster de Kubernetes. Las flechas sólidas son flujo de datos o de peticiones; las punteadas son lecturas o escrituras del Model Registry. entrenar.py envía los runs al servidor; registrar.py lee el mejor run, aplica la compuerta de calidad y escribe el alias champion. La imagen Docker no contiene el modelo: cada pod del Deployment lo carga por alias desde host.docker.internal:5050 al arrancar y hasta entonces no recibe tráfico (readiness). El Service de la API (NodePort 30080) balancea entre los pods Ready; la interfaz (nginx) hace proxy de /api/ a ese Service por DNS interno y se expone en el NodePort 30081. Cada respuesta trae el pod que atendió y la versión y run_id del modelo: la trazabilidad cruza las dos zonas. El monitoreo (validación de datos, data drift, concept drift) carga el champion desde el registro para evaluar los lotes, fuera del camino de la petición."),

  h1("2. Modalidad y reparto de trabajo"),
  p("Trabajo individual. La tabla indica los componentes y quién los construyó; el historial de commits del repositorio (git log) está organizado por componente."),
  tabla(["Componente", "Qué incluye", "Integrante"], [
    ["Datos y esquema", "comun/esquema.py, comun/datos.py, datos/descargar.py, datos/credito.csv", "Omar Terceros"],
    ["Fase 1 · MLflow", "entrenamiento/entrenar.py (8 runs), entrenamiento/registrar.py (registry y alias)", "Omar Terceros"],
    ["Fase 2 · Docker", "servicio/api.py, Dockerfile, requirements-servicio.txt", "Omar Terceros"],
    ["Fase 3 · Kubernetes", "k8s/*.yaml (namespace, configmap, deployment, service, UI), scripts/", "Omar Terceros"],
    ["Fase 4 · Drift", "monitoreo/data_drift.py, lotes.py, concept_drift.py y tests/", "Omar Terceros"],
    ["Extra · Interfaz", "ui/index.html, ui/nginx.conf, k8s/04-05 UI", "Omar Terceros"],
    ["Documentación", "README.md, ARQUITECTURA.md, este informe y las evidencias", "Omar Terceros"],
  ], { cols: [2200, 5400, 1700] }),
  espacio(),
  p("Historial de commits (git log, del más reciente al más antiguo; el registro se tomó al generar este informe, así que el commit que lo actualiza se ve solo en el repositorio). Nota sobre el historial: el código se desarrolló y probó primero en local y los siete primeros commits se crearon por componente al consolidar el trabajo (por eso comparten hora); los siguientes reflejan las iteraciones reales del día (ajustes de MLflow 3, calibración del concept drift, evidencias, informe y correcciones de la revisión)."),
  archivo("docs/evidencia/salidas/00-git-log.txt", 40),

  h1("3. Fase 1 — Modelo, experimentación y trazabilidad con MLflow"),
  h2("3.1 Elección del problema y del dataset"),
  p("Dataset público Default of Credit Card Clients (Yeh & Lien, 2009), del UCI Machine Learning Repository (id 350), descargado de Kaggle (uciml/default-of-credit-card-clients-dataset, archivo UCI_Credit_Card.csv): 30.000 clientes de tarjetas de crédito de Taiwán y 23 variables de entrada: límite de crédito (LIMIT_BAL), sexo, nivel educativo y estado civil (categóricas), edad, estado de pago de los últimos seis meses (PAY_0…PAY_6, ordinales: -2/-1/0 al día, 1…9 meses de atraso), montos facturados (BILL_AMT1…6) y montos pagados (PAY_AMT1…6). La variable objetivo mora vale 1 si el cliente no pagó el mes siguiente (22,1 % de los casos)."),
  p("Cumple la restricción del enunciado (muchas más de 4 variables y 30.000 registros) y, sobre todo, tiene variables de tres tipos (numéricas, categóricas y ordinales), lo que permite aplicar una prueba estadística distinta por tipo en el análisis de drift y construir escenarios de deriva realistas (envejecimiento de la cartera, recorte de límites, más atrasos). El archivo datos/credito.csv está versionado en el repositorio (MD5 " + M.datos_md5 + ") y ese hash se guarda como tag de cada run, de modo que cada modelo queda enlazado a los datos exactos con los que se entrenó."),

  h2("3.2 Entrenamiento reproducible"),
  bullet("Semilla fija 42 en la partición y en todos los algoritmos (comun/esquema.py: SEMILLA = 42)."),
  bullet("División train/test 80/20 estratificada por mora: 24.000 clientes de entrenamiento y 6.000 de prueba (comun/datos.py: particion()). La misma función la usan el entrenamiento, el baseline del data drift y los lotes del concept drift."),
  bullet("Preprocesamiento dentro del pipeline (one-hot de SEX, EDUCATION y MARRIAGE; escalado del resto), de modo que lo que se empaqueta y despliega es el pipeline completo, no solo el estimador."),
  bullet(`${RUNS.length} ejecuciones con distintos algoritmos e hiperparámetros, todas sobre la misma partición y con las mismas métricas, por lo que son comparables entre sí: tres regresiones logísticas (C = 0.01, 0.1, 1), dos random forest (100 árboles/profundidad 8 y 200/12) y tres hist gradient boosting (learning rate 0.05 y 0.1 con 200 iteraciones, y 0.1 con 400 iteraciones y profundidad 4).`),
  h3("Por qué estas tres familias y estos ocho runs"),
  p("La selección sigue el criterio del módulo para elegir una técnica: el dato decide la familia, la pregunta decide la tarea y la métrica, y la restricción decide antes que la precisión. Dentro de la familia, los modelos se prueban como una escalera de tres escalones (línea base, modelo sólido, modelo exigente) y solo se sube un escalón si gana al anterior en la métrica principal sobre el mismo conjunto de prueba: el modelo correcto es el más simple que gana."),
  bullet("Dato: una tabla con etiqueta (30.000 filas, 23 columnas, objetivo mora). Para tablas la escalera es logística → bosque → boosting. Las redes neuronales no son el camino: en datos tabulares de tamaño mediano los árboles con boosting siguen ganando a las redes (Grinsztajn, Oyallon y Varoquaux, 2022) y piden más ajuste sin ganar. KNN, Naive Bayes y K-Means no aplican (K-Means es sin etiqueta; KNN y Naive Bayes no son escalón de ninguna escalera tabular con 23 variables mixtas)."),
  bullet("Pregunta: ¿entrará en mora el mes siguiente, sí o no? Es clasificación binaria con clase minoritaria (22 %), así que la métrica debe medir cómo ordena el modelo a los clientes (roc_auc, pr_auc) y no la exactitud, que se infla con el 78 % de no morosos."),
  bullet("Restricción: una decisión de crédito que hay que poder explicar (por eso la logística se conserva registrada como versión base), un servicio en línea que responde en milisegundos sin GPU (modelos tabulares de scikit-learn y la variante hist del boosting) y una clase minoritaria (umbral de decisión configurable en el ConfigMap y pr_auc registrada junto al AUC en todos los runs)."),
  bullet("Escalón 1, la línea base obligatoria: regresión logística. Es el punto de partida de toda clasificación: entrega una probabilidad, se interpreta (un coeficiente por variable) y fija el rival a vencer. Se probaron tres valores de C (0.01, 0.1 y 1: tres órdenes de magnitud de regularización L2) para demostrar que el techo de la familia (0.708 a 0.710) no depende del ajuste sino de la linealidad: los atrasos PAY_* y los montos interactúan y una frontera lineal no lo captura."),
  bullet("Escalón 2, el modelo sólido: random forest. Es el segundo escalón por defecto en tablas: funciona casi sin ajustar, captura no linealidades e interacciones y es estable. Se probaron dos tamaños (100 árboles con profundidad 8 y 200 con profundidad 12) para ver si crecer aporta: pasó de 0.7734 a 0.7739, es decir, la familia ya saturó. Gana a la logística por 0.064 de AUC, muy por encima del error de muestreo (~0.008 con 6.000 clientes; con la prueba pareada de DeLong la diferencia vale z ≈ 8.8): se sube el escalón."),
  bullet("Escalón 3, el modelo exigente: hist gradient boosting. Se prueba solo porque el bosque ya ganó y quedaba margen; es el modelo de referencia hoy en tablas cuando la precisión importa más que la explicación, y exige validación y early stopping (scikit-learn lo activa solo con más de 10.000 filas). La variante hist (histogramas, la misma idea que LightGBM) se eligió por latencia y volumen. Tres configuraciones: learning rate 0.05 y 0.1 sin tope de profundidad (hasta 31 hojas por árbol) y 0.1 con profundidad 4; max_iter (200, 200 y 400) es solo un tope, porque con el early stopping automático se detuvieron en 103, 49 y 104 árboles, así que lo que de verdad varió fue el learning rate y la profundidad. Frente al bosque la ganancia es pequeña (roc_auc 0.7797 frente a 0.7739; pr_auc 0.5568 frente a 0.5563) y, aunque la prueba pareada de DeLong la da significativa (z ≈ 2.5, p ≈ 0.01), se trata como ganancia pequeña y no concluyente: el champion se eligió mirando esta misma prueba entre cinco modelos de árboles, lo que infla la significancia, y no hay validación cruzada. Por la regla de la escalera, ante un empate queda el escalón más simple; lo que inclina al boosting es la restricción declarada de latencia: con 104 árboles de profundidad 4 predice una fila en unos 6 ms, frente a unos 50 ms del bosque de 200 árboles de profundidad 12 (medido en esta laptop; no es una métrica del run), y además no pierde en ninguna métrica registrada. Si la latencia no importara, el bosque sería igual de defendible (sección 8)."),
  p("Escrita como se pide en el módulo, la justificación es una tabla de iteraciones con una fila de descartados, no una opinión:"),
  tabla(["Iteración", "Modelo", "Complejidad", "roc_auc", "pr_auc", "Entrena", "Decisión"], [
    ["Línea base trivial", "Clase mayoritaria (nadie entra en mora)", "ninguna", "0.500", "0.221", "—", "exactitud 0.78 sin servir para nada: rival mínimo"],
    ["Escalón 1", "Regresión logística (mejor: C = 1)", "baja, interpretable", "0.7100", "0.4948", "0.1 s", "gana a la trivial; queda como versión 1 (baseline y rollback)"],
    ["Escalón 2", "Random forest (200 árboles, profundidad 12)", "media", "0.7739", "0.5563", "1.5 s", "gana con claridad (+0.064 AUC): se sube"],
    ["Escalón 3", "Hist gradient boosting (lr 0.1, profundidad 4, early stopping)", "alta", "0.7797", "0.5568", "0.4 s", "ganancia pequeña y no concluyente frente al bosque; la inclina la latencia de predicción (~6 ms frente a ~50 ms por fila): champion (versión 2)"],
    ["Descartado", "Red neuronal (MLP / deep learning)", "muy alta", "no evaluado", "—", "—", "tabla de 30.000 filas: no gana a los árboles (Grinsztajn et al., 2022); entraría solo si venciera al bosque en la prueba: es el siguiente experimento"],
    ["Descartado", "KNN, Naive Bayes, SVM con kernel, árbol único", "—", "no evaluado", "—", "—", "no son escalón de la escalera tabular; el árbol solo es inestable; SVM con kernel no escala a 24.000 filas"],
  ], { cols: [1150, 2250, 1100, 800, 750, 650, 3540] }),
  espacio(),
  p("Dentro de cada familia las diferencias son de milésimas; entre familias, de centésimas: la familia pesa más que el ajuste fino, y eso es lo que muestra la vista de comparación de MLflow. Los valores de la línea base trivial no son un run: salen de la definición (AUC 0.5 para un score constante; el área precisión-recall de un clasificador al azar es la prevalencia, 0.221)."),
  p("Resultado de python entrenamiento/entrenar.py (ordenado por roc_auc, la métrica principal):"),
  tabla(["Run", "Familia", "roc_auc", "pr_auc", "f1", "accuracy", "run_id"],
    RUNS.map((r) => [r.run_name, r.familia, r.roc_auc, r.pr_auc, r.f1, r.accuracy, r.run_id]),
    { cols: [1900, 1900, 900, 900, 800, 1000, 2900], mono: [0, 6] }),
  espacio(),
  figure("01-entrenar.png", "Salida real del entrenamiento: los 8 runs, sus métricas y el mejor run por roc_auc."),

  h2("3.3 Qué registra MLflow en cada run"),
  p("Todo el ciclo pasa por MLflow Tracking (servidor mlflow server en http://localhost:5050, backend SQLite y artefactos servidos por el propio servidor). Cada run guarda:"),
  bullet("Parámetros: familia del modelo, hiperparámetros, semilla, test_size, estratificación, tamaños de train/test y número de variables."),
  bullet("Métricas: roc_auc (principal), pr_auc, accuracy, f1, precision, recall y segundos de entrenamiento."),
  bullet("Tags: dataset, datos_md5 (huella del CSV), familia, metrica_principal y modelo_id."),
  bullet("Artefactos: matriz de confusión (PNG), reporte de clasificación (TXT), el conjunto de entrenamiento como input del run (nombre, fuente y esquema) y el modelo empaquetado con el flavor sklearn, con firma (signature) y ejemplo de entrada (input_example)."),
  p("No se guarda ningún modelo con pickle o joblib a mano ni se comparan métricas en una hoja de cálculo: la comparación se hace en la interfaz de MLflow."),
  figure("mlflow-01-experimento.png", "Interfaz de MLflow: el experimento riesgo-credito con los runs ordenados por roc_auc y las columnas de métricas y familia visibles."),
  figure("mlflow-05-filtro.png", "Filtro aplicado en la tabla de runs (metrics.roc_auc > 0.77 and tags.familia = 'hist_gradient_boosting'): quedan 3 runs."),
  figure("mlflow-02-comparacion.png", "Vista de comparación de MLflow con cuatro runs seleccionados: gráfico de coordenadas paralelas (parámetros y roc_auc) y detalles de los runs."),
  figure("mlflow-02b-comparacion-tabla.png", "La misma comparación, más abajo: parámetros y métricas de los cuatro runs lado a lado (accuracy, f1, pr_auc, precision, recall, roc_auc), que es donde se argumenta la elección del modelo."),

  h2("3.4 Registro y versionado del modelo (Model Registry)"),
  pr(["El modelo se registra con el nombre estable ", mono("riesgo-credito"), ". Se usan alias (recomendados en MLflow 3 en lugar de los stages) siguiendo el paradigma champion/challenger visto en clase:"]),
  bulletRuns([b(`Versión ${M.baseline.version} — alias baseline. `), `Run ${M.baseline.run_id} (${M.baseline.run_name}), roc_auc ${f4(M.baseline.roc_auc)}. Es el modelo base, simple e interpretable: la referencia contra la que se compara el resto y la versión a la que se vuelve en un rollback.`]),
  bulletRuns([b(`Versión ${M.version} — alias champion. `), `Run ${M.run_id} (${M.run_name}, ${M.familia}), roc_auc ${f4(M.roc_auc)}. Es el mejor run del experimento por la métrica principal y es la versión en producción. Cuando un reentrenamiento produzca un challenger, se registrará como versión 3 y solo tomará el alias champion si supera a la versión 2 en la métrica.`]),
  pr(["El servicio consume el modelo por la referencia ", mono(M.uri), ": al arrancar resuelve el alias en el registro, carga esa versión exacta y expone en /info y en cada respuesta la versión y el run que la produjo. Cambiar el modelo en producción es cambiar el alias y reiniciar los pods, sin reconstruir la imagen; la sección 5.5 muestra ese ciclo ejecutado (rollback a la versión 1 y vuelta a la 2)."]),
  tabla(["Referencia", "Versión", "Run", "Run name", "roc_auc", "Uso"], [
    [M.uri, String(M.version), M.run_id, M.run_name, f4(M.roc_auc), "En producción (lo cargan los pods)"],
    [`models:/${M.nombre_registro}@${M.baseline.alias}`, String(M.baseline.version), M.baseline.run_id, M.baseline.run_name, f4(M.baseline.roc_auc), "Modelo base / rollback"],
  ], { cols: [2600, 800, 2600, 1500, 800, 1900], mono: [0, 2] }),
  espacio(),
  p("Compuerta de calidad (quality gate): registrar.py no mueve el alias champion a ciegas. El candidato tiene que alcanzar un roc_auc mínimo de 0.75 (el modelo base logístico, 0.71, más 0.04, unas cuatro o cinco veces el error estándar del AUC con 6.000 clientes, ~0.0086 según Hanley-McNeil: un piso redondeado y conservador para que el candidato sea claramente mejor que el modelo simple) y además superar al champion actual si ya hay uno; si no cumple, el script termina con error y el alias no cambia. Si el candidato ya es la versión champion (como en la figura siguiente, donde el registro se volvió a ejecutar), la compuerta solo reconfirma el piso de 0.75; la condición de superar al champion se aplica a una versión nueva. Es el candado que evita que un reentrenamiento con datos malos reemplace al modelo en producción por uno peor. Hoy el candidato es el mejor run del experimento; en un entrenamiento continuo sería el run recién entrenado."),
  figure("02-registrar.png", "Salida de entrenamiento/registrar.py: versiones registradas, alias, el run de cada una y la compuerta de calidad reconfirmando a la versión 2 como champion (el candidato ya era el champion, así que solo se verifica el piso de 0.75)."),
  figure("mlflow-03-registry.png", "Model Registry en la interfaz de MLflow: el modelo riesgo-credito con sus versiones y alias."),
  figure("mlflow-04-version-champion.png", `Detalle de la versión ${M.version} (alias champion) en el registro, con el enlace al run que la produjo.`),

  h2("3.5 Interfaz de MLflow en la defensa"),
  p("El servidor se levanta con scripts\\mlflow_server.ps1 y queda en http://localhost:5050. Guion para mostrar en vivo:"),
  bullet("Abrir el experimento riesgo-credito: cada run es un algoritmo con una combinación de hiperparámetros entrenado sobre la misma partición; el nombre del run lo resume (por ejemplo hgb_lr0.1_200it)."),
  bullet("Ordenar la tabla por la columna roc_auc (clic en el encabezado) y filtrar, por ejemplo, metrics.roc_auc > 0.77 o tags.familia = 'hist_gradient_boosting'."),
  bullet("Marcar varios runs con la casilla de la izquierda y pulsar Compare (el botón aparece junto a Delete): la vista muestra parámetros y métricas en paralelo y permite explicar por qué se eligió el champion (mejor roc_auc con tiempo de entrenamiento de segundos) frente a la regresión logística base."),
  bullet(`Abrir Model registry (enlace propio en la barra lateral; la pestaña Models del experimento lista los modelos registrados por run, no el registro) → riesgo-credito → Version ${M.version}: lleva el alias champion y enlaza al run ${M.run_id} (Source Run); es la misma versión que devuelve http://localhost:30080/info.`),
);

add(
  h1("4. Fase 2 — Contenerización con Docker"),
  p("El servicio de inferencia corre dentro de un contenedor: la imagen contiene el código (comun/ y servicio/) y todas las dependencias fijadas por versión, incluida la de MLflow, así que no necesita Python ni librerías de la máquina anfitriona. El único servicio externo del que depende, a propósito, es el servidor de MLflow (Model Registry): el modelo no va dentro de la imagen sino que se descarga del registro al arrancar, porque la consigna exige consumirlo por su alias y no por una ruta de archivo. En Kubernetes esa dirección viene del ConfigMap; en un despliegue real sería un servidor de MLflow compartido (sección 8)."),
  h3("Dockerfile"),
  archivo("Dockerfile"),
  h3("requirements-servicio.txt (lo único que se instala en la imagen)"),
  archivo("requirements-servicio.txt"),
  p("Decisiones: imagen base python:3.13-slim fijada; primero las dependencias y después el código para aprovechar la caché de capas; usuario sin privilegios (appuser) con HOME propio para que MLflow pueda descargar el modelo; variables de entorno con valores por defecto (MLFLOW_TRACKING_URI, MODELO_NOMBRE, MODELO_ALIAS) que Kubernetes puede sobreescribir; .dockerignore excluye datos, pruebas, documentación y el entorno virtual."),
  figure("03-docker-build.png", "Construcción de la imagen riesgo-credito-api:1.0 (capas cacheadas) y la imagen resultante."),
  p("El contenedor levanta el servicio y responde peticiones sin pasos manuales: docker run, esperar a que /health devuelva 200 (el modelo ya está cargado) y pedir una predicción. La respuesta incluye el pod/hostname que atendió y la versión y run del modelo."),
  figure("04-docker-run.png", "Contenedor en ejecución: /health en 200, una predicción de alto riesgo por POST /predecir y el log que confirma la carga del modelo desde el registro."),
);

add(
  h1("5. Fase 3 — Despliegue en Kubernetes con réplicas"),
  p("Clúster local: el Kubernetes integrado de Docker Desktop (un nodo, v1.34.1). Los manifiestos están en k8s/ y se aplican con kubectl apply -f k8s/:"),
  bullet("00-namespace.yaml: namespace riesgo-credito."),
  bullet("01-configmap.yaml: MLFLOW_TRACKING_URI=http://host.docker.internal:5050 (el servidor de MLflow en la máquina anfitriona), MODELO_NOMBRE, MODELO_ALIAS=champion, UMBRAL_MORA."),
  bullet("02-deployment.yaml: 3 réplicas de riesgo-credito-api:1.0; POD_NAME inyectado desde metadata.name; requests (250m CPU, 512Mi) y limits (1 CPU, 1Gi); readinessProbe sobre /health (listo solo con el modelo cargado) y livenessProbe sobre /vivo (reinicia solo si el proceso dejó de responder, no si MLflow está caído); estrategia RollingUpdate con maxSurge 1 y maxUnavailable 0."),
  bullet("03-service.yaml: Service NodePort 30080 → puerto 8000 de los pods con la etiqueta app=riesgo-credito-api."),
  bullet("04-ui-configmap.yaml y 05-ui.yaml: la interfaz web (sección 7)."),
  h3("Deployment"),
  archivo("k8s/02-deployment.yaml"),
  figure("05-k8s-despliegue.png", "kubectl apply, espera del rollout y todos los objetos del namespace riesgo-credito."),

  h2("5.1 Demostración 1: tres réplicas en Running simultáneamente"),
  figure("06-k8s-replicas-running.png", "Los 3 pods del Deployment en Running y READY 1/1, y el EndpointSlice del Service con exactamente esas tres IPs. RESTARTS 1: la máquina se reinició durante la mañana y Kubernetes relanzó los contenedores por su cuenta."),

  h2("5.2 Demostración 2: el tráfico se distribuye entre réplicas"),
  p("Cada respuesta de la API devuelve el nombre del pod que la atendió (variable POD_NAME inyectada por Kubernetes). El script scripts/demo_balanceo.sh envía 12 peticiones sucesivas al Service (http://localhost:30080) y cuenta cuántas atendió cada pod."),
  figure("07-k8s-balanceo.png", "Doce peticiones sucesivas al Service atendidas por pods distintos y el conteo por pod."),

  h2("5.3 Demostración 3: autorreparación"),
  p("scripts/demo_autorreparacion.sh lanza en segundo plano un bucle que manda una petición al Service cada 0,5 s e imprime la hora, el código HTTP y el pod que atendió; dos segundos después elimina un pod con kubectl delete pod --wait=false (sin esperar a que termine). El ReplicaSet crea un pod nuevo de inmediato y todas las peticiones del bucle, incluidas las emitidas durante la eliminación, devuelven 200 atendidas por los pods que quedan: el Service deja de enrutar al pod que muere en cuanto deja de estar Ready."),
  figure("08-k8s-autorreparacion.png", "Bucle de peticiones concurrente con kubectl delete pod: todas devuelven HTTP 200, el pod eliminado desaparece y el ReplicaSet crea uno nuevo (edad de segundos) que queda en Running."),

  h2("5.4 Demostración 4: escalado"),
  p("kubectl scale cambia el número de réplicas de 3 a 5 y luego de vuelta a 3. Con 5 réplicas en Running, 10 peticiones se repartieron entre cuatro de los cinco pods: kube-proxy elige un pod al azar en cada conexión, así que con más peticiones aparecen los cinco."),
  figure("09-k8s-escalado.png", "Escalado a 5 réplicas en Running, reparto de 10 peticiones entre cuatro de ellas y vuelta a 3 réplicas."),

  h2("5.5 Trazabilidad en vivo"),
  pr(["GET /info del servicio desplegado devuelve el pod, el servidor de MLflow y el modelo cargado: nombre, alias, versión y run. Coincide con entrenamiento/modelo_desplegado.json y con lo que muestra el Model Registry: el modelo que sirve peticiones en el clúster es exactamente la versión ", b(String(M.version)), " del run ", mono(M.run_id), "."]),
  figure("10-k8s-trazabilidad.png", "GET /info contra el Service de Kubernetes y el archivo modelo_desplegado.json: misma versión y mismo run."),
  h3("Cambio de versión en producción sin reconstruir la imagen (rollback y promoción)"),
  p(`scripts/demo_cambio_version.sh ejecuta el ciclo completo: mueve el alias champion a la versión ${M.baseline.version} (rollback al modelo base) con scripts/cambiar_champion.py, hace kubectl rollout restart y, con maxSurge 1 / maxUnavailable 0, los pods se renuevan de a uno sin bajar de 3 pods listos (maxUnavailable 0); GET /info pasa a devolver la versión ${M.baseline.version} y su run. Después vuelve a mover el alias a la versión ${M.version} y repite el rolling update: el servicio vuelve a servir el champion. Es exactamente lo que haría el equipo cuando un challenger gane o cuando haya que volver atrás.`),
  figure("16-k8s-cambio-version.png", `Rollback y promoción por alias: /info antes (versión ${M.version}), tras mover el alias a la versión ${M.baseline.version} y reiniciar (versión ${M.baseline.version}), y al final de nuevo la versión ${M.version}; todo sin tocar la imagen.`),
);

add(
  h1("6. Fase 4 — Pruebas automatizadas de drift"),
  p("Antes de medir drift, el lote pasa por la validación de datos (segundo pilar visto en clase): monitoreo/validar_datos.py verifica el esquema (las 23 columnas numéricas), que no haya nulos, que los valores estén en los rangos del diccionario de datos y que haya un mínimo de filas; si falla, termina con código 1 y el flujo se detiene, porque un lote roto no debe disparar ni silenciar una alarma de drift (ni usarse para reentrenar). Los tres pilares quedan así cubiertos: código (24 pruebas con pytest), datos (validar_datos.py) y modelo (la compuerta de calidad al registrar, sección 3.4)."),
  figure("17-validar-datos.png", "Validación de datos: el lote normal pasa (código 0) y un lote con celdas vacías, códigos inexistentes y pagos negativos es rechazado con el detalle de cada problema (código 1)."),
  h2("6.1 Data drift (deriva de datos)"),
  p("monitoreo/data_drift.py compara cada una de las 23 variables de entrada de un lote nuevo contra el baseline de entrenamiento (los 24.000 clientes del conjunto de entrenamiento, la misma partición con la que se entrenó el champion)."),
  h3("Pruebas por tipo de variable y por qué"),
  bullet("Numéricas (LIMIT_BAL, AGE, BILL_AMT1…6, PAY_AMT1…6): prueba de Kolmogorov-Smirnov de dos muestras más PSI por deciles del baseline. KS es no paramétrica, no supone normalidad (los montos son muy asimétricos) y su estadístico D es la mayor distancia entre las dos distribuciones acumuladas, es decir, un tamaño de efecto interpretable. El PSI (índice de estabilidad poblacional) resume cuánta masa de probabilidad se movió entre deciles."),
  bullet("Categóricas y ordinales (SEX, EDUCATION, MARRIAGE, PAY_0…PAY_6): prueba chi-cuadrado de homogeneidad sobre la tabla de contingencia baseline/lote más PSI por categoría. KS no aplica a categorías nominales; chi-cuadrado compara las proporciones de cada categoría y la V de Cramer da el tamaño del efecto. Las categorías con menos del 1 % en el baseline se agrupan en otros para que las frecuencias esperadas sean razonables. Son dos pruebas para tres tipos de variable: las ordinales PAY_* (11 niveles enteros, muy concentrados en -2, -1 y 0) se tratan como categóricas a propósito, porque chi-cuadrado detecta cualquier cambio en la forma de la distribución (no solo de posición) y el PSI por categoría es directamente interpretable; una alternativa sensible al orden sería KS o Mann-Whitney sobre los códigos."),
  h3("Umbrales y de dónde salen"),
  bullet("PSI < 0.10 sin cambio; 0.10 a 0.25 cambio moderado (vigilar, amarillo); ≥ 0.25 cambio importante (rojo). Son los cortes clásicos de la industria del credit scoring (Siddiqi, Credit Risk Scorecards, 2006), el mismo dominio del dataset."),
  bullet("α = 0.01 para KS y chi-cuadrado. Se hacen 23 pruebas por lote: con α = 0.05 se esperaría más de un falso positivo por lote; con 0.01, cerca de 0.2."),
  bullet("Tamaño de efecto mínimo 0.10 (D de KS o V de Cramer). Con miles de filas una p muy pequeña aparece con cambios irrelevantes; para ponerse en rojo el cambio tiene que ser significativo y además de tamaño práctico. Un desplazamiento de un año en la edad, por ejemplo, es significativo pero no es rojo (prueba test_un_desplazamiento_pequeno_no_es_rojo)."),
  bullet("Estado por variable: ROJO si PSI ≥ 0.25 o (p < α y efecto ≥ 0.10); AMARILLO si PSI ≥ 0.10 o p < α; VERDE en otro caso. Estado del lote: el peor de sus variables."),
  h3("Lotes de prueba"),
  p("monitoreo/lotes.py genera dos lotes a partir del conjunto de prueba: lote_normal.csv (1.500 clientes al azar, mismo origen que el entrenamiento) y lote_derivado.csv (los mismos clientes con drift inyectado a propósito: AGE +12 años, LIMIT_BAL ×0.6, BILL_AMT1 ×1.8, la mitad de los clientes con EDUCATION = 3 y el 40 % con un mes más de atraso en PAY_0)."),
  p(`Resultado: el lote del mismo origen da VERDE${amarillasVerde.length ? ` (variables a vigilar: ${amarillasVerde.join(", ")})` : " en las 23 variables"} y el lote derivado da ROJO con ${rojas.length} variables en rojo (${rojas.join(", ")}): exactamente las que se derivaron, mientras que las no tocadas siguen en verde.`),
  tabla(["Variable", "Tipo", "Prueba", "Estadístico", "p-valor", "PSI", "Estado", "Detalle"],
    DD_ROJO.filter((r) => r.estado !== "verde").map((r) => [r.variable, r.tipo, r.prueba, f3(r.estadistico), Number(r.p_valor) < 0.001 ? Number(r.p_valor).toExponential(1) : f3(r.p_valor), f3(r.psi), r.estado.toUpperCase(), r.detalle]),
    { cols: [1300, 1100, 1100, 1000, 1000, 800, 1000, 2000] }),
  espacio(),
  figure("11-data-drift-verde.png", "Lote del mismo origen que el entrenamiento: las 23 variables evaluadas y estado del lote VERDE (código de salida 0)."),
  figure("12-data-drift-rojo.png", "Lote con datos derivados inyectados: variables en ROJO y estado del lote ROJO (código de salida 1)."),
  h3("La prueba automatizada: verde pasa, rojo falla"),
  p("tests/test_lote_produccion.py es la puerta de calidad que un pipeline de entrenamiento continuo ejecutaría con cada lote nuevo: recibe el lote con --lote, lo evalúa contra el baseline y falla (estado rojo) si hay drift. Con el lote normal pasa; con el lote derivado falla y el mensaje lista las variables con drift. Las demás pruebas de tests/test_data_drift.py verifican el detector en sí (PSI, tipo de prueba por variable, verde/rojo, efecto pequeño no es rojo)."),
  figure("13-pytest-lote.png", "pytest con el lote normal (1 passed) y con el lote derivado (1 failed: DATA DRIFT con las cinco variables)."),

  h2("6.2 Concept drift (deriva de concepto)"),
  h3("Escenario simulado"),
  p(`monitoreo/concept_drift.py construye ${CD.n_lotes || 12} lotes mensuales de ${CD.n_por_lote || 500} clientes (los 6.000 del conjunto de prueba, sin reposición, que el modelo nunca vio al entrenar). En los lotes 1 a ${(CD.inicio_drift || 7) - 1} las etiquetas son las reales. Desde el lote ${CD.inicio_drift || 7} cambia la regla del mundo sin tocar las entradas: un shock económico hace que clientes que venían pagando al día (PAY_0 ≤ 0) caigan en mora; se reasigna mora = 1 a una fracción creciente de ellos (${FRACCIONES_TXT}), un shock que empieza suave y se agrava mes a mes, como una crisis real. Las X son idénticas, por lo que el detector de data drift no lo ve: solo se nota al comparar las predicciones con las etiquetas reales.`),
  h3("Métrica por lote y gráfica temporal"),
  p(`Se evalúa el champion (versión ${M.version}, roc_auc de referencia ${f4(CD.roc_auc_referencia)} sobre el conjunto de prueba al entrenarlo) en cada lote: roc_auc y f1 con etiqueta, y dos señales que no necesitan etiqueta (PSI de la distribución de scores del lote respecto de la distribución de scores de referencia, la del conjunto de prueba al entrenar, y tasa de positivos predicha).`),
  figure("concept_drift.png", "Degradación de roc_auc en los 12 lotes mensuales (arriba) y señales sin etiqueta frente a la tasa de mora real que llega con retraso (abajo)."),
  tabla(["Lote", "n", "roc_auc", "f1", "mora real", "positivos predichos", "PSI score", "bajo umbral", "regla nueva"],
    LOTES.map((l) => [l.lote, l.n, f4(l.roc_auc), f4(l.f1), f3(l.tasa_mora_real), f3(l.tasa_positivos_predicha), f3(l.psi_score), l.bajo_umbral === "True" ? "sí" : "no", l.regla_nueva === "True" ? "sí" : "no"]),
    { cols: [700, 700, 1000, 1000, 1100, 1400, 1100, 1100, 1100] }),
  espacio(),
  figure("15-concept-drift.png", "Salida de monitoreo/concept_drift.py: tabla por lote y decisión del criterio de reentrenamiento."),
  h3("Criterio de reentrenamiento"),
  bullet(`Alarma cuando la caída de roc_auc respecto de la referencia supera 0.05 absoluto durante 3 lotes consecutivos (umbral = ${f4(CD.roc_auc_referencia)} − 0.05 = ${f4(CD.roc_auc_referencia - 0.05)}); alarma inmediata si la caída supera 0.12 en un solo lote (casi cinco errores estándar: una caída catastrófica que no admite esperar tres meses).`),
  bullet("Por qué 0.05: con n = 500 y una tasa de mora del 22 % (unos 110 positivos y 390 negativos por lote), el error estándar del AUC es de unos 0.025–0.03 (fórmula de Hanley-McNeil), así que 0.05 está a unos dos errores estándar y no es ruido de muestreo. De hecho, en los lotes estables se ven oscilaciones de ±0.03 que no deben disparar nada."),
  bullet("Por qué 3 lotes: un mes malo puede ser estacional o un problema de datos; tres meses seguidos es un cambio sostenido, y el costo de reentrenar (horas) es menor que el de operar tres meses más con un modelo equivocado."),
  bullet(alarma ? `Resultado de la simulación: la alarma se disparó en el lote ${alarma} (la regla cambió en el lote 7; a los tres lotes seguidos bajo el umbral se declara concept drift y se lanza el reentrenamiento del challenger). roc_auc del lote 6: ${f4(loteRef(6).roc_auc)}; del lote 7: ${f4(loteRef(7).roc_auc)}; del lote 12: ${f4(loteRef(12).roc_auc)}.` : "Resultado de la simulación: sin alarma."),
  bullet("Qué pasa al disparar la alarma: se entrena un challenger con los datos de la regla nueva (lotes recientes ya etiquetados, posteriores al cambio de regla del lote 7: en este concept drift los datos anteriores al cambio enseñan la regla vieja), se registra como nueva versión en el Model Registry y solo si supera al champion en roc_auc sobre un conjunto de validación reciente se mueve el alias champion y se hace rolling update de los pods (kubectl rollout restart), sin cortar el servicio. Si sale mal, el alias vuelve a la versión anterior: rollback inmediato."),
  h3("El problema del retraso de etiquetas"),
  p("En producción la etiqueta real (mora del mes siguiente) se conoce recién 30 a 90 días después de la predicción, y la definición operativa de mora suele requerir 90 días de atraso. Durante ese tiempo no se puede calcular roc_auc del lote. Qué hace el equipo mientras tanto:"),
  bullet("Señales sin etiqueta calculadas el mismo día: data drift de las entradas (6.1), PSI de la distribución de scores respecto del entrenamiento y tasa de positivos predicha. Son el radar temprano. La simulación muestra también su límite: en un concept drift puro las entradas y los scores no cambian (PSI del score ≈ 0 en todos los lotes), así que estas señales detectan data drift y cambios de mezcla, pero no un cambio de regla con X idéntico."),
  bullet("Evaluación con retraso: cada lote se cierra cuando llegan sus etiquetas; la gráfica temporal se construye con lotes cerrados y el criterio de 3 lotes se aplica sobre ellos. Para acortar el retraso, en producción se usaría una etiqueta proxy temprana: el primer atraso observado a los 30 días de la predicción (el estado de pago del mes siguiente, que este dataset no trae: PAY_0 es el estado del mes en que se predice, una entrada, y usarlo como etiqueta sería fuga de información; por eso la simulación trabaja con la etiqueta final)."),
  bullet("Muestreo con revisión humana: una muestra pequeña de solicitudes se revisa antes de los 90 días por analistas de riesgo para tener una estimación temprana de la tasa de error."),
  bullet("Challenger en sombra: ante señales tempranas se entrena ya un candidato con los datos más recientes y se lo corre en paralelo (shadow) sin exponerlo; cuando las etiquetas confirman la caída, la comparación champion/challenger ya está lista y la promoción es inmediata."),
  h3("Pruebas automatizadas"),
  p("tests/test_concept_drift.py verifica el detector con un modelo entrenado en la propia prueba: el criterio no dispara sin caída ni con bajas aisladas, dispara con tres lotes seguidos o con una caída crítica, no hay alarma sin cambio de regla (a lo sumo lotes aislados bajo el umbral por azar, nunca una racha), con la regla nueva la alarma salta después del cambio con los tres lotes previos bajo el umbral y una caída media mayor que 0.05, y el PSI de los scores es idéntico con y sin concept drift (las entradas no cambian). La suite completa (24 pruebas) se ejecuta con pytest."),
  figure("14-pytest-suite.png", "Suite completa: 24 pruebas (API, validación de datos, data drift, concept drift y puerta del lote) en verde."),
);

add(
  h1("7. Puntos extra — API y consumo desde una interfaz"),
  p("La API (FastAPI) expone POST /predecir, GET /health, GET /vivo, GET /info y GET /esquema, con documentación Swagger en /docs y validación de entradas con Pydantic (rangos del diccionario de datos: un SEX = 3 o una edad de 10 años devuelven 422)."),
  p("La interfaz es una página HTML con JavaScript (ui/index.html) servida por nginx dentro del clúster (Deployment riesgo-credito-ui, Service NodePort 30081). nginx hace de proxy inverso de /api/ hacia el Service riesgo-credito-api por DNS interno del clúster (riesgo-credito-api.riesgo-credito.svc.cluster.local), de modo que el consumo es real contra el servicio desplegado en Kubernetes y no contra un proceso local; el navegador solo habla con la UI y no hace falta CORS. La página construye el formulario desde GET /esquema, trae dos ejemplos (bajo y alto riesgo), muestra la probabilidad de mora, el pod que atendió y la versión/run del modelo, y tiene un botón de ráfaga de 12 peticiones que lista qué pod atendió cada una (balanceo visible desde la interfaz)."),
  figure("ui-01-prediccion.png", "Interfaz web en http://localhost:30081: predicción de un solicitante de alto riesgo con el pod que la atendió y la versión del modelo."),
  figure("ui-02-rafaga.png", "Ráfaga de 12 peticiones desde la interfaz: las atienden pods distintos del Deployment."),
  figure("api-docs.png", "Documentación Swagger de la API desplegada (http://localhost:30080/docs)."),
);

add(
  h1("8. Decisiones de arquitectura y preguntas probables de la defensa"),
  p("El documento de arquitectura completo está en ARQUITECTURA.md del repositorio. Resumen de las decisiones y su porqué:"),
  tabla(["Decisión", "Por qué"], [
    ["Dataset real de 23 variables en lugar de Iris", "Tres tipos de variables permiten una prueba estadística por tipo y escenarios de drift realistas; 30.000 filas dan lotes mensuales de tamaño creíble."],
    ["roc_auc como métrica principal", "Clase positiva minoritaria (22 %) y decisión de negocio basada en la probabilidad con umbral ajustable; AUC no depende del umbral y compara modelos entre sí."],
    ["8 runs de lo simple a lo complejo", "Comparar varios modelos y fundamentar la elección en la vista de comparación de MLflow, no elegir el primero."],
    ["Preprocesamiento dentro del pipeline", "Lo que se empaqueta es el modelo completo; el servicio no repite lógica de transformación."],
    ["Alias champion/baseline en el registro", "MLflow 3 recomienda alias; cambiar de versión en producción es mover el alias y reiniciar pods; la versión base queda para rollback."],
    ["El modelo no viaja en la imagen", "Una sola imagen sirve cualquier versión del registro; trazabilidad explícita (versión y run en cada respuesta). Costo: el arranque depende del servidor de MLflow, cubierto con reintentos y readiness probe."],
    ["3 réplicas, probes, requests/limits, rolling update sin indisponibilidad", "Alta disponibilidad, tráfico solo a pods con el modelo cargado, memoria acotada, cambio de versión sin cortar el servicio."],
    ["MLflow en la máquina anfitriona", "La UI debe mostrarse en vivo; es lo más simple de operar. En un equipo real sería un servicio compartido con base de datos y almacén de artefactos remotos."],
    ["Umbrales de drift explícitos y justificados", "PSI 0.10/0.25 del credit scoring, α = 0.01 por las 23 pruebas, efecto mínimo 0.10 para no alertar por cambios sin tamaño práctico; 0.05 y 3 lotes para el concept drift."],
  ], { cols: [3000, 6300] }),
  espacio(),
  h3("Limitaciones reconocidas"),
  bullet("La elección del champion se hizo sobre el conjunto de prueba (no hay un conjunto de validación separado ni validación cruzada) y los cinco modelos de árboles están a menos de 0.007 de roc_auc entre sí. El champion le gana al mejor bosque por 0.0059; con la prueba pareada de DeLong sobre la misma prueba esa diferencia tiene un error estándar de 0.0023 (z ≈ 2.5, p ≈ 0.01), pero no se presenta como victoria: el champion se eligió mirando esta misma prueba entre cinco modelos de árboles, lo que infla la significancia. Se trata como una ganancia pequeña y no concluyente, desempatada por la restricción de latencia de predicción; el bosque sería igualmente defendible. El énfasis del proyecto es la ingeniería; el desempate riguroso sería validación cruzada estratificada (5 particiones) o bootstrap, registrando en MLflow la media y la desviación de roc_auc."),
  bullet("HistGradientBoostingClassifier activa early stopping automáticamente con más de 10.000 filas: max_iter es un tope, no el número de iteraciones entrenadas (los tres runs hgb, declarados con max_iter 200, 200 y 400, se detuvieron en 103, 49 y 104 iteraciones por su criterio interno de validación con el 10 % del train). El champion entrena en 0.4 s porque sus árboles son chicos (profundidad 4): con profundidad libre y learning rate 0.05, un número parecido de árboles (103) tardó 3.6 s. Los runs hgb difieren de verdad en learning_rate y max_depth; en una siguiente iteración se registraría n_iter_ como métrica de cada run."),
  bullet("El servidor de MLflow corre en la máquina anfitriona con SQLite: válido para la demo y para la defensa, pero en producción sería un servicio compartido con base de datos y almacén de artefactos propios, desplegado en el clúster o en la nube."),
  h3("Preguntas probables y respuesta corta"),
  bullet("¿Por qué ese modelo y no la regresión logística? Porque se subió la escalera de la clase de modelos: la logística es la línea base obligatoria (0.710) y perdió con claridad frente al bosque (0.774: una diferencia de casi nueve errores estándar con la prueba pareada de DeLong, z ≈ 8.8); el boosting se probó porque el bosque ya había ganado y quedaba margen, y frente al bosque la ganancia es pequeña y no concluyente (+0.006), desempatada por la restricción de latencia de predicción (unos 6 ms frente a unos 50 ms por fila) y porque no pierde en ninguna métrica registrada. La logística queda registrada como versión base para rollback y como referencia de interpretabilidad; el bosque sería igualmente defendible."),
  bullet("¿Por qué tres regresiones logísticas, dos random forest y tres gradient boosting? Porque son los tres escalones de la escalera para tablas con etiqueta (línea base, modelo sólido, modelo exigente) y en cada escalón se varió el hiperparámetro que define a la familia: C en la logística (tres órdenes de magnitud, para probar que su techo es la linealidad y no la regularización), tamaño y profundidad en el bosque (para ver que crecer ya no aporta) y learning rate y profundidad en el boosting (el número de árboles lo fija el early stopping: 103, 49 y 104). Los números muestran que la familia pesa más que el ajuste: dentro de cada familia las diferencias son de milésimas; entre familias, de centésimas."),
  bullet("¿Por qué roc_auc como principal y no PR-AUC, si la clase es minoritaria? La tabla maestra de la clase pone la mora con PR-AUC, y la lámina de métricas advierte que el ROC-AUC se infla con la clase mayoritaria. Me aparté de eso y lo declaro: usé roc_auc como principal porque la decisión de crédito usa la probabilidad con un umbral ajustable, y un 22 % de positivos (1.327 morosos en la prueba) no es una clase extrema. Pero pr_auc está registrado en los 8 runs y da el mismo orden entre familias tomando el mejor run de cada una (azar 0.221 → logística 0.495 → bosque 0.556 → boosting 0.557); dentro de los árboles el orden cambia: el bosque de 200 árboles supera a dos de los tres boosting y queda a 0.0005 del champion. Con precisión ≥ 0.5, el champion recupera el 60 % de los morosos, el bosque el 59 % y la logística el 50 % (cálculo posterior sobre la misma prueba, no registrado en MLflow)."),
  bullet("¿Por qué no deep learning? Porque el dato es una tabla de 30.000 filas, y en tablas los modelos de árboles siguen ganando a las redes (Grinsztajn, Oyallon y Varoquaux, 2022). La regla de la clase es que una red entra solo si vence al bosque en la prueba. No se registró como run: queda en la fila de descartados como el siguiente experimento."),
  bullet("¿Cómo sé que el pod sirve el modelo del registro? GET /info y cada respuesta devuelven versión y run_id; coinciden con el alias champion en el Model Registry y con modelo_desplegado.json."),
  bullet("¿Qué pasa si se cae el servidor de MLflow? Los pods que ya cargaron el modelo siguen sirviendo (está en memoria). Un pod nuevo reintenta la carga cada 10 s y, mientras tanto, la readiness (/health en 503) lo deja fuera del Service; la liveness apunta a /vivo, que responde mientras el proceso esté vivo, así que Kubernetes no lo reinicia por una caída de MLflow."),
  bullet("¿Data drift siempre implica reentrenar? No: se vigila. Reentrenar lo decide el concept drift (la métrica cae de forma sostenida). El data drift sí obliga a investigar la fuente de datos. Y si la población nueva es legítima y hace falta cubrirla, el reentrenamiento es con datos viejos más nuevos, sin descartar los viejos: el modelo no está equivocado, le faltaba evidencia en esa región."),
  bullet("¿Por qué KS para numéricas y chi-cuadrado para categóricas? KS compara distribuciones continuas sin suponer forma; en categorías no hay orden ni acumulada, así que se comparan proporciones por categoría con chi-cuadrado; el PSI sirve para ambas y es el estándar del dominio."),
  bullet("¿Cómo se cambia de versión sin cortar el servicio? Se mueve el alias champion a la nueva versión y se hace kubectl rollout restart: con maxSurge 1 y maxUnavailable 0 Kubernetes no baja de 3 pods listos durante el rollout: lo garantiza la estrategia del manifiesto; la sección 5.5 muestra el cambio de versión ejecutado y la 5.3 muestra que el Service no corta el tráfico cuando sale un pod."),
  bullet("¿Cuándo se reentrena? En la clase vimos tres disparadores. En este proyecto está implementado el de rendimiento: caída de roc_auc > 0.05 durante 3 lotes (o > 0.12 en uno), que es el criterio de concept drift. El de tiempo (un CT programado) sería el siguiente paso, junto con CI/CD. El data drift no reentrena solo: obliga a investigar la fuente, porque un cambio en X no implica que la regla haya cambiado. Todo modelo reentrenado es un challenger que pasa por la misma compuerta de calidad antes de reemplazar al champion."),
  bullet("¿Con qué datos se reentrena la versión nueva: solo los nuevos, todos? Depende del tipo de drift, y por eso el monitoreo los separa. Ante data drift el modelo no está equivocado: ve entradas para las que no tenía evidencia, así que no se descartan los datos viejos y, si se reentrena, es con viejos más nuevos. Ante concept drift cambió la relación entre X y la mora y los datos viejos enseñan la regla vieja (en el ejercicio de la clase, mezclar todo el histórico dio peor error que entrenar solo con el mundo nuevo); la estrategia depende de la forma del cambio: un corte limpio pide entrenar con los lotes de la regla nueva; un cambio gradual, una ventana deslizante reentrenada cada mes con más peso a lo reciente; uno estacional no descarta el modelo viejo, que sigue sirviendo para su temporada (un modelo por régimen o variables de estacionalidad). En este proyecto el challenger se entrena con los lotes recientes ya etiquetados porque la simulación es un cambio de regla que arranca en el lote 7 y se agrava mes a mes; como el cambio sigue agravándose, en producción sería una ventana deslizante mensual con más peso a lo reciente."),
  bullet("¿Blue-green, canary o A/B? El Deployment hace rolling update (maxSurge 1, maxUnavailable 0): reemplaza los pods de a uno, sin dos entornos gemelos, así que no es blue-green estricto, aunque comparte con él el rollback rápido (kubectl rollout undo o mover el alias). Como cambiar el modelo es un riesgo de comportamiento, lo indicado según la clase es canary: un segundo Deployment del challenger con el 10 % del tráfico detrás del mismo Service. Blue-green (dos entornos completos, el doble de costo) se reserva para riesgo de infraestructura. Un A/B compararía la métrica de negocio de ambos con una prueba estadística. No se implementaron porque el enunciado no lo pide, pero el diseño lo permite sin cambiar la imagen."),
  bullet("¿Qué se monitorea? Las tres capas: técnica (probes, kubectl get pods y los restarts: ¿está vivo?), datos y modelo (data drift por variable, PSI del score, tasa de positivos, roc_auc por lote: ¿entiende el mundo de hoy?) y negocio (tasa de mora real de la cartera aprobada y pérdida esperada frente al ingreso por créditos: ¿genera valor?; no se implementó porque el dataset no trae montos de pérdida)."),
  bullet("¿Por qué umbral de decisión 0.5? roc_auc mide si el modelo ordena bien a los clientes, independiente del umbral. El umbral lo fija el negocio según el costo de un falso negativo (aprobar a un moroso) frente a un falso positivo (rechazar a un buen cliente); 0.5 es provisional y configurable en el ConfigMap (UMBRAL_MORA); con costos reales bajaría a 0.2–0.3 para ganar recall."),
  bullet("¿Nivel de madurez? Nivel 0 avanzado, en camino al 1 (escala de Google vista en clase). Hay tracking y registry en MLflow, despliegue reproducible con imagen y manifiestos, compuerta de calidad al registrar (registrar.py) y validación de datos y drift automatizados con pytest. El nivel 1 exige entrenamiento continuo (CT) orquestado, y eso no está: las piezas que lo dispararían ya existen (el criterio de concept drift y la compuerta), pero falta orquestarlas con CI/CD/CT (GitHub Actions), que el enunciado deja fuera."),
);

add(
  h1("9. Cómo reproducirlo"),
  code([
    "python -m venv .venv && .\\.venv\\Scripts\\pip install -r requirements.txt",
    ".\\scripts\\mlflow_server.ps1              # MLflow en http://localhost:5050 (dejar abierto)",
    ".\\scripts\\entrenar_y_registrar.ps1       # datos, 8 runs y registro del champion",
    ".\\scripts\\desplegar_k8s.ps1              # imagen Docker + kubectl apply -f k8s/",
    "bash scripts/demo_balanceo.sh 12          # balanceo entre pods",
    "python monitoreo/lotes.py && python monitoreo/validar_datos.py monitoreo/lotes/lote_normal.csv",
    "python monitoreo/data_drift.py --lote monitoreo/lotes/lote_derivado.csv   # rojo, exit 1",
    "python monitoreo/concept_drift.py         # grafica y alarma",
    "pytest                                    # 24 pruebas",
    "pytest tests/test_lote_produccion.py --lote monitoreo/lotes/lote_derivado.csv   # falla: rojo",
  ]),
  p("Versiones: Python 3.13 · mlflow 3.18.0 · scikit-learn 1.9.1 · pandas 3.1.0 · fastapi 0.162.0 · Docker Desktop con Kubernetes v1.34.1."),

  h1("10. Listado de evidencias"),
  p("Cómo se tomaron las evidencias: todos los comandos se ejecutaron en Windows 11 desde Git Bash (MINGW64, el bash que instala Git para Windows), con el kubectl y el docker de Docker Desktop y el Python del entorno virtual del proyecto; por eso la sintaxis de las capturas es la de bash (bucles for, $(…), tuberías). docs/herramientas/cap.sh ejecuta cada comando real y guarda su salida completa con tee en docs/evidencia/salidas/*.txt; las imágenes de terminal de este informe se generan desde esos archivos de texto con docs/herramientas/render_terminal.py, que reproduce la ventana de Git Bash (barra de título de Windows, el prompt usuario@equipo MINGW64 ruta (rama), el comando y su salida tal cual quedó guardada). Las capturas de la interfaz de MLflow, de la interfaz web y de Swagger son capturas de navegador. La gráfica de concept drift la genera monitoreo/concept_drift.py. Los scripts de PowerShell de scripts/ (mlflow_server.ps1, entrenar_y_registrar.ps1, desplegar_k8s.ps1, publicar_repo.ps1) son atajos para una consola de PowerShell; los scripts .sh son para Git Bash.", { italics: true }),
);
FIGS.forEach((f) => children.push(bullet(`Figura ${f.n} (${f.file}): ${f.caption}`)));

const doc = new Document({
  creator: "Omar Terceros Vallejos", lastModifiedBy: "Omar Terceros Vallejos", title: "Proyecto final ML-Ops: riesgo de crédito (riesgo-credito-mlops)",
  styles: { default: { document: { run: { font: "Calibri", size: 22 } } } },
  sections: [{ properties: { page: { size: { width: 12240, height: 15840 }, margin: { left: 1000, right: 1000, top: 1134, bottom: 1134 } } }, children }],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(OUT, buf);
  console.log("OK:", OUT, buf.length, "bytes,", FIGS.length, "figuras");
});
