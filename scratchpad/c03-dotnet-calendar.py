from pathlib import Path
import subprocess, sys
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from scripts.measure_mind_budget import dotnet_executable,environment_for_dotnet
exe=dotnet_executable()
command=[str(exe),'test','tests/Baxy.Integration.Tests/Baxy.Integration.Tests.csproj','-c','Release','--nologo','-v:minimal','--filter','FullyQualifiedName~PlannerAppBoundaryTests|FullyQualifiedName~C03FactPreservationTests|FullyQualifiedName~MindShellEndToEndTests']
raise SystemExit(subprocess.call(command,cwd=root,env=environment_for_dotnet(exe)))
