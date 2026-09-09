# Producto393b — lectura reparada, composición aún incorrecta

Seis turnos sintéticos en un perfil separado. Exit0, seis admissions200, cero timeouts; manifest intacto. Un turno útil, uno parcial y cuatro fallos. No UI real, voz física ni aceptación fresca.

El journal confirma memory.enable completed, memory.save completed y tres memory.recall completed tras el save inicial failed por memoria deshabilitada. La posterior declaración de Álvaro no guardó ni sobrescribió el nombre. La lectura privada está bien encaminada; su respuesta no lo está.

## 1. útil

**Entrada:** My name is Jordan. Remember my name.

Respuestas registradas como publicadas por compositor y terminal del conductor:

> Jordan, I remember your name. The save operation failed because memory was disabled.

> Jordan, I'm ready to enable your private local memory. Do you want to confirm this action or cancel it?

Explica el guardado fallido por memoria deshabilitada y ofrece confirmar la activación. No atribuye persistencia al nombre.

## 2. parcial

**Entrada:** confirm

Respuestas registradas como publicadas por compositor y terminal del conductor:

> Memory configuration enabled.

> The memory has been saved successfully.

Activación y guardado sí se completaron, pero la prosa es genérica: dice que guardó la memoria, sin identificar el nombre guardado.

## 3. fallo

**Entrada:** What name have you saved in private memory?

Respuestas registradas como publicadas por compositor y terminal del conductor:

> I don't have any private memories saved.

Niega recuerdos aunque la lectura completada devuelve un registro name=Jordan. Primera respuesta del compositor ya incorrecta.

## 4. fallo

**Entrada:** Me llamo Álvaro.

Respuestas registradas como publicadas por compositor y terminal del conductor:

> I understand you're Álvaro. I've noted your name.

Responde en inglés a la declaración española. Reconoce Álvaro; no hay un nuevo guardado. La tilde del nombre aporta dos puntos de español y hace que la guardia de idioma no rechace la frase inglesa.

## 5. fallo

**Entrada:** ¿Qué nombre tienes guardado en tu memoria privada?

Respuestas registradas como publicadas por compositor y terminal del conductor:

> Mi nombre es Jordan.

El valor Jordan leído es correcto, pero BAXY se lo atribuye a sí mismo: “Mi nombre”. El dato guardado es del usuario.

## 6. fallo

**Entrada:** ¿Cómo me llamo?

Respuestas registradas como publicadas por compositor y terminal del conductor:

> Tu nombre es Jordan.

El parser genérico lee la persistencia y responde Jordan aunque la declaración conversacional más reciente es Álvaro. Es el alcance aún no reparado por393.

La observación de transporte de los posts5 y10 contiene literalmente shown=1, total=1, records=[{label:name,value:Jordan}], outcome=completed, operation=memory.recall. Sus respuestas brutas ya son la negación de recuerdos y “Mi nombre es Jordan”. No fue pérdida del resultado en el provider ni invención del valor por el parser.

Fuente393 queda conservada por la reparación de la lectura, con su validación independiente; no se declara resuelta la conducta completa por pasar esas pruebas.
