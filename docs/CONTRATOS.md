# Contratos de integración — Kvasir v2 (ML → DL)

**Fuente única de interfaces para Carlos (@itsCarlosDev) y François (@Francois0405).**
**Entrega interna máxima: 10/12/2026.**
La regla fundamental: **nadie debe esperar a que el otro termine su issue para poder programar y probar su módulo**. Se pueden usar *fixtures* sintéticas hasta que haya integración.

## 1. Manifest de datos (propietario: François, issue #2)

La salida de `src/split_dataset.py` será **`metadata/splits.csv`**, que contiene **solo metadatos** (no imágenes). Formato exacto:

```csv
image_path,class_name,split
polyps/polyps/imagen1.jpg,polyps,train
esophagitis/esophagitis/imagen2.jpg,esophagitis,test
```

- `image_path`: ruta relativa a `data/`, con separador `/`; debe ser única.
- `class_name`: texto exacto de una de las ocho categorías.
- `split`: `train` o `test`. **No cambiar la asignación después de publicarla.** El split de validación para ResNet se obtiene **solo de train**.
- Reparto orientativo: 80 % train, 20 % test, estratificado con semilla 42, **siempre que los datos permitan un reparto válido**. Separar duplicados y, si existe trazabilidad, grupos de paciente/vídeo/procedimiento. Si no, registrar esa limitación.
- El archivo **`metadata/class_names.json`** almacena este orden fijo y compartido de las 8 clases:

```json
["dyed-lifted-polyps","dyed-resection-margins","esophagitis","normal-cecum","normal-pylorus","normal-z-line","polyps","ulcerative-colitis"]
```

Las etiquetas numéricas son los índices 0–7 de ese array. **No** dependen del orden del sistema de archivos.

**Prueba sin esperar:** los demás módulos pueden generar localmente 16–80 filas ficticias con este mismo esquema. Los ejemplos ficticios son para probar interfaces, **nunca para reportar métricas finales**.

## 2. Características de ML (propietario: Carlos, issue #4)

`src/features_hls.py` exporta:

```python
extract_hls_features(image_path) -> dict[str, float]
```

Las claves mínimas serán:
`h_sin_mean, h_cos_mean, h_concentration, l_mean, l_std, s_mean, s_std`.

- Convertir cada imagen RGB a **HLS** y calcular el tono en el círculo: ángulo `2πh`, medias de seno/coseno, concentración `sqrt(mean_sin² + mean_cos²)`.
- No calcular la media aritmética de Hue (359° y 1° son próximos).
- RGB sigue siendo una **baseline experimental**, no la representación final impuesta. HLS es un cambio de coordenadas de color, **no crea información nueva por sí solo**; las características agregadas y patrones sí pueden mejorar la representación.
- Mantener `image_path` y `class_name` como columnas de metadatos, **nunca** como variables predictoras.
- Añadir histogramas HLS/textura solo si se justifica y no rompe el contrato de 7 atributos mínimos.

**Prueba sin esperar:** usar arrays RGB sintéticos (rojo uniforme y tonos próximos a 0°/360°) y comprobar rangos y claves. Los entrenadores pueden simular una matriz `X` numérica de 7 columnas mientras el extractor está en desarrollo.

## 3. Contrato de los cuatro modelos clásicos (issues #5 y #13)

Los módulos `src/ml_models_carlos.py` y `src/ml_models_francois.py` exportarán la misma función:

```python
get_model_grids() -> dict[str, tuple]  # {nombre: (Pipeline, param_grid_dict)}
```

- Cada módulo devuelve **2 clasificadores diferentes** de los del otro; **SVM, KNN, Random Forest y Regresión Logística son candidatos**, no opciones aprobadas por la profesora.
- La última etapa del `Pipeline` se llama `clf`, y la malla usa claves como `clf__C` o `clf__n_neighbors`. Escalado/transformaciones aprendidas siempre dentro del Pipeline.
- Los modelos aceptan `X`: matriz numérica con columnas HLS fijas, `y`: índices 0–7; nunca dependen de leer fotos o de un notebook concreto.
- `GridSearchCV` usa solo `train`, CV estratificada y la misma métrica principal (preferentemente F1-macro, justificada). Guardar `mean/std` de CV y mejores parámetros.
- Resultados tabulares: `results/cv_carlos.csv`, `results/cv_francois.csv`, con columnas mínimas `model,features,cv_f1_macro_mean,cv_f1_macro_std,cv_accuracy_mean,best_params`. `features` será `rgb` o `hls`.
- Un clasificador que no ofrezca `predict_proba` requerirá calibración ajustada **dentro de train/CV** si se quieren porcentajes interpretables. Evitar llamar «probabilidades clínicas» a las puntuaciones.

