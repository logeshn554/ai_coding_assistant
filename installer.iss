; =====================================================================
; DevPilot AI Coding Assistant - Inno Setup Script (VS Code Style)
; =====================================================================

#define MyAppName "DevPilot AI Editor"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "DevPilot Team"
#define MyAppURL "https://devpilot.ai"
#define MyAppExeName "DevPilot.exe"

[Setup]
AppId={{D37E8675-812C-4A2D-A32F-E2B45A884719}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={localappdata}\Programs\DevPilot
DisableDirPage=no
DisableProgramGroupPage=auto
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
PrivilegesRequired=lowest
OutputDir=dist
OutputBaseFilename=DevPilot-Windows-Setup-{#MyAppVersion}
SetupIconFile=assets\devpilot.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
LicenseFile=TERMS_AND_CONDITIONS.txt
UninstallDisplayIcon={app}\{#MyAppExeName}
ChangesEnvironment=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "addtopath"; Description: "Add to PATH (restart terminals to apply)"; GroupDescription: "Other:"; Flags: unchecked

[Files]
Source: "dist\DevPilot\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Environment"; ValueType: expandsz; ValueName: "Path"; ValueData: "{olddata};{app}"; Tasks: addtopath; Flags: preservestringtype

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
