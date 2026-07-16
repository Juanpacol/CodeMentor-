# LÓGICA>_

## Plataforma web de lógica de programación

(PSeInt y Python) — INEM José Félix de Restrepo, Medellín

### DOCUMENTO DE REQUERIMIENTOS

Requerimientos para un desarrollo profesional y para la escalabilidad de la plataforma en el tiempo

Julio de 2026

> Este documento es la fuente de verdad de requerimientos del proyecto. El plan de implementación derivado vive en `docs/arquitectura.md` y en el historial de fases del repositorio; cada requerimiento (RF-xx / RE-xx) se referencia desde el código o los ADRs correspondientes.

## 1. Introducción y alcance

Este documento consolida los requerimientos necesarios para llevar el prototipo funcional de "Lógica>_" — una plataforma para que estudiantes se inscriban, practiquen lógica de programación en pseudocódigo (PSeInt) y Python, y presenten evaluaciones, mientras el equipo docente crea contenidos, grupos y hace seguimiento al progreso — a una versión profesional, segura y lista para crecer dentro de la institución y, eventualmente, a otras sedes o instituciones.

El documento se organiza en dos grandes bloques:

- **Requerimientos para una implementación profesional**: lo necesario para que la aplicación sea confiable, segura, usable y mantenible desde el primer despliegue real con estudiantes.

- **Requerimientos de escalabilidad**: lo necesario para que la plataforma soporte el crecimiento en número de usuarios, grupos, contenidos y funcionalidades sin necesidad de reescribirse desde cero.

**Nota**: el prototipo actual (interfaz interactiva con almacenamiento propio de artefactos) es válido para validar la idea con un grupo piloto. Los requerimientos de este documento describen lo necesario para pasar de ese prototipo a un producto institucional.

## 2. Requerimientos funcionales

Funcionalidades que la plataforma debe cubrir, agrupadas por módulo.

### 2.1 Gestión de usuarios y roles

| ID | Requerimiento | Prioridad |
| --- | --- | --- |
| RF-01 | Registro e inicio de sesión seguro para estudiantes y docentes, con verificación de identidad institucional (correo del colegio o código de estudiante). | Alta |
| RF-02 | Roles diferenciados: Estudiante, Docente y Administrador (coordinación académica / TI), cada uno con permisos propios. | Alta |
| RF-03 | Recuperación de contraseña y edición de datos básicos del perfil. | Media |
| RF-04 | Un docente puede administrar varios grupos; un estudiante pertenece a uno o más grupos. | Alta |

### 2.2 Gestión de grupos y contenidos

| ID | Requerimiento | Prioridad |
| --- | --- | --- |
| RF-05 | Creación, edición y archivado de grupos (por grado, jornada o curso). | Alta |
| RF-06 | Inscripción de estudiantes a grupos por código de invitación o carga masiva (CSV) desde el docente. | Alta |
| RF-07 | Creación de temas/unidades con nivel (básico, intermedio, avanzado) y visibilidad por grupo. | Alta |
| RF-08 | Banco de ejercicios reutilizable entre temas y entre periodos académicos. | Media |

### 2.3 Práctica y evaluación

| ID | Requerimiento | Prioridad |
| --- | --- | --- |
| RF-09 | Ejercicios de práctica libre, sin límite de intentos, disponibles fuera del horario de clase. | Alta |
| RF-10 | Tipos de evaluación: verdadero/falso, selección múltiple, completar código, encontrar el error, trazado de variables, ordenar líneas y respuesta argumentada. | Alta |
| RF-11 | Evaluaciones cronometradas con tabla de posiciones (modo competencia). | Media |
| RF-12 | Corrección automática para preguntas objetivas y cola de revisión manual para preguntas abiertas. | Alta |
| RF-13 | Retroalimentación inmediata al estudiante (correcto / incorrecto / pista) tras cada intento. | Alta |

### 2.4 Seguimiento y reportes

| ID | Requerimiento | Prioridad |
| --- | --- | --- |
| RF-14 | Panel de progreso individual (puntos, insignias, temas dominados) visible para el estudiante y su docente. | Alta |
| RF-15 | Panel de progreso grupal con comparativos y alertas de estudiantes rezagados. | Media |
| RF-16 | Exportación de calificaciones y avance a Excel/PDF para boletines o planillas institucionales. | Media |
| RF-17 | Historial de intentos y evaluaciones consultable por periodo académico. | Media |

