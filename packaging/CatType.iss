#define MyAppName "Cat Type"
#define MyAppVersion "1.0.13"
#define MyAppPublisher "fungusta"
#define MyAppExeName "Cat Type.exe"
#ifndef MyAppId
  #define MyAppId "{{B5744A59-8267-45DE-A419-5FF56D9BB86C}"
#endif
#ifndef MyOutputBaseFilename
  #define MyOutputBaseFilename "Cat Type Setup"
#endif
#ifndef MyUninstallable
  #define MyUninstallable "yes"
#endif

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Cat Type
DefaultGroupName=Cat Type
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename={#MyOutputBaseFilename}
SetupIconFile=..\assets\cat-type.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=force
RestartApplications=no
Uninstallable={#MyUninstallable}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked
Name: "launchstartup"; Description: "Start Cat Type when I sign in to Windows"; GroupDescription: "Startup:"

[Files]
Source: "..\dist\Cat Type.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
#ifndef SmokeTest
Name: "{autoprograms}\Cat Type"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\Cat Type"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
#endif

[Registry]
#ifndef SmokeTest
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Cat Type"; ValueData: """{app}\{#MyAppExeName}"""; Tasks: launchstartup; Flags: uninsdeletevalue
#endif

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch Cat Type"; Flags: nowait postinstall skipifsilent
Filename: "{app}\{#MyAppExeName}"; Flags: nowait skipifnotsilent; Check: IsAutoUpdate

[Code]
const
  EVENT_MODIFY_STATE = $0002;
  SYNCHRONIZE = $00100000;

function OpenEventW(dwDesiredAccess: DWORD; bInheritHandle: BOOL;
  lpName: String): THandle;
  external 'OpenEventW@kernel32.dll stdcall';
function SetEvent(hEvent: THandle): BOOL;
  external 'SetEvent@kernel32.dll stdcall';
function CloseHandle(hObject: THandle): BOOL;
  external 'CloseHandle@kernel32.dll stdcall';
function OpenMutexW(dwDesiredAccess: DWORD; bInheritHandle: BOOL;
  lpName: String): THandle;
  external 'OpenMutexW@kernel32.dll stdcall';

function IsAutoUpdate: Boolean;
var
  Index: Integer;
begin
  Result := False;
  if not WizardSilent then
    Exit;
  for Index := 1 to ParamCount do
  begin
    if CompareText(ParamStr(Index), '/AUTOUPDATE=1') = 0 then
    begin
      Result := True;
      Exit;
    end;
  end;
end;

function OpenCatTypeShutdownEvent: THandle;
begin
  Result := OpenEventW(
    EVENT_MODIFY_STATE, False, 'Local\CatTypeShutdown');
end;

procedure SignalCatTypeShutdown(ShutdownEvent: THandle);
begin
  SetEvent(ShutdownEvent);
  CloseHandle(ShutdownEvent);
end;

procedure WaitForCatTypeExit;
var
  Attempt: Integer;
  InstanceMutex: THandle;
begin
  for Attempt := 1 to 50 do
  begin
    InstanceMutex := OpenMutexW(
      SYNCHRONIZE, False, 'Local\CatTypeDesktopApp');
    if InstanceMutex = 0 then
      Exit;
    CloseHandle(InstanceMutex);
    Sleep(100);
  end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ShutdownEvent: THandle;
begin
  Result := '';
  if WizardSilent then
  begin
    if not IsAutoUpdate then
    begin
      Result := 'Automatic update authorization is missing.';
      Exit;
    end;
    ShutdownEvent := OpenCatTypeShutdownEvent;
  end
  else
  begin
    ShutdownEvent := OpenCatTypeShutdownEvent;
    if ShutdownEvent = 0 then
      Exit;
    if MsgBox(
      'Cat Type must close to update. Close Cat Type now and continue?',
      mbConfirmation, MB_YESNO) <> IDYES then
    begin
      CloseHandle(ShutdownEvent);
      Result := 'Cat Type must close before the update can continue.';
      Exit;
    end;
  end;
  if ShutdownEvent <> 0 then
  begin
    SignalCatTypeShutdown(ShutdownEvent);
    WaitForCatTypeExit;
  end;
end;
