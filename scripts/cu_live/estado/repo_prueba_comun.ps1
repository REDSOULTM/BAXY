# The harness's test git repository for the GitHub Desktop cases (v3-54/55/56): <Documentos>\baxy-repo-prueba, outside
# baxy-prueba-v3 (whose file cases count what is in it). Pasada r9: GitHub Desktop's only repository was the owner's
# "RicardoYMontiel", missing on disk, so every case met "Can't find" and no History, branch or Options to work on.
# Exactly: branch main checked out with 3 commits (fixed author and dates: the same hashes every time), a branch
# prueba-rama at the second commit, a clean tree. A folder that is not exactly that is rebuilt; only that folder, and
# only when it is proven the harness's (Get-DecisionRepoDelArnes: empty, or every commit by prueba@baxy.invalid).
# Harness only. ASCII only.
. (Join-Path $PSScriptRoot 'decisiones_comun.ps1')
$global:RepoPruebaRaiz=Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'baxy-repo-prueba'
$global:RepoPruebaCommits=@(
  @{ msg='Primer commit de prueba'; fecha='2026-01-05T10:00:00-03:00'; archivo='LEEME.md'; texto="# repo de prueba`n`nRepositorio de prueba del arnes de BAXY.`n" }
  @{ msg='Agrega notas'; fecha='2026-01-06T11:00:00-03:00'; archivo='notas.txt'; texto="notas de prueba`n" }
  @{ msg='Actualiza notas'; fecha='2026-01-07T12:00:00-03:00'; archivo='notas.txt'; texto="notas de prueba`nsegunda linea`n" }
)
$global:RepoPruebaRama='prueba-rama'

function Invoke-GitPrueba([string[]]$GitArgs,[hashtable]$Env=@{}){
  # git in the test repo, without a window and never asking; returns @{ code; out }.
  $psi=New-Object Diagnostics.ProcessStartInfo 'git'
  $psi.Arguments=(@('-C',"`"$global:RepoPruebaRaiz`"")+@($GitArgs | ForEach-Object { if($_ -match '\s'){ "`"$_`"" }else{ $_ } })) -join ' '
  $psi.UseShellExecute=$false; $psi.RedirectStandardOutput=$true; $psi.RedirectStandardError=$true; $psi.CreateNoWindow=$true
  $psi.EnvironmentVariables['GIT_TERMINAL_PROMPT']='0'
  foreach($k in $Env.Keys){ $psi.EnvironmentVariables[$k]=[string]$Env[$k] }
  $p=[Diagnostics.Process]::Start($psi)
  $o=$p.StandardOutput.ReadToEnd(); [void]$p.StandardError.ReadToEnd(); $p.WaitForExit()
  @{ code=$p.ExitCode; out=$o.Trim() }
}

function Get-RepoPruebaEstado(){
  # What the test repo is now: @{ existe; rama; commits (subjects, newest first); ramas; limpio }.
  if(-not (Test-Path -LiteralPath (Join-Path $global:RepoPruebaRaiz '.git'))){ return @{ existe=$false } }
  $rama=(Invoke-GitPrueba @('rev-parse','--abbrev-ref','HEAD')).out
  $log=(Invoke-GitPrueba @('log','--format=%s','main')).out
  $ramas=(Invoke-GitPrueba @('branch','--format=%(refname:short)')).out
  $st=Invoke-GitPrueba @('status','--porcelain')
  @{ existe=$true; rama=$rama; commits=@($log -split "`n" | Where-Object { $_ }); ramas=@($ramas -split "`n" | Where-Object { $_ } | Sort-Object); limpio=($st.code -eq 0 -and -not $st.out) }
}

function Test-RepoPruebaValido($S){
  # Get-DecisionRepoPrueba (decisiones_comun.ps1) on the expected shape.
  Get-DecisionRepoPrueba $S @($global:RepoPruebaCommits | ForEach-Object { $_.msg }) $global:RepoPruebaRama
}

function Get-RepoPruebaPropiedad(){
  # What proves the folder the harness's: @{ existe; vacia; git_ok; autores (every commit's author e-mail, all refs) }.
  if(-not (Test-Path -LiteralPath $global:RepoPruebaRaiz)){ return @{ existe=$false } }
  $vacia=(@(Get-ChildItem -LiteralPath $global:RepoPruebaRaiz -Force -ErrorAction SilentlyContinue).Count -eq 0)
  if($vacia -or -not (Test-Path -LiteralPath (Join-Path $global:RepoPruebaRaiz '.git'))){ return @{ existe=$true; vacia=$vacia; git_ok=$false } }
  $g=Invoke-GitPrueba @('log','--all','--format=%ae')
  @{ existe=$true; vacia=$false; git_ok=($g.code -eq 0); autores=@($g.out -split "`n" | Where-Object { $_ }) }
}

function New-RepoPrueba(){
  # Rebuilds the folder from nothing: its CONTENTS are removed (the folder itself stays: GitHub Desktop open on it
  # holds it, revision 2026-10-08), only when it is proven the harness's. Returns $true when the result is valid;
  # $global:RepoPruebaMotivo says why not ('ajeno': not proven the harness's, untouched; 'ocupado': something stayed).
  $global:RepoPruebaMotivo=''
  if(-not (Get-DecisionRepoDelArnes (Get-RepoPruebaPropiedad))){ $global:RepoPruebaMotivo='ajeno'; return $false }
  if(Test-Path -LiteralPath $global:RepoPruebaRaiz){
    foreach($x in @(Get-ChildItem -LiteralPath $global:RepoPruebaRaiz -Force)){ Remove-Item -LiteralPath $x.FullName -Recurse -Force -ErrorAction SilentlyContinue }
    if(@(Get-ChildItem -LiteralPath $global:RepoPruebaRaiz -Force -ErrorAction SilentlyContinue).Count){ $global:RepoPruebaMotivo='ocupado'; return $false }
  }else{ [void](New-Item -ItemType Directory -Path $global:RepoPruebaRaiz) }
  $utf8=New-Object Text.UTF8Encoding $false
  if((Invoke-GitPrueba @('init','-q','-b','main')).code -ne 0){ return $false }
  [void](Invoke-GitPrueba @('config','core.autocrlf','false'))
  $i=0
  foreach($c in $global:RepoPruebaCommits){
    [IO.File]::WriteAllText((Join-Path $global:RepoPruebaRaiz $c.archivo),$c.texto,$utf8)
    [void](Invoke-GitPrueba @('add','--',$c.archivo))
    $env1=@{ GIT_AUTHOR_NAME='BAXY prueba'; GIT_AUTHOR_EMAIL='prueba@baxy.invalid'; GIT_COMMITTER_NAME='BAXY prueba'; GIT_COMMITTER_EMAIL='prueba@baxy.invalid'; GIT_AUTHOR_DATE=$c.fecha; GIT_COMMITTER_DATE=$c.fecha }
    if((Invoke-GitPrueba @('-c','commit.gpgsign=false','commit','-q','--no-verify','-m',$c.msg) $env1).code -ne 0){ return $false }
    $i++
    if($i -eq 2){ [void](Invoke-GitPrueba @('branch',$global:RepoPruebaRama)) }
  }
  Test-RepoPruebaValido (Get-RepoPruebaEstado)
}