### 2.5 Control de alcance de contenidos y evaluaciones

El docente debe poder decidir, en todo momento, qué contenidos están habilitados para cada grupo y hasta qué punto del temario cubre cada evaluación — igual que definiría el alcance de un examen en clase.

Esto resuelve un punto clave solicitado: el docente conserva siempre el control sobre qué se trabaja y hasta dónde evalúa, y la plataforma nunca avanza contenido por su cuenta ni evalúa temas que el estudiante todavía no ha visto en clase.

| ID | Requerimiento | Prioridad |
| --- | --- | --- |
| RF-18 | El docente puede activar o desactivar cada tema por grupo de forma independiente, controlando qué ve el estudiante y cuándo. | Alta |
| RF-19 | El docente puede definir un orden/secuencia curricular de los temas (unidad 1, 2, 3…) y el estudiante avanza siguiendo ese orden sugerido. | Alta |
| RF-20 | Al crear una evaluación, el docente elige explícitamente "hasta qué tema o unidad" llega la evaluación; el sistema solo permite seleccionar ejercicios de los temas incluidos en ese rango. | Alta |
| RF-21 | Opción de evaluación "acumulativa": incluye automáticamente ejercicios de todos los temas habilitados hasta la fecha, sin que el docente tenga que marcarlos uno por uno. | Media |
| RF-22 | Los estudiantes solo pueden practicar o presentar evaluaciones de los temas ya habilitados por su docente; el contenido no habilitado permanece bloqueado (visible como "próximamente" o ni siquiera visible, según configuración). | Alta |
| RF-23 | Vista de "línea de tiempo curricular" para el docente: cronograma visual del temario con el estado de cada tema (bloqueado, habilitado, evaluado) y la fecha en que se habilitó. | Media |
| RF-24 | Posibilidad de programar la habilitación automática de un tema en una fecha futura (por ejemplo, para que coincida con el avance real de la clase presencial). | Baja |

### 2.6 Soporte multilenguaje de programación

Aunque el punto de partida es la lógica de programación en pseudocódigo (PSeInt) y Python, la plataforma debe diseñarse desde ya para enseñar y evaluar otros lenguajes usados en cursos posteriores o en articulación con educación media técnica.

Este requerimiento se apoya en la arquitectura de "motor de ejercicios por lenguaje" descrita en la sección 5.2 (RE-05 y RE-06): agregar C, C++, Java o PHP no debería exigir reescribir el sistema, sino registrar un nuevo lenguaje con sus reglas de resaltado y, si aplica, su entorno de ejecución aislado (sandbox) para retos de código en vivo.

| ID | Requerimiento | Prioridad |
| --- | --- | --- |
| RF-25 | Cada tema y cada ejercicio se etiqueta con un lenguaje (PSeInt, Python, C, C++, Java, PHP, u otro que se agregue) tomado de una lista configurable por el docente o administrador, no fija en el código de la aplicación. | Alta |
| RF-26 | El editor y las vistas de código aplican resaltado de sintaxis propio de cada lenguaje seleccionado (palabras clave, tipos de dato, comentarios) para que el estudiante reconozca la sintaxis real que usará en el aula. | Alta |
| RF-27 | El estudiante puede filtrar "Practicar" y "Evaluaciones" por lenguaje, para reforzar un lenguaje específico sin mezclarlo con otros que esté viendo en paralelo. | Media |
| RF-28 | Para ejercicios de "encontrar el error" o "trazado de variables" en lenguajes compilados (C, C++, Java), el docente puede indicar si el error es de sintaxis, de lógica o de tipos, ya que estos lenguajes distinguen claramente esos casos frente a Python o PSeInt. | Media |
| RF-29 | El progreso del estudiante (puntos, insignias, dominio de temas) se registra por lenguaje, de modo que el reporte muestre, por ejemplo, avance en "Lógica con PSeInt" por separado de "Fundamentos de Java". | Media |

## 3. Requerimientos no funcionales (calidad profesional)

Condiciones de calidad que debe cumplir la plataforma para ser considerada un producto profesional, no solo un prototipo funcional.

### 3.1 Usabilidad y accesibilidad

