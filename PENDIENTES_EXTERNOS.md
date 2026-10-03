# Pendientes externos

Todo el trabajo técnico está completo y verificado (ver `docs/registro_validacion.md`).

## 1. URL del repositorio — COMPLETADO

Repositorio público: https://github.com/PabloV2003/tp2-charizard-ga

La URL figura en la referencia 15 del informe (`docs/informe_final.docx` / `.pdf`) y en la matriz de cumplimiento.
Si el repositorio se renombra o se mueve, actualizarla con:

```
.venv\Scripts\python scripts\build_report.py --repo-url https://github.com/USUARIO/NUEVO-REPO
.venv\Scripts\python scripts\run_validation.py
.venv\Scripts\python scripts\make_package.py
```

## 2. Fecha de presentación

La portada usa **03/10/2026** (fecha de preparación de esta versión final; no se reutilizó la de la entrega parcial
ni se inventó una fecha límite). Si se entrega otro día, cambiar `fecha_presentacion` en `config/report.json`,
ejecutar `.venv\Scripts\python scripts\build_report.py` y subir el cambio (`git commit` + `git push`).

## 3. Entrega en el Campus Virtual

Subir `docs/informe_final.pdf` (y el `.docx` si la cátedra lo pide) a la tarea correspondiente del aula virtual.

## 4. Verificación en Linux/macOS (opcional)

Los comandos para Linux/macOS del README no se pudieron verificar en este entorno (solo Windows 11). La exportación a
PDF depende de Microsoft Word; en otros sistemas usar `--no-pdf` y exportar el DOCX manualmente.
