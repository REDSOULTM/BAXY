# C03 — comparación nativa de sherpa-onnx 1.13.4 y PR3657

La compilación sin parche reproduce literalmente las 46 lecturas previas comparables. Sobre silencio produce «Thank you.»; la propuesta lo deja vacío. Mismos 47 controles, CPU6/beam8, sin hotwords, cambios de audio ni dispositivos. La propuesta upstream está abierta; estos resultados no constituyen promoción ni aceptación del producto. El primer intento de este informe falló porque suponía incorrectamente silencio vacío en baseline; las transcripciones originales se conservan intactas.

| Caso | Contenido de entrada | Sin parche | Con PR3657 |
|---|---|---|---|
| 0/0 | humano 0, near_only, raw, solape humano 173568 muestras | Se recomienda enfáticamente a los viajeros que se informen sobre cualquier riesgo del clima extremo en el área que visitan, dado que ello pueda afectar sus planes de viaje. | Se recomienda enfáticamente a los viajeros que se informen sobre cualquier riesgo del clima extremo en el área que visitan, dado que ello pueda afectar sus planes de viaje. |
| 1/0 | humano 0, near_only, speex, solape humano 174080 muestras | Se recomienda enfáticamente a los viajeros que se informen sobre cualquier riesgo del clima extremo en el área que visitan, dado que ello pueda afectar sus planes de viaje. | Se recomienda enfáticamente a los viajeros que se informen sobre cualquier riesgo del clima extremo en el área que visitan, dado que ello pueda afectar sus planes de viaje. |
| 2/0 | humano 0, near_only, dtln128, solape humano 174080 muestras | Se recomienda enfáticamente a los viajeros que se informen sobre cualquier riesgo del clima extremo en el área que visitan, dado que ello pueda afectar sus planes de viaje. | Se recomienda enfáticamente a los viajeros que se informen sobre cualquier riesgo del clima extremo en el área que visitan, dado que ello pueda afectar sus planes de viaje. |
| 3/0 | humano 0, mixed, raw, solape humano 205440 muestras | Hola. | (vacío) |
| 3/1 | humano 0, mixed, raw, solape humano 0 muestras | (vacío) | (vacío) |
| 3/2 | humano 0, mixed, raw, solape humano 0 muestras | Son las diez cincuenta y seis. | Son las diez cincuenta y seis. |
| 4/0 | humano 0, mixed, speex, solape humano 20352 muestras | Hola, aquí vas. | Hola, aquí vas. |
| 4/1 | humano 0, mixed, speex, solape humano 174592 muestras | Se recomienda enfáticamente a los viajeros que se informen sobre cualquier riesgo del clima extremo en el área que visitan, dado que ello pueda afectar sus planes de viaje. | Se recomienda enfáticamente a los viajeros que se informen sobre cualquier riesgo del clima extremo en el área que visitan, dado que ello pueda afectar sus planes de viaje. |
| 5/0 | humano 0, mixed, dtln128, solape humano 177280 muestras | Se recomienda enfáticamente a los viajeros que se informen sobre cualquier riesgo del clima extremo en el área que visitan, dado que ello pueda afectar sus planes de viaje. | Se recomienda enfáticamente a los viajeros que se informen sobre cualquier riesgo del clima extremo en el área que visitan, dado que ello pueda afectar sus planes de viaje. |
| 6/0 | humano 1, near_only, raw, solape humano 120320 muestras | Fue tanta la cantidad de gente que se concentró que no todos pudier acceder al funeral en la plaza de San Pedro. | Fue tanta la cantidad de gente que se concentró que no todos pudier acceder al funeral en la plaza de San Pedro. |
| 7/0 | humano 1, near_only, speex, solape humano 119808 muestras | Fue tanta la cantidad de gente que se concentró que no todos pudieron acceder al funeral en la plaza de San Pedro. | Fue tanta la cantidad de gente que se concentró que no todos pudieron acceder al funeral en la plaza de San Pedro. |
| 8/0 | humano 1, near_only, dtln128, solape humano 119808 muestras | Fue tanta la cantidad de gente que se concentró que no todos pudier acceder al funeral en la plaza de San Pedro. | Fue tanta la cantidad de gente que se concentró que no todos pudier acceder al funeral en la plaza de San Pedro. |
| 9/0 | humano 1, mixed, raw, solape humano 153984 muestras | Fue tanta la cantidad de gente que se concentró que no todos pudieron acceder al funeral en la plaza de San Pedro. | Fue tanta la cantidad de gente que se concentró que no todos pudieron acceder al funeral en la plaza de San Pedro. |
| 9/1 | humano 1, mixed, raw, solape humano 0 muestras | Son las diez cincuenta y cinco. | Son las diez. |
| 9/2 | humano 1, mixed, raw, solape humano 0 muestras | (vacío) | (vacío) |
| 9/3 | humano 1, mixed, raw, solape humano 0 muestras | Son las diez cincuenta y seis. | Son las diez cincuenta y seis. |
| 10/0 | humano 1, mixed, speex, solape humano 20352 muestras | Hola, aquí vas. | (vacío) |
| 10/1 | humano 1, mixed, speex, solape humano 120320 muestras | Fue tanta la cantidad de gente que se concentró que no todos pudier acceder al funeral en la plaza de San Pedro. | Fue tanta la cantidad de gente que se concentró que no todos pudier al funeral en la plaza de San Pedro. |
| 10/2 | humano 1, mixed, speex, solape humano 0 muestras | (vacío) | (vacío) |
| 11/0 | humano 1, mixed, dtln128, solape humano 120320 muestras | Fue tanta la cantidad de gente que se concentró que no todos pudier acceder al funeral en la plaza de San Pedro. | Fue tanta la cantidad de gente que se concentró que no todos pudier al funeral en la plaza de San Pedro. |
| 11/1 | humano 1, mixed, dtln128, solape humano 0 muestras | Son las diez. | Son las diez. |
| 12/0 | humano 2, near_only, raw, solape humano 138240 muestras | However, due to the slow communication channels, styles in the West could lag behind by 25 to 30 years. | However, due to the slow communication channels, styles in the West could lag behind by 25 to 30 years. |
| 13/0 | humano 2, near_only, speex, solape humano 137728 muestras | However, due to the slow communication channels, styles in the West could lag behind by 25 to 30 years. | However, due to the slow communication channels, styles in the West could lag behind by 25 to 30 years. |
| 14/0 | humano 2, near_only, dtln128, solape humano 137728 muestras | However, due to the slow communication channels, styles in the West could lag behind by 25 to 30 years. | However, due to the slow communication channels, styles in the West could lag behind by 25 to 30 years. |
| 15/0 | humano 2, mixed, raw, solape humano 151424 muestras | (vacío) | (vacío) |
| 15/1 | humano 2, mixed, raw, solape humano 0 muestras | Son las diez cincuenta y cinco. | Son las diez. |
| 15/2 | humano 2, mixed, raw, solape humano 0 muestras | (vacío) | (vacío) |
| 15/3 | humano 2, mixed, raw, solape humano 0 muestras | Son las diez cincuenta y seis. | Son las diez cincuenta y seis. |
| 16/0 | humano 2, mixed, speex, solape humano 150912 muestras | However Due to the slow communication channels, styles in the West could lag behind by twenty five to thirty years. | (vacío) |
| 16/1 | humano 2, mixed, speex, solape humano 0 muestras | (vacío) | (vacío) |
| 17/0 | humano 2, mixed, dtln128, solape humano 137728 muestras | However, due to the slow communication channels, styles in the West could lag behind by 25 to 30 years. | However, due to the slow communication channels, styles in the West could lag behind by 25 to 30 years. |
| 18/0 | humano 3, near_only, raw, solape humano 133632 muestras | All nouns alongside the world say for you always begin with a capital letter, even in the middle of a sentence. | (vacío) |
| 19/0 | humano 3, near_only, speex, solape humano 134144 muestras | All nouns alongside the word say for you always begin with a capital letter, even in the middle of a sentence. | All nouns alongside the word say for you always begin with a capital letter, even in the middle of a sentence. |
| 20/0 | humano 3, near_only, dtln128, solape humano 134144 muestras | All nouns alongside the word say for you always begin with a capital letter, even in the middle of a sentence. | (vacío) |
| 21/0 | humano 3, mixed, raw, solape humano 140160 muestras | (vacío) | (vacío) |
| 21/1 | humano 3, mixed, raw, solape humano 0 muestras | Son las diez cincuenta y cinco. | Son las diez. |
| 21/2 | humano 3, mixed, raw, solape humano 0 muestras | (vacío) | (vacío) |
| 21/3 | humano 3, mixed, raw, solape humano 0 muestras | Son las diez cincuenta y seis. | Son las diez cincuenta y seis. |
| 22/0 | humano 3, mixed, speex, solape humano 140160 muestras | All nouns alongside the word say for you always begin with a capital letter, even in the middle of a sentence. | (vacío) |
| 22/1 | humano 3, mixed, speex, solape humano 0 muestras | (vacío) | (vacío) |
| 23/0 | humano 3, mixed, dtln128, solape humano 131072 muestras | (vacío) | (vacío) |
| 23/1 | humano 3, mixed, dtln128, solape humano 0 muestras | S. | (vacío) |
| original 0 | WAV humano original con padding197 | Se recomienda enfáticamente a los viajeros que se informen sobre cualquier riesgo del clima extremo en el área que visitan, dado que ello puede afectar sus planes de viaje. | Se recomienda enfáticamente a los viajeros que se informen sobre cualquier riesgo del clima extremo en el área que visitan, dado que ello puede afectar sus planes de viaje. |
| original 1 | WAV humano original con padding197 | Fue tanta la cantidad de gente que se concentró, que no todos pudieron acceder al funeral en la plaza de San Pedro. | Fue tanta la cantidad de gente que se concentró, que no todos pudieron acceder al funeral en la plaza de San Pedro. |
| original 2 | WAV humano original con padding197 | However, due to the slow communication channels, styles in the West could lag behind by 25 to 30 years. | However, due to the slow communication channels, styles in the West could lag behind by 25 to 30 years. |
| original 3 | WAV humano original con padding197 | All nouns alongside the world say for you always begin with a capital letter even in the middle of a sentence. | All nouns alongside the word say for you always begin with a capital letter even in the middle of a sentence. |
| silencio | dos segundos de ceros | Thank you. | (vacío) |