- **Interfaz responsiva**: debe funcionar correctamente en computadores de sala de sistemas, tablets y celulares de gama media (realidad de muchos estudiantes).

- **Cumplimiento de pautas de accesibilidad WCAG 2.1 AA**: contraste de color adecuado, navegación por teclado, textos alternativos en imágenes.

- **Lenguaje 100% en español**, con las convenciones de PSeInt respetadas tal como el docente las enseña en clase.

- **Tiempo de carga inicial menor a 3 segundos** en conexión 4G promedio.

### 3.2 Rendimiento y disponibilidad

- **Disponibilidad objetivo de 99.5%** durante el calendario escolar (excluye vacaciones).

- **Capacidad de soportar el uso simultáneo** de al menos un curso completo (35–40 estudiantes) en una evaluación cronometrada sin degradación perceptible.

- **Tiempo de respuesta** menor a 500 ms para operaciones de lectura (ver temas, ver progreso) y menor a 1.5 s para operaciones de escritura (guardar respuesta).

### 3.3 Mantenibilidad

- **Código fuente versionado** en un repositorio Git con historial de cambios y convenciones de commits.

- **Separación clara** entre frontend, backend y base de datos (arquitectura en capas) para permitir que distintos desarrolladores trabajen en paralelo.

- **Documentación técnica mínima**: diagrama de arquitectura, diccionario de datos y guía de despliegue.

- **Pruebas automatizadas** para la lógica de calificación (el componente más sensible a errores silenciosos).

### 3.4 Compatibilidad y soporte

- **Compatibilidad** con los navegadores más usados en salas de sistemas públicas (Chrome, Edge, Firefox) en sus últimas dos versiones mayores.

- **Funcionamiento aceptable** con ancho de banda limitado y de forma intermitente (conectividad típica de sedes públicas).

## 4. Arquitectura técnica recomendada

Para pasar del prototipo a producción se recomienda una arquitectura cliente-servidor desacoplada:

### 4.1 Frontend

- Framework de componentes (por ejemplo React) con enrutamiento propio para cada módulo (Grupos, Temas, Ejercicios, Evaluaciones, Progreso).

- Editor de código embebido con resaltado de sintaxis para PSeInt y Python (por ejemplo CodeMirror o Monaco Editor).

- Diseño de componentes reutilizables (biblioteca de UI propia) para mantener consistencia visual al agregar nuevos tipos de ejercicio.

### 4.2 Backend y API

- API REST o GraphQL propia, documentada (OpenAPI/Swagger), que exponga los recursos: usuarios, grupos, temas, ejercicios, evaluaciones y progreso.

- Autenticación basada en tokens (JWT) con expiración y renovación, y autorización por rol en cada endpoint.

- Servicio de calificación desacoplado: recibe una respuesta y un ejercicio, y devuelve un resultado — facilita agregar nuevos tipos de pregunta sin tocar el resto del sistema.

- Para el reto de "código en vivo" (retos cronometrados con ejecución de Python real) se recomienda un servicio aislado de ejecución de código en un entorno restringido (sandbox), nunca ejecución directa en el servidor principal.

### 4.3 Base de datos

- Motor relacional (PostgreSQL o MySQL) como fuente principal de verdad: garantiza integridad entre usuarios, grupos, ejercicios y calificaciones.

- Modelo de datos normalizado, con llaves foráneas explícitas entre estudiante, grupo, tema, ejercicio y resultado (a diferencia del almacenamiento clave-valor del prototipo).

- Índices sobre las columnas de consulta frecuente: usuario, grupo y fecha de evaluación.

### 4.4 Infraestructura y despliegue

- Alojamiento en la nube (por ejemplo un proveedor con presencia en Latinoamérica) con entornos separados de desarrollo, pruebas y producción.

- Copias de seguridad automáticas diarias de la base de datos, con retención mínima de 30 días.

- Integración y despliegue continuos (CI/CD): cada cambio pasa por pruebas automáticas antes de llegar a producción.

- Monitoreo de errores y de disponibilidad con alertas al equipo responsable (por ejemplo Sentry, UptimeRobot o equivalente).

## 5. Requerimientos de escalabilidad

Estos requerimientos garantizan que la plataforma pueda crecer — en número de estudiantes, sedes, contenidos y tipos de evaluación — sin degradar el servicio ni obligar a reescribir el sistema.

