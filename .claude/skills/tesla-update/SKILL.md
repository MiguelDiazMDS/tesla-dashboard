---
name: tesla-update
description: Actualización mensual del cuadro de mando de Tesla. Carga y verifica datos, se detiene ante un trimestre nuevo para que el usuario decida sobre los supuestos, valora, registra el histórico, construye la página, la republica en la misma URL, hace el commit y resume los cambios. Úsala cuando el usuario pida actualizar el dashboard o la valoración de Tesla, o escriba /tesla-update.
---

# Actualización mensual del cuadro de mando de Tesla

Herramienta analítica basada en los supuestos del usuario; no es asesoramiento de inversión. No des recomendaciones de compra o venta.

Trabaja siempre desde la raíz de este repositorio, en `master`. git existe solo en esa carpeta: nunca uses git fuera de ella ni lo inicialices en una carpeta superior.

Artifact publicado: su URL está en `.env`, en `ARTIFACT_URL` (no se sube al repositorio). Republica siempre ese. Si esta conversación no lo publicó, léelo antes con la acción `read` y publica pasándolo como `url`.

Nunca ejecutes `python -m src.valorar` a mano en esta rutina: la pausa de revisión de supuestos solo la garantiza `completar`.

## 1. Preparar

1. `git status --short` debe estar limpio. Si no, pregunta al usuario antes de seguir.
2. `python -m src.actualizar preparar`. Descarga de la SEC, Tesla, Nasdaq, el Tesoro y el BCE, con reintentos ante fallos pasajeros; puede tardar varios minutos. Necesita `SEC_USER_AGENT`, definida en `.env`. El valor lleva espacios sin comillas, así que `.env` no se puede cargar con `source`; en la misma orden de Bash que `preparar`:

   ```bash
   export SEC_USER_AGENT="$(grep '^SEC_USER_AGENT=' .env | cut -d= -f2- | tr -d '\r')" && python -m src.actualizar preparar
   ```
3. Si se niega o falla: muestra el mensaje tal cual y detente. Si el mensaje habla de periodos eliminados, es casi siempre una descarga fallida: ofrece restaurar con `git checkout data/` y reintentar más tarde. No retoques datos, tolerancias ni esquemas para que pase.
4. Lee `dist/informe_actualizacion.json`.

## 2. Trimestre nuevo: decisión sobre los supuestos

Solo si `revision_trimestral` es `true`. No valores antes de que el usuario decida.

1. Muestra qué trajo el trimestre: trimestres nuevos, reexpresiones, columnas nuevas y avisos del informe, y las cifras del trimestre frente al anterior, leídas de `data/*.csv`: ingresos por segmento, margen bruto de automoción sin créditos y de energía, margen operativo, FCF, entregas y almacenamiento.
2. Muestra los supuestos vigentes (`data/assumptions.yaml`).
3. Pregunta: ¿mantener los supuestos o revisarlos?
4. **Mantener:** paso 3 con `--mantener-supuestos`.
5. **Revisar:** propón cambios concretos, cada uno justificado con los datos del trimestre, nunca con el precio. El usuario decide cada cambio. Aplica solo lo aprobado, cambia `version` a la fecha de hoy entre comillas y añade la justificación fechada a `docs/metodologia-valoracion.md`. Paso 3 sin `--mantener-supuestos`.

### Hitos (también con trimestre nuevo, tras la decisión sobre los supuestos)

1. Repasa el Update Letter del trimestre y la earnings call contra `data/milestones.yaml`:
   - pasos de los seis hitos prioritarios que se hayan cumplido;
   - fechas nuevas que Tesla o Musk hayan comprometido, ligadas con `paso:` al paso que prometen, o sin `paso` si hablan del hito completo;
   - cambios de estado en el historial;
   - investigaciones de seguridad nuevas o cerradas.
2. Propón cada cambio con fecha, tipo de fuente, fuente y enlace. Si viene de prensa, lleva etiqueta E. Las citas, de menos de 15 palabras. El usuario aprueba cada cambio.
3. Aplica solo lo aprobado y cambia `version` a la fecha de hoy. Comprueba que valida:

   ```bash
   python -c "from src import hitos; hitos.cargar()"
   ```

