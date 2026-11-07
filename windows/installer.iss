; Currycaster Windows installer.
; Original work Copyright (c) 2024 Adam Curry. MIT License.
; Keep MyAppVersion aligned with cc/__init__.py.

#define MyAppName "Currycaster"
#define MyAppVersion "41.8"
#define MyAppPublisher "Adam Curry"
#define MyAppURL "https://github.com/bstirling2307/currycaster"
#define MyAppExeName "Currycaster.exe"

[Setup]
AppId={{8F4C2E1A-6B7D-4E5F-9A10-2C3D4E5F6071}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
DefaultDirName={autopf}\Currycaster
DefaultGroupName=Currycaster
DisableProgramGroupPage=yes
LicenseFile=..\LICENSE
OutputDir=output
OutputBaseFilename=Currycaster-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
Source: "..\dist\Currycaster\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Currycaster"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\Currycaster"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch Currycaster"; Flags: nowait postinstall skipifsilent