### 5.1 Escalabilidad de usuarios y carga

| ID | Requerimiento | Beneficio a futuro |
| --- | --- | --- |
| RE-01 | Arquitectura sin estado (stateless) en el backend, permitiendo añadir más instancias del servidor detrás de un balanceador de carga. | Soporta más colegios o sedes sin rediseñar el sistema. |
| RE-02 | Uso de caché (por ejemplo Redis) para contenidos de lectura frecuente: temas, ejercicios y tablas de posiciones. | Reduce carga a la base de datos en horas pico (ej. toda una jornada evaluando a la vez). |
| RE-03 | Cola de trabajos asíncrona para tareas pesadas: envío de reportes, cálculo de rankings, exportaciones. | Evita que operaciones lentas bloqueen la experiencia de otros usuarios. |
| RE-04 | Particionamiento lógico de datos por institución (multi-tenant), aun si hoy solo hay una sede. | Permite ofrecer la plataforma a otras instituciones públicas sin mezclar su información. |

### 5.2 Escalabilidad de contenidos y funcionalidades

| ID | Requerimiento | Beneficio a futuro |
| --- | --- | --- |
| RE-05 | Los tipos de ejercicio se modelan como "plugins" con una interfaz común (recibir respuesta, devolver calificación). | Permite agregar nuevos tipos de evaluación (ej. diagramas de flujo, retos por parejas) sin modificar el motor existente. |
| RE-06 | Soporte planeado para más lenguajes además de PSeInt y Python — C, C++, Java, PHP y otros que la institución requiera — mediante el mismo motor de ejercicios, cada uno con su propio resaltado de sintaxis y, si aplica, entorno de ejecución aislado (sandbox) por lenguaje. | Prepara la plataforma para cursos técnicos, media técnica y articulación con el SENA u otras instituciones. |
| RE-07 | Versionado de contenidos (temas y ejercicios) para que un cambio de un docente no afecte evaluaciones ya presentadas por otros grupos. | Permite reutilizar y mejorar contenido de un año a otro con trazabilidad. |

### 5.3 Escalabilidad organizacional

- Panel de administración institucional que permita crear nuevas sedes, jornadas o incluso otras instituciones (Secretaría de Educación) sin intervención de un desarrollador.

- Roles adicionales previstos desde el diseño: coordinador académico (ve todos los grupos de la sede) y administrador de la Secretaría de Educación (ve indicadores agregados entre instituciones).

- API abierta y documentada para integraciones futuras con el Sistema Integrado de Matrícula (SIMAT) u otras plataformas del Ministerio de Educación.

## 6. Seguridad y protección de datos

Al tratarse de una aplicación usada por menores de edad en una institución pública, este bloque tiene prioridad máxima.

- **Cumplimiento de la Ley 1581 de 2012 (Habeas Data)** y el Decreto 1377 de 2013 de Colombia sobre tratamiento de datos personales, incluyendo el de menores de edad.

- **Consentimiento informado** de acudientes para el tratamiento de datos de estudiantes menores de edad, gestionado por la institución antes del uso de la plataforma.

- **Cifrado de contraseñas** (hash con sal) y cifrado en tránsito (HTTPS/TLS) en toda la aplicación.

- **Principio de mínimo privilegio**: un estudiante solo puede ver y modificar su propia información; un docente solo accede a los grupos que administra.

- **Registro de auditoría** (quién hizo qué y cuándo) para acciones sensibles: cambios de calificación, eliminación de datos, cambios de rol.

- **Política de retención y eliminación de datos** al finalizar el año escolar o el retiro de un estudiante de la institución.

## 7. Hoja de ruta sugerida

| Fase | Objetivo | Duración estimada |
| --- | --- | --- |
| 1. Piloto | Validar la plataforma actual con uno o dos grupos, recoger retroalimentación de estudiantes y docentes. | 4–6 semanas |
| 2. Migración a arquitectura profesional | Backend con base de datos relacional, autenticación segura y despliegue en la nube con entornos separados. | 2–3 meses |
| 3. Consolidación institucional | Roles adicionales, reportes para coordinación, copias de seguridad y monitoreo en producción. | 1–2 meses |
| 4. Escalamiento | Multi-sede o multi-institución, caché y balanceo de carga, nuevos tipos de ejercicio y lenguajes. | Continuo |

