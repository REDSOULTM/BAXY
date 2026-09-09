@echo off
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" >nul
if errorlevel 1 exit /b %errorlevel%
cl /nologo /O2 /MD /LD /DHAVE_CONFIG_H /I..\speexdsp-1.2.1\include /I..\speexdsp-1.2.1\win32 ..\speexdsp-1.2.1\libspeexdsp\mdf.c ..\speexdsp-1.2.1\libspeexdsp\fftwrap.c ..\speexdsp-1.2.1\libspeexdsp\smallft.c ..\speexdsp-1.2.1\libspeexdsp\preprocess.c ..\speexdsp-1.2.1\libspeexdsp\filterbank.c /link /DEF:exports.def /OUT:speexdsp.dll
exit /b %errorlevel%
