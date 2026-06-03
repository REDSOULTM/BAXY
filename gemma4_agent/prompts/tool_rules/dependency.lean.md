dependency(...): diagnostica módulos Python y binarios de sistema que otras tools usan. Actions: status, list, verify, explain_missing, install, repair.
!= package (apps desktop de usuario vía winget). dependency = lo que el AGENTE necesita (ffmpeg p/media_edit, psycopg p/database, etc.).
install es advisory salvo cableado explícito -> reportá el hint y dejá decidir al user, salvo que pida reparación automática.