En cualquier mes, si el usuario lo pide, revisa las novedades de un hito concreto con las mismas reglas.

## 3. Completar

`python -m src.actualizar completar [--mantener-supuestos]`. Si se niega, sigue su mensaje; no lo esquives. Si falla a mitad, el mensaje dice qué quedó escrito: corrige la causa y repite `completar`.

## 4. Revisar y publicar

1. Mira la página construida (`dist/dashboard.html`) **una vez**, sirviéndola en local a ancho de escritorio. Comprueba:
   - consola sin errores;
   - «Simulador verificado» en verde;
   - la cabecera con el precio y el valor de la valoración nueva;
   - el gráfico «Precio frente a valor» con el punto del mes.
2. Si ves algo roto, haz una sola tanda de correcciones, vuelve a construir y publica sin volver a mirar.
3. Republica `dist/dashboard.html` en la URL de arriba.
4. Recuerda al usuario que suba al servidor web, con FileZilla (SFTP), `dist/web/index.html`: la versión completa que genera `construir_dashboard`, sobrescribiendo la anterior. No subas nada tú.
5. Para el servidor local y borra los ficheros temporales que haya dejado la revisión fuera del repositorio.

## 5. Commit

`git add data dist`, más `data/assumptions.yaml` y `docs/metodologia-valoracion.md` si cambiaron. Commit `actualizacion AAAA-MM` con la línea `Co-Authored-By` que corresponda a la sesión.

### Repositorio público de GitHub

`master` es local y nunca se sube: sus commits llevan el correo profesional del usuario. Lo público es la rama `publico`, que se sube como `main` del remoto `origin` con un commit por actualización, firmado con el correo privado de GitHub (`GIT_PUBLIC_EMAIL` y `GIT_PUBLIC_NAME`, en `.env`).

1. Comprueba que nada privado ha entrado en los ficheros. Esta orden no debe devolver nada; si devuelve algo, detente y enséñaselo al usuario:

   ```bash
   git grep -n -I -E "claude\.ai/artifact/[A-Za-z0-9]{10}|[A-Z]:\\\\|@[a-z0-9-]+\.(es|com)\b" -- . ':!tests/fixtures' ':!.env.example'
   ```
2. Prepara el commit público con el árbol de `master`, sin subirlo:

   ```bash
   export GIT_AUTHOR_NAME="$(grep '^GIT_PUBLIC_NAME=' .env | cut -d= -f2- | tr -d '\r')" GIT_AUTHOR_EMAIL="$(grep '^GIT_PUBLIC_EMAIL=' .env | cut -d= -f2- | tr -d '\r')" && export GIT_COMMITTER_NAME="$GIT_AUTHOR_NAME" GIT_COMMITTER_EMAIL="$GIT_AUTHOR_EMAIL" && git branch -f publico "$(git commit-tree 'master^{tree}' -p publico -m 'actualizacion AAAA-MM')"
   ```
3. Pregunta al usuario si lo subes. Solo con su sí: `git push origin publico:main`. Nunca `git push` de `master` ni con `--force`.

## 6. Resumen para el usuario

En español, breve, con esta estructura:

- **Datos nuevos:** trimestres nuevos por fichero, o «ninguno».
- **Reexpresiones:** cuántas y las relevantes (campo, trimestre, antes → después). Los cambios del mes anterior de mercado (`mercado.mes_revisado`) no son reexpresiones: el mes estaba a medias.
- **Mercado:** precio, EUR/USD y tipo sin riesgo frente al mes anterior.
- **Valoración:**
  - valor por acción base, bear y bull frente a la fila anterior del histórico;
  - precio frente a valor;
  - crecimiento implícito;
  - opcionalidad en % de la capitalización;
  - percentil de los múltiplos.
- **Supuestos:** mantenidos, o versión nueva con sus cambios.
- **Hitos:** pasos cumplidos, fechas nuevas y cambios de estado aprobados, o «sin cambios», y el estado de los seis hitos prioritarios.
- **Avisos:** los del informe, o «ninguno».
- **URL** del artifact y recordatorio de subir `dist/web/index.html` al servidor.
