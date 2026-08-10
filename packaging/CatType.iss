#define MyAppName "Cat Type"
#define MyAppVersion "1.0.3"
#define MyAppPublisher "fungusta"
#define MyAppExeName "Cat Type.exe"

[Setup]
AppId={{B5744A59-8267-45DE-A419-5FF56D9BB86C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Cat Type
DefaultGroupName=Cat Type
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=Cat Type Setup
SetupIconFile=..\assets\cat-type.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked
Name: "launchstartup"; Description: "Start Cat Type when I sign in to Windows"; GroupDescription: "Startup:"

[Files]
Source: "..\dist\Cat Type.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\Cat Type"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\Cat Type"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Cat Type"; ValueData: """{app}\{#MyAppExeName}"""; Tasks: launchstartup; Flags: uninsdeletevalue

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch Cat Type"; Flags: nowait postinstall skipifsilent