## 8. Recomendaciones para una implementación de calidad profesional

Además de los requerimientos anteriores, estas recomendaciones prácticas marcan la diferencia entre un sistema que funciona y un producto que la institución adopta con confianza y lo sostiene en el tiempo.

### 8.1 Proceso y metodología

- Trabajar por ciclos cortos (metodología ágil tipo Scrum/Kanban de 2 semanas), con el docente como "dueño del producto": prioriza qué se construye primero según lo que más falta en el aula.

- Empezar siempre por un piloto acotado (un grupo, un tema) antes de habilitar la plataforma a todo el colegio; corregir con datos reales antes de escalar.

- Definir criterios de "listo para producción" antes de cada entrega: sin errores críticos, probado en al menos dos navegadores y un celular gama media.

### 8.2 Calidad y pruebas

- Incluir pruebas de aceptación con estudiantes reales antes de cada lanzamiento importante (por ejemplo, 3-5 estudiantes de distintos niveles probando la misma evaluación).

- Revisar cada tipo de ejercicio con un "caso borde": respuesta vacía, doble clic en enviar, pérdida de conexión a mitad de una evaluación cronometrada — estos son los momentos donde un sistema educativo pierde la confianza del usuario.

- Mantener un ambiente de pruebas idéntico a producción para validar cambios sin arriesgar la información real de los estudiantes.

### 8.3 Documentación, capacitación y soporte

- Elaborar un manual breve para docentes (crear grupo, habilitar tema, armar evaluación) y uno para estudiantes (cómo practicar y presentar evaluaciones), en lenguaje simple y con capturas de pantalla.

- Realizar una sesión de inducción con el equipo docente del área de tecnología antes del primer uso masivo.

- Definir un canal claro de soporte (correo, WhatsApp institucional o formulario) y un tiempo de respuesta esperado ante fallos, especialmente en semanas de evaluación.

### 8.4 Gobernanza, ética y sostenibilidad

- Validar el tratamiento de datos de menores con la coordinación/rectoría y, si es posible, con la oficina jurídica de la Secretaría de Educación de Medellín antes del despliegue institucional.

- Ser transparente con estudiantes y acudientes sobre qué datos se recogen (progreso académico) y qué datos NO se recogen (no se usan cámaras, ubicación ni datos sensibles).

- Planear la sostenibilidad técnica más allá de un solo docente o desarrollador: documentar el proyecto para que pueda mantenerlo otra persona (por ejemplo, un semillero de investigación o estudiantes de último grado como monitores técnicos).

- Explorar alianzas de bajo costo o gratuitas para hosting educativo (por ejemplo programas para instituciones públicas o educativas de distintos proveedores de nube) antes de asumir costos comerciales plenos.

### 8.5 Mejora continua

- Recoger retroalimentación de estudiantes y docentes al cierre de cada periodo académico (encuesta corta de 3-4 preguntas) y usarla para priorizar el siguiente ciclo de desarrollo.

- Medir el uso real (temas más practicados, tipos de ejercicio con más error) para ajustar contenidos y detectar dificultades comunes de aprendizaje, no solo fallas técnicas.

## 9. Integración de Inteligencia Artificial: harness, agentes, skills y AI Engineering

La plataforma puede evolucionar de un sistema de ejercicios y evaluaciones a un entorno que asiste tanto al estudiante como al docente mediante inteligencia artificial. Esta sección define cómo incorporar esas capacidades de forma controlada, auditable y segura para menores de edad — sin que la IA reemplace el criterio pedagógico del docente.

### 9.1 Qué es un "harness" de IA y por qué lo necesita el proyecto

Un "harness" de IA es la capa intermedia entre la aplicación y los modelos de lenguaje: no se llama al modelo directamente desde cualquier parte del código, sino a través de un servicio propio que controla qué se le envía, qué se le permite responder y qué se hace con la respuesta. Para este proyecto, el harness debe encargarse de:

- **Enrutamiento de modelos**: elegir el modelo adecuado según la tarea (uno económico y rápido para pistas cortas, uno más capaz para generar ejercicios nuevos), con un modelo de respaldo si el principal falla.

- **Plantillas de prompt versionadas**: cada tipo de interacción (dar una pista, sugerir una calificación, generar un ejercicio) tiene una plantilla propia, guardada en control de versiones igual que el código.

