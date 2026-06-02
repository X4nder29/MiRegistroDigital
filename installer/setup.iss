; Inno Setup script para MiRegistroDigital
; Genera un instalador .exe con acceso directo y desinstalador.
;
; Requisitos:
;   1. Ejecutar installer\build.bat primero para generar dist\MiRegistroDigital\
;   2. Compilar con Inno Setup: iscc installer\setup.iss

#define MyAppName "MiRegistroDigital"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "MiRegistroDigital"
#define MyAppURL ""
#define MyAppExeName "MiRegistroDigital.exe"

[Setup]
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir=..\dist
OutputBaseFilename=MiRegistroDigital_Installer
Compression=lzma2
SolidCompression=yes
DisableProgramGroupPage=yes
DisableWelcomePage=no
UninstallDisplayIcon={app}\{#MyAppExeName}
PrivilegesRequired=admin

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Files]
Source: "..\dist\MiRegistroDigital\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Ejecutar {#MyAppName}"; Flags: postinstall nowait skipifsilent unchecked

[UninstallRun]
Filename: "{app}\{#MyAppExeName}"; Parameters: "--uninstall"
