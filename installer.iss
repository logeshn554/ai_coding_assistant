; =====================================================================
; DevPilot AI Coding Assistant - Full VS Code Style Windows Installer
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
OutputDir=dist_installer
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
Name: "addcontextmenufiles"; Description: "Add ""Open with DevPilot"" action to Windows Explorer file context menu"; GroupDescription: "Other:"; Flags: checkedonce
Name: "addcontextmenufolders"; Description: "Add ""Open with DevPilot"" action to Windows Explorer directory context menu"; GroupDescription: "Other:"; Flags: checkedonce
Name: "associatewithfiles"; Description: "Register DevPilot as an editor for supported file types"; GroupDescription: "Other:"; Flags: unchecked
Name: "addtopath"; Description: "Add to PATH (restart terminals to apply)"; GroupDescription: "Other:"; Flags: checkedonce

[Files]
Source: "dist\DevPilot\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
; PATH environment variable
Root: HKCU; Subkey: "Environment"; ValueType: expandsz; ValueName: "Path"; ValueData: "{olddata};{app}"; Tasks: addtopath; Flags: preservestringtype

; "Open with DevPilot" for files
Root: HKCU; Subkey: "Software\Classes\*\shell\DevPilot"; ValueType: string; ValueName: ""; ValueData: "Open with DevPilot"; Tasks: addcontextmenufiles; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\*\shell\DevPilot"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""; Tasks: addcontextmenufiles
Root: HKCU; Subkey: "Software\Classes\*\shell\DevPilot\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Tasks: addcontextmenufiles

; "Open with DevPilot" for folders
Root: HKCU; Subkey: "Software\Classes\Directory\shell\DevPilot"; ValueType: string; ValueName: ""; ValueData: "Open with DevPilot"; Tasks: addcontextmenufolders; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\Directory\shell\DevPilot"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""; Tasks: addcontextmenufolders
Root: HKCU; Subkey: "Software\Classes\Directory\shell\DevPilot\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%V"""; Tasks: addcontextmenufolders

; "Open with DevPilot" for folder background
Root: HKCU; Subkey: "Software\Classes\Directory\Background\shell\DevPilot"; ValueType: string; ValueName: ""; ValueData: "Open with DevPilot"; Tasks: addcontextmenufolders; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\Directory\Background\shell\DevPilot"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""; Tasks: addcontextmenufolders
Root: HKCU; Subkey: "Software\Classes\Directory\Background\shell\DevPilot\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%V"""; Tasks: addcontextmenufolders

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
