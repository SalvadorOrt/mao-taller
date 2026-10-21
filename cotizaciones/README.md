# Torre de control de repuestos

Módulo integrado en el ERP MAO, sobre la app `cotizaciones` existente. Reutiliza
`OrdenTrabajo`, sus datos de vehículo/sucursal, `compras.Proveedor`, el catálogo
`Producto`/`CodigoProducto` y el usuario configurado en `AUTH_USER_MODEL`.

## Uso

- Abrir **Compras y abastecimiento → Torre de control**. También hay accesos desde
  el detalle de una OT: **Torre de control** y **Solicitar repuestos**.
- Crear una solicitud para una OT de la sucursal operativa. Una OT puede tener
  varias solicitudes; cada reparación conserva su comparativo e historial.
- Pegar una lista inicial con una línea por repuesto:

  ```text
  Bomba de agua; 1; UNIDAD
  Amortiguadores; 2; UNIDAD
  Pistones; 1; JUEGO; STD
  ```

  La cantidad omitida se propone como 1. Verificarla antes de guardar. Las unidades
  admitidas son UNIDAD, PAR, JUEGO y KIT; pueden quedar por confirmar.
- Agregar o editar repuestos manuales, o vincular productos/códigos del catálogo.
  Especificar cantidad, unidad, medida exacta y cantidad efectivamente cubierta
  desde bodega. El stock general no equivale a una reserva para esta solicitud.
- Registrar cada opción del proveedor: costo por presentación, marca, medida,
  contenido, disponibilidad, IVA y entrega. Un proveedor puede ofrecer varias marcas.
- Elegir una opción por repuesto y **Marcar pedido**. Esta acción registra la compra
  para seguimiento; no envía mensajes ni realiza pedidos en servicios externos.
- Registrar recepciones en la unidad de la solicitud. Las cantidades parciales y el
  pendiente se calculan automáticamente. Anular una recepción equivocada exige
  motivo, conserva el registro y vuelve a abrir la cantidad pendiente.
- Exportar el comparativo a CSV. Incluye los repuestos sin cotización y protege las
  celdas de texto frente a fórmulas de hoja de cálculo.

## Comparación de costos

El total usa presentaciones completas, redondeadas hacia arriba, necesarias para
cubrir `cantidad requerida − cantidad cubierta desde bodega`. Ejemplo: dos unidades
cotizadas a 60 USD el par cubren la solicitud con un par de 60 USD; tres unidades
requieren dos pares de 120 USD. Se suma el IVA cuando está confirmado como adicional,
con redondeo monetario por línea. El importe no incluye transporte u otros cargos;
anotarlos y acordarlos por separado.

El total queda pendiente si falta unidad, conversión, IVA o disponibilidad. Si hay
marca exigida o medida solicitada, la oferta debe coincidir; las medidas requieren
confirmación del técnico. No se convierten STD, +20, 40 u otras medidas técnicas.
Una selección no representa una garantía de compatibilidad: verificar referencia,
vehículo, código de motor y contenido con el técnico/proveedor.

El pedido conserva costo y cantidad acordados. Sus datos de compra y la opción
seleccionada quedan bloqueados para edición; los cambios requieren otro
requerimiento. Las modificaciones previas al pedido conservan el costo anterior
con fecha y usuario. Las operaciones usan bloqueo transaccional de solicitud/ítem,
revisiones para formularios desactualizados y una clave única en cada recepción.

## Alcance de inventario y migración de Sheets

Las recepciones son seguimiento de la solicitud. No generan movimientos de stock,
facturas, asientos ni cambios en los importes de venta de la OT. Esas operaciones
siguen en sus módulos actuales. El contenido de un kit se describe explícitamente;
la cobertura de varias líneas distintas por un mismo kit se concilia manualmente.

Las capturas y tablas históricas no se cargan automáticamente: antes hay que
asociar cada grupo con su OT, aclarar precios laterales, unidades, IVA, colores y
abreviaturas. La lista inicial permite comenzar a cargar solicitudes ya revisadas.
No se han incorporado archivos de clientes ni cotizaciones reales al repositorio.

## Instalación en una copia de desarrollo

Revisar y respaldar la base según el procedimiento habitual del proyecto. Con las
dependencias existentes del ERP (Django 6.0.3):

```bash
python manage.py migrate --plan
python manage.py migrate
python manage.py check
python manage.py collectstatic --noinput
```

La migración valida selecciones históricas duplicadas y costos negativos antes de
modificar las tablas. Conserva solicitudes, proveedores, precios y decisiones
existentes; los nuevos campos de unidad/IVA/medida quedan por confirmar. No supone
fechas históricas nuevas ni sustituye la tabla previa de decisión global.

Los permisos se administran con los roles existentes, en **Cotizaciones de
Proveedores**: ver/crear solicitudes, agregar/editar ítems y cotizaciones,
agregar recepciones y cambiar recepciones para anularlas. Crear un proveedor usa
`compras.add_proveedor`. Leer otra sucursal requiere el permiso de cambio de
sucursal del ERP; operar exige que esa sucursal sea la operativa actual.

Ruta: `/cotizaciones-proveedores/`.

## Validación aislada

```bash
python manage.py test cotizaciones --settings=cotizaciones.test_settings
python manage.py check --settings=cotizaciones.test_settings
python manage.py makemigrations --check --dry-run --settings=cotizaciones.test_settings
```

La configuración de pruebas usa SQLite en memoria, datos ficticios y el usuario
real del proyecto; no importa configuración ni credenciales de producción.
Las migraciones completas se ejecutan durante las pruebas. Las rutas auxiliares
solo evitan cargar vistas de facturación/PDF ajenas a este módulo. El bloqueo de
filas de PostgreSQL requiere validar concurrencia en ese motor antes de habilitar
el módulo a varios operadores en producción.
