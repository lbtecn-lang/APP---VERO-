# Veronik Sweet — Calculadora de costos + inventario

App web con:
- **Login** con usuario y contraseña propios (una sola cuenta, la de Veronik).
- **Calculadora de costos**: recetas con ingredientes de tu inventario, empaque, trabajo, margen y comisión → precio sugerido en USD **y en Bs a la tasa BCV del día**.
- **Inventario**: tus ingredientes con costo por unidad y alerta de stock bajo.
- **Recetas guardadas**: quedan en base de datos, las puedes reabrir y editar.
- **Tasa BCV automática**: se actualiza sola una vez al día, y también si detecta que la última tasa guardada tiene más de 24h (por si el servicio estuvo apagado).

## 1. Subir el proyecto a GitHub

1. Descomprime este .zip.
2. Crea un repositorio nuevo en GitHub (puede ser privado).
3. Sube el contenido de la carpeta a ese repositorio (arrastrando los archivos en la web de GitHub, o con `git init / git add . / git commit / git push` si usas la terminal).

## 2. Desplegar en Render

**Opción rápida (con el archivo `render.yaml` incluido):**

1. Entra a [render.com](https://render.com) y conecta tu cuenta de GitHub.
2. "New" → "Blueprint" → selecciona el repositorio.
3. Render va a leer `render.yaml` y crear solo:
   - El servicio web (`veronik-sweet-app`).
   - Una base de datos PostgreSQL gratuita (`veronik-sweet-db`), conectada automáticamente.
4. Te va a pedir el valor de `APP_PASSWORD` (la contraseña de Veronik) — escribe la que quieras.
5. Espera a que termine el build (unos 2-3 minutos) y te da la URL pública.

**Opción manual (si prefieres no usar Blueprint):**

1. "New" → "Web Service" → conecta el repo.
2. Build command: `pip install -r requirements.txt`
3. Start command: `gunicorn app:app`
4. En "Environment", agrega estas variables:
   - `SECRET_KEY` → cualquier texto largo y aleatorio
   - `APP_USERNAME` → `veronik` (o el usuario que prefieras)
   - `APP_PASSWORD` → la contraseña que quieras usar
   - `DATABASE_URL` → (ver paso siguiente)
5. Crea aparte una base de datos: "New" → "PostgreSQL" (plan free) → copia su "Internal Connection String" y pégala como `DATABASE_URL` en el servicio web.

⚠️ **Importante:** si no agregas la base de datos PostgreSQL y dejas que la app use SQLite por defecto, en el plan gratuito de Render el disco se borra cada vez que la app se reinicia o se re-despliega — perderías el inventario y las recetas guardadas. Con PostgreSQL conectado, los datos quedan seguros.

## 3. Iniciar sesión

Entra a la URL que te da Render, usa el `APP_USERNAME` y `APP_PASSWORD` que configuraste. Ya puedes cargar tus ingredientes en "Mis ingredientes" y luego armar recetas en la calculadora.

## Sobre la tasa BCV

La app consulta `bcv.today` (con respaldo en `pydolarve.org`) para obtener la tasa oficial del Banco Central de Venezuela. Se guarda en la base de datos y se refresca:
- Automáticamente una vez al día (job programado).
- Al vuelo si la última tasa guardada tiene más de 24 horas.
- Manualmente con el botón "Actualizar" en la calculadora.

## Desarrollo local (opcional)

```bash
python -m venv venv
source venv/bin/activate      # en Windows: venv\Scripts\activate
pip install -r requirements.txt
export APP_USERNAME=veronik
export APP_PASSWORD=tu_clave
python app.py
```

Abre `http://localhost:5000`.
