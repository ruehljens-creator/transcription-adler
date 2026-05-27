; Inno Setup Script for Transcription Adler
[Setup]
AppName=Transcription Adler
AppVersion=1.0
AppPublisher=Jens ruehljens-creator
DefaultDirName={autopf}\Transcription Adler
DefaultGroupName=Transcription Adler
OutputDir=.
OutputBaseFilename=TranscriptionAdler_Setup
Compression=lzma2/max
SolidCompression=yes
SetupIconFile=eagle_icon.ico
UninstallDisplayIcon={app}\TranscriptionAdler.exe
PrivilegesRequired=lowest

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "dist\TranscriptionAdler\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Transcription Adler"; Filename: "{app}\TranscriptionAdler.exe"
Name: "{commondesktops}\Transcription Adler"; Filename: "{app}\TranscriptionAdler.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\TranscriptionAdler.exe"; Description: "{cm:LaunchProgram,Transcription Adler}"; Flags: nowait postinstall skipifsilent