- **Guardrails (barreras de seguridad)**: reglas que filtran la entrada y la salida — el agente nunca entrega la respuesta completa de una evaluación, nunca genera contenido inapropiado para menores, y rechaza instrucciones que intenten manipularlo ("inyección de prompt").

- **Registro y trazabilidad**: cada interacción con IA queda registrada (quién la solicitó, qué modelo respondió, qué costó, si fue aprobada por el docente) para poder auditar el uso.

- **Control de costos**: límites de uso por estudiante y por día, y caché de respuestas frecuentes para no pagar dos veces por la misma pista.

### 9.2 Agentes de IA propuestos para la plataforma

Principio guía: ningún agente decide una nota final, bloquea a un estudiante o publica contenido nuevo sin que un docente lo apruebe. La IA asiste; el docente decide.

| Agente | Función | Supervisión requerida |
| --- | --- | --- |
| Agente Tutor | Da pistas progresivas a un estudiante atascado en un ejercicio, sin revelar la respuesta directa; escala el nivel de ayuda solo si el estudiante sigue fallando. | Ninguna en tiempo real; el docente revisa el historial de pistas por muestreo. |
| Agente Generador de ejercicios | A partir de un tema y nivel, propone nuevos ejercicios (de cualquiera de los tipos ya definidos) para que el docente los revise antes de publicarlos. | Obligatoria: el ejercicio queda en borrador hasta aprobación docente. |
| Agente Asistente de calificación | Para respuestas abiertas (tipo "argumentar"), sugiere un puntaje y una justificación con base en la rúbrica del docente. | Obligatoria: es solo una sugerencia; el docente decide y puede corregirla. |
| Agente de analítica de aprendizaje | Detecta patrones de error frecuentes en un grupo (ej. confusión entre Mientras y Para) y sugiere al docente qué reforzar. | Informativa; no actúa sobre calificaciones ni contenido por sí solo. |
| Agente de integridad de código | En retos de código en vivo, revisa si una solución tiene patrones típicos de copiar/pegar o generación automática, como apoyo (no como prueba definitiva) para el docente. | El resultado es una alerta, nunca una sanción automática. |

### 9.3 Skills: capacidades modulares y reutilizables

En lugar de construir un solo asistente que "sepa hacer de todo", se recomienda definir "skills": unidades pequeñas, documentadas y probadas de forma independiente, cada una con una entrada y una salida claras, que los agentes combinan según la tarea. Por ejemplo:

- **Skill "validar sintaxis PSeInt"**: recibe un bloque de pseudocódigo y devuelve si es sintácticamente válido y en qué línea está el error, si existe.

- **Skill "ejecutar código en sandbox"**: ejecuta Python, C, C++, Java o PHP en un entorno aislado y devuelve la salida o el error, usada tanto por el motor de calificación como por el agente tutor.

- **Skill "generar pista progresiva"**: recibe el ejercicio, la respuesta del estudiante y el número de intentos, y devuelve una pista cada vez más específica (nunca la solución completa en el primer intento).

- **Skill "redactar retroalimentación pedagógica"**: convierte un resultado técnico (correcto/incorrecto, línea de error) en una explicación en español, clara y respetuosa, adecuada para adolescentes.

- **Skill "resumir progreso de un grupo"**: produce, para el docente, un resumen breve del avance y las dificultades más comunes de un grupo en un periodo.

Diseñar así el sistema permite auditar, probar y mejorar cada capacidad por separado, y reutilizarla en distintos agentes sin duplicar lógica — el mismo principio de los "plugins" de contenido ya definido en la sección 5.2.

### 9.4 Prácticas de AI Engineering para el proyecto

- **Evaluaciones automatizadas ("evals")**: antes de publicar un cambio en un prompt o de cambiar de modelo, correr un conjunto de casos de prueba (ej. 30 ejercicios conocidos) y verificar que las pistas y calificaciones sugeridas sigan siendo adecuadas.

- **Observabilidad dedicada**: panel de monitoreo con latencia, tasa de error, costo por interacción y volumen de uso por agente, separado del monitoreo general de la aplicación (sección 4.4).

- **Gestión de prompts como código**: versionado en el mismo repositorio Git, con revisión de pares antes de cambiar el comportamiento de un agente que interactúa con menores.