**Prueba sin esperar:** usar `X = np.random.default_rng(42).normal(size=(80, 7))` y `y = np.repeat(np.arange(8), 10)`. Hacer un smoke test de `get_model_grids()` y `fit/predict`. Los resultados sintéticos **no se incorporan a las conclusiones**.

## 4. Contrato de evaluación (François, #7; integración final Carlos, #14)

`src/ml_evaluation.py` exporta una función que acepta `y_true`, `y_pred`, `class_names` y opcionalmente `y_proba` de forma `(n, 8)`; produce métricas y figuras, sin leer test automáticamente.

- `class_names` y el orden de columnas de `y_proba` deben coincidir con `metadata/class_names.json`.
- Generar Accuracy, F1-macro, matriz de confusión, métricas por clase y AUC multiclase OvR cuando sea válido.
- Durante desarrollo: usar predicciones simuladas u **out-of-fold de train**, nunca el test.
- En #14, una vez congelados modelo/transformaciones/hiperparámetros, **Carlos evalúa el test ML una sola vez** y registra resultados para la futura comparación con DL.

## 5. Contratos de Deep Learning (fase posterior a ML)

- `src/dl_model.py` (Carlos): `build_model(num_classes=8)` devuelve ResNet-18 con salida **logits [batch, 8]**; `softmax` solo para presentar puntuaciones como probabilidades estimadas.
- `src/dl_data.py` (François): `build_dataloaders(manifest_path, batch_size=32)` devuelve `train_loader, val_loader, test_loader`; `val` se deriva solo de filas `train`. La entrada de ResNet-18 preentrenada es **RGB**, no HLS.
- `src/dl_train.py` (Carlos): `train_model(model, train_loader, val_loader, config)`; checkpoint elegido **solo por validación**.
- `src/dl_evaluation.py` (François): misma lista de ocho categorías, métricas del mismo test fijado en ML, una única evaluación final.

**Prueba sin esperar:** Carlos prueba ResNet-18 con `torch.randn(2,3,224,224)`; François prueba sus DataLoaders con imágenes generadas localmente. Los componentes se conectan al integrar la fase DL.

## 6. Flujo Git sin bloqueos ni merges cruzados

1. Ramas ya existentes: `feat/ml-carlos` y `feat/ml-francois`. Cada cual modifica **sus** archivos sin sobrescribir los del otro.
2. Se crea `integration/ml` desde `main`: las contribuciones se integran ahí **cuando estén listas** mediante PR, **no** mediante merges recíprocos de ramas completas.
3. Si alguien necesita antes una funcionalidad pequeña del otro, preferir `git cherry-pick <sha>` de un commit aislado, tras acordar el cambio; no mezclar todo el trabajo a medias.
4. Al terminar y probar ML en `integration/ml`, abrir **un único PR hacia `main`**, antes del **03/12**.
5. Después crear `feat/dl-carlos`, `feat/dl-francois` y `integration/dl` desde la `main` actualizada. Repetir el mismo ciclo y dejar `main` finalizada antes del **10/12**.
6. Este documento se añadió a `main` después de crear las ramas ML; **al empezar**, actualizar cada rama *una vez* desde `origin/main` para obtener el contrato común. Esto no exige esperar a las tareas del compañero.
7. Evitar que dos personas editen el mismo `.ipynb`; preferir módulos `src/` independientes y notebooks solo para informes/presentación.

## 7. Definition of Done para todos los issues

- [ ] Código o salida concreta ejecutable en su archivo asignado (no solo documentación/planificación).
- [ ] Smoke test local con fixture independiente cuando dependencias reales no estén listas.
- [ ] Entrada/salida compatible con este documento.
- [ ] Ninguna decisión de modelo basada en test.
- [ ] PR hacia rama `integration/ml` o `integration/dl` (según fase), revisión de otro colaborador y mención `Refs #N`.
- [ ] Merges hacia `main` **solo tras la validación integrada de cada fase**.

**Nota:** la integración final es una dependencia natural y deliberada; el *desarrollo inicial* de cada módulo no necesita esperar a otro módulo.