- **Minimización de datos personales**: al enviar información a un proveedor de IA externo, no incluir nombre completo, número de documento ni otros datos identificables del estudiante; usar identificadores internos anónimos.

- **Estrategia de proveedor**: evaluar entre uso de una API de modelos de terceros, un modelo más pequeño autoalojado para tareas simples (más económico y con más control de datos), o una combinación de ambos según la sensibilidad de cada tarea.

- **Plan de contingencia sin IA**: toda funcionalidad basada en IA debe tener una alternativa manual (el docente sigue pudiendo crear ejercicios y calificar sin el agente) para que un fallo del proveedor de IA nunca detenga la clase.

### 9.5 Nuevos requerimientos funcionales de IA

| ID | Requerimiento | Prioridad |
| --- | --- | --- |
| RF-30 | El docente puede activar o desactivar cada agente de IA (tutor, generador, calificación asistida, analítica) de forma independiente y por grupo. | Alta |
| RF-31 | El Agente Tutor entrega pistas progresivas y nunca la respuesta completa de un ejercicio activo en una evaluación en curso. | Alta |
| RF-32 | Todo ejercicio generado por IA queda en estado "borrador" y no es visible para estudiantes hasta que un docente lo aprueba o edita. | Alta |
| RF-33 | Toda calificación sugerida por IA para respuestas abiertas requiere confirmación explícita del docente antes de afectar el puntaje del estudiante. | Alta |
| RF-34 | Se registra un historial auditable de cada interacción con un agente de IA (fecha, usuario, agente, resumen de la respuesta y si fue aprobada). | Alta |
| RF-35 | El estudiante puede ver claramente cuándo está interactuando con un agente de IA (identificado como tal) y no con su docente. | Alta |

### 9.6 Lineamientos de diseño para un panel de IA (inspirado en dashboards de IA/SaaS actuales)

Para la interfaz donde el docente supervisa a los agentes (aprobar ejercicios, revisar calificaciones sugeridas, ver el estado de cada agente), se recomienda seguir el lenguaje visual que hoy predomina en los dashboards de productos de IA: fondo oscuro con acentos de color vivos, tarjetas de métricas compactas, indicadores de estado en tiempo real y un panel de conversación con el agente. Concretamente:

- **Tarjetas de estado por agente** (activo/inactivo, último uso, número de sugerencias pendientes) en la parte superior del panel, como resumen inmediato.

- **Una bandeja de "pendientes de aprobación" unificada**: ejercicios generados y calificaciones sugeridas en una sola cola, para que el docente revise todo en un solo lugar en lugar de buscar en cada módulo.

- **Indicadores visuales claros** de "contenido generado por IA" (una etiqueta o color distintivo) frente a "contenido creado por el docente", en toda la plataforma, no solo en el panel de administración.

- **Un historial de conversación tipo chat** para el Agente Tutor, visible para el estudiante y consultable por el docente, coherente con el estilo conversacional de los asistentes de IA actuales.

- **Gráficas simples de tendencia** (uso de cada agente por semana, tasa de aprobación de sugerencias) para que el docente y la coordinación evalúen si vale la pena mantener cada agente activo.

**Referencia de estilo**: colecciones actuales de dashboards de IA/SaaS (por ejemplo, en Dribbble bajo la etiqueta "ai-saas-dashboard") muestran consistentemente esta combinación de tema oscuro, tarjetas de métricas y paneles conversacionales — es un lenguaje visual ya familiar para los estudiantes y transmite confianza en un producto que usa IA de forma responsable. No se debe copiar ni reproducir diseños de terceros; se recomienda usarlos solo como referencia de estilo general al construir un sistema de diseño propio.

## 10. Conclusión

Adoptar estos requerimientos permite que la plataforma pase de ser un prototipo de validación a una herramienta institucional confiable: seria en el manejo de los datos de los estudiantes, estable durante el uso simultáneo de un curso completo, y preparada para crecer — en contenidos, tipos de evaluación y número de sedes — sin necesidad de reconstruirse desde cero en cada etapa. Con el control de alcance de contenidos y evaluaciones (sección 2.5) y las recomendaciones de calidad profesional (sección 8), el docente conserva siempre el timón pedagógico: la tecnología acompaña el ritmo real de la clase, nunca lo reemplaza ni se adelanta a él.
