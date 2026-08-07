; Srxy offline Windows installer (Inno Setup 6.2+ / 7).
; Built by packaging/windows/build-offline.ps1 - do not compile without the staged payload.
;
; Defines expected from the build script:
;   MyAppVersion, InstallerVersion, Arch, PayloadDir, OutputDir,
;   PrivacyEnFile, PrivacyEsFile, SetupIconFile

#if Ver < EncodeVer(6,2,0)
  #error Inno Setup 6.2 or later is required (ExecAndLogOutput). Prefer Inno Setup 7.
#endif

#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif
#ifndef InstallerVersion
  #define InstallerVersion "0"
#endif
#ifndef Arch
  #define Arch "x86_64"
#endif
#ifndef PayloadDir
  #define PayloadDir "payload"
#endif
#ifndef OutputDir
  #define OutputDir "dist"
#endif
#ifndef PrivacyEnFile
  #define PrivacyEnFile "privacy-en.txt"
#endif
#ifndef PrivacyEsFile
  #define PrivacyEsFile "privacy-es.txt"
#endif
#ifndef PrivacyAckVersion
  #define PrivacyAckVersion "6"
#endif
#ifndef SetupIconFile
  #define SetupIconFile "srxy-installer.ico"
#endif

#define MyAppName "Srxy"
#define MyAppPublisher "srxy"
#define MyAppURL "https://github.com/illescasDaniel/srxy"
#define MyAppExeName "Srxy.exe"

[Setup]
AppId={{A7E8C2F1-9B4D-4E6A-8F31-2C5D9A1B0E77}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion} ({cm:InstallerLabel} {#InstallerVersion})
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
DefaultDirName={localappdata}\Programs\srxy
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
#if Ver >= EncodeVer(7,0,0)
SetupArchitecture=x64
#endif
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutputDir}
OutputBaseFilename=srxy-{#MyAppVersion}-installer-{#InstallerVersion}-{#Arch}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
SetupIconFile={#SetupIconFile}
UninstallDisplayIcon={app}\bin\{#MyAppExeName}
SetupLogging=yes
CloseApplications=no
RestartApplications=no
DirExistsWarning=no
UsePreviousAppDir=yes
AllowNoIcons=yes
UsePreviousSetupType=no
ShowComponentSizes=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[CustomMessages]
; Keep in sync with src/srxy/i18n/{en,es}.json installer.* where practical.
english.TypeRecommendedGpu=Recommended (GPU) - Tesseract, ffmpeg, smarter search
english.TypeRecommendedCpu=Recommended (no GPU) - Tesseract and ffmpeg
english.TypeSimple=Simple - app only (not recommended)
english.TypeComplete=Complete - includes AI model download
english.TypeCustom=Custom installation
english.InstallerLabel=Installer
english.CompCore=Srxy application
english.CompTesseract=Text in images (Tesseract; downloaded during install)
english.TessLangPageCaption=Languages for text in images
english.TessLangPageDescription=Choose languages for reading text in photos and scans (English and orientation always on).
english.CompFfmpeg=Audio/video helper (ffmpeg; downloaded during install)
english.CompSemantic=Smarter search packages (semantic extras; needs a GPU)
english.CompModels=Download AI models now (requires Smarter search)
english.TasksGroup=Additional tasks:
english.TaskAddPath=Add Srxy to the user PATH
english.TaskDesktop=Create a desktop shortcut
english.RunLaunch=Launch Srxy
english.ModePageCaption=Installation mode
english.ModePageDescription=What do you want to do?
english.ModePageSubCaption=Choose install/update, reinstall, or uninstall.
english.ModeInstall=Install or update
english.ModeReinstall=Reinstall (remove then install)
english.ModeUninstall=Uninstall
english.PrivacyPageCaption=Privacy & downloads notice
english.PrivacyPageDescription=Please review and acknowledge before continuing.
english.PrivacyAck=I understand and want to continue
english.PrivacyMissing=Privacy notice file missing from the installer payload.
english.PrivacyNeedAck=Please acknowledge the privacy notice to continue.
english.ProgressCaption=Installing Srxy
english.ProgressDescription=Please wait while Srxy is installed.
english.ProgressRunning=Running install engine...
english.ProgressUninstallCaption=Uninstalling Srxy
english.ProgressUninstallDescription=Please wait while Srxy is removed.
english.ProgressUninstallRunning=Running uninstall engine...
english.ProgressReinstallCaption=Reinstalling Srxy
english.ProgressReinstallDescription=Please wait while Srxy is reinstalled.
english.ProgressReinstallRunning=Running reinstall engine...
english.WizardUninstalling=Uninstalling
english.WizardUninstallingLabel=Please wait while Setup removes Srxy from your computer.
english.WizardReinstalling=Reinstalling
english.WizardReinstallingLabel=Please wait while Setup reinstalls Srxy on your computer.
english.ReadyModeLabel=Mode:
english.ReadyUninstallCaption=Ready to Uninstall
english.ReadyUninstallDescription=Setup is now ready to remove Srxy from your computer. Click Uninstall to continue, or click Back if you want to review or change any settings.
english.ReadyReinstallCaption=Ready to Reinstall
english.ReadyReinstallDescription=Setup is now ready to remove and reinstall Srxy. Click Reinstall to continue, or click Back if you want to review or change any settings.
english.ButtonUninstall=Uninstall
english.ButtonReinstall=Reinstall
english.ErrBootstrapMissing=Bootstrap Python was not found. The installer payload may be incomplete.
english.ErrEngineStart=Failed to start the install engine.
english.ErrEngineFailed=Install engine failed with exit code %1. See %2 for details.
english.ErrEngineException=The Srxy install engine reported a failure. See {app}\logs\installer-engine.log

spanish.TypeRecommendedGpu=Recomendada (GPU) - Tesseract, ffmpeg y búsqueda más inteligente
spanish.TypeRecommendedCpu=Recomendada (sin GPU) - Tesseract y ffmpeg
spanish.TypeSimple=Simple - solo la app (no recomendada)
spanish.TypeComplete=Completa - incluye descarga de modelos de IA
spanish.TypeCustom=Instalación personalizada
spanish.InstallerLabel=Instalador
spanish.CompCore=Aplicación Srxy
spanish.CompTesseract=Texto en imágenes (Tesseract; se descarga durante la instalación)
spanish.TessLangPageCaption=Idiomas para texto en imágenes
spanish.TessLangPageDescription=Elige idiomas para leer texto en fotos y escaneos (inglés y orientación siempre activos).
spanish.CompFfmpeg=Ayuda de audio y vídeo (ffmpeg; se descarga durante la instalación)
spanish.CompSemantic=Paquetes de búsqueda más inteligente (extras semantic; necesita GPU)
spanish.CompModels=Descargar modelos de IA ahora (requiere búsqueda más inteligente)
spanish.TasksGroup=Tareas adicionales:
spanish.TaskAddPath=Añadir Srxy al PATH del usuario
spanish.TaskDesktop=Crear un acceso directo en el escritorio
spanish.RunLaunch=Iniciar Srxy
spanish.ModePageCaption=Modo de instalación
spanish.ModePageDescription=¿Qué quieres hacer?
spanish.ModePageSubCaption=Elige instalar/actualizar, reinstalar o desinstalar.
spanish.ModeInstall=Instalar o actualizar
spanish.ModeReinstall=Reinstalar (quitar e instalar de nuevo)
spanish.ModeUninstall=Desinstalar
spanish.PrivacyPageCaption=Aviso de privacidad y descargas
spanish.PrivacyPageDescription=Revisa y confirma el aviso antes de continuar.
spanish.PrivacyAck=Entiendo y quiero continuar
spanish.PrivacyMissing=Falta el aviso de privacidad en el contenido del instalador.
spanish.PrivacyNeedAck=Confirma el aviso de privacidad para continuar.
spanish.ProgressCaption=Instalando Srxy
spanish.ProgressDescription=Espera mientras se instala Srxy.
spanish.ProgressRunning=Ejecutando el motor de instalación...
spanish.ProgressUninstallCaption=Desinstalando Srxy
spanish.ProgressUninstallDescription=Espera mientras se elimina Srxy.
spanish.ProgressUninstallRunning=Ejecutando el motor de desinstalación...
spanish.ProgressReinstallCaption=Reinstalando Srxy
spanish.ProgressReinstallDescription=Espera mientras se reinstala Srxy.
spanish.ProgressReinstallRunning=Ejecutando el motor de reinstalación...
spanish.WizardUninstalling=Desinstalando
spanish.WizardUninstallingLabel=Espera mientras el asistente elimina Srxy de tu equipo.
spanish.WizardReinstalling=Reinstalando
spanish.WizardReinstallingLabel=Espera mientras el asistente reinstala Srxy en tu equipo.
spanish.ReadyModeLabel=Modo:
spanish.ReadyUninstallCaption=Listo para desinstalar
spanish.ReadyUninstallDescription=El asistente está listo para eliminar Srxy de tu equipo. Haz clic en Desinstalar para continuar, o en Atrás si quieres revisar o cambiar alguna opción.
spanish.ReadyReinstallCaption=Listo para reinstalar
spanish.ReadyReinstallDescription=El asistente está listo para quitar e instalar de nuevo Srxy. Haz clic en Reinstalar para continuar, o en Atrás si quieres revisar o cambiar alguna opción.
spanish.ButtonUninstall=Desinstalar
spanish.ButtonReinstall=Reinstalar
spanish.ErrBootstrapMissing=No se encontró el Python de arranque. El contenido del instalador puede estar incompleto.
spanish.ErrEngineStart=No se pudo iniciar el motor de instalación.
spanish.ErrEngineFailed=El motor de instalación falló con el código %1. Consulta %2 para más detalles.
spanish.ErrEngineException=El motor de instalación de Srxy informó de un error. Consulta {app}\logs\installer-engine.log

[Types]
; Order: safer silent default first (CPU recommended). Interactive wizard
; overrides to GPU recommended when an NVIDIA GPU is detected.
Name: "recommendedcpu"; Description: "{cm:TypeRecommendedCpu}"
Name: "recommendedgpu"; Description: "{cm:TypeRecommendedGpu}"
Name: "simple"; Description: "{cm:TypeSimple}"
Name: "complete"; Description: "{cm:TypeComplete}"
Name: "custom"; Description: "{cm:TypeCustom}"; Flags: iscustom

[Components]
Name: "core"; Description: "{cm:CompCore}"; Types: recommendedcpu recommendedgpu simple complete custom; Flags: fixed
Name: "tesseract"; Description: "{cm:CompTesseract}"; Types: recommendedcpu recommendedgpu complete custom
Name: "ffmpeg"; Description: "{cm:CompFfmpeg}"; Types: recommendedcpu recommendedgpu complete custom
Name: "semantic"; Description: "{cm:CompSemantic}"; Types: recommendedgpu complete custom
Name: "models"; Description: "{cm:CompModels}"; Types: complete custom

[Tasks]
Name: "addpath"; Description: "{cm:TaskAddPath}"; GroupDescription: "{cm:TasksGroup}"; Flags: checkedonce
Name: "desktopicon"; Description: "{cm:TaskDesktop}"; GroupDescription: "{cm:TasksGroup}"; Flags: unchecked

[Files]
; Bootstrap lives under {tmp} for the engine run. A tiny marker keeps {app} registered for ARP.
Source: "{#PayloadDir}\*"; DestDir: "{tmp}\srxy-boot"; Flags: ignoreversion recursesubdirs createallsubdirs deleteafterinstall; Components: core; Check: not IsUninstallMode
Source: "{#PrivacyEnFile}"; DestDir: "{app}"; DestName: ".srxy-installer-marker"; Flags: ignoreversion; Components: core; Check: not IsUninstallMode
Source: "{#PrivacyEnFile}"; DestName: "privacy-en.txt"; Flags: dontcopy
Source: "{#PrivacyEsFile}"; DestName: "privacy-es.txt"; Flags: dontcopy
Source: "tessdata-langs.txt"; DestName: "tessdata-langs.txt"; Flags: dontcopy

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\bin\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\bin\{#MyAppExeName}"; Check: not IsUninstallMode
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\bin\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\bin\{#MyAppExeName}"; Tasks: desktopicon; Check: not IsUninstallMode

[Run]
Filename: "{app}\bin\{#MyAppExeName}"; Description: "{cm:RunLaunch}"; Flags: nowait postinstall skipifsilent; Check: not IsUninstallMode

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
function SetEnvironmentVariable(Name, Value: String): BOOL;
  external 'SetEnvironmentVariableW@kernel32.dll stdcall';

var
  ModePage: TInputOptionWizardPage;
  PrivacyPage: TWizardPage;
  PrivacyMemo: TNewMemo;
  PrivacyCheck: TNewCheckBox;
  TessLangPage: TWizardPage;
  TessLangList: TNewCheckListBox;
  TessLangCodes: TStringList;
  ProgressPage: TOutputProgressWizardPage;
  SelectedMode: Integer; { 0=install/update, 1=reinstall, 2=uninstall }
  DetectedGpu: Boolean;
  DefaultTypeApplied: Boolean;
  EngineLogFile: String;
  EngineShowProgress: Boolean;
  EnginePhaseLabel: String;
  EnginePhaseIndex: Integer;
  EnginePhaseTotal: Integer;
  EngineProgressLabel: String;
  EngineProgressDone: Int64;
  EngineProgressTotal: Int64;

function IsUninstallMode: Boolean;
begin
  Result := SelectedMode = 2;
end;

function FormatBytes(N: Int64): String;
begin
  if N < Int64(1024) then
  begin
    Result := IntToStr(N) + ' B';
    Exit;
  end;
  if N < Int64(1024) * Int64(1024) then
  begin
    Result := IntToStr(N div Int64(1024)) + ' KB';
    Exit;
  end;
  if N < Int64(1024) * Int64(1024) * Int64(1024) then
  begin
    Result := IntToStr(N div (Int64(1024) * Int64(1024))) + ' MB';
    Exit;
  end;
  Result := IntToStr(N div (Int64(1024) * Int64(1024) * Int64(1024))) + ' GB';
end;

function TabField(const S: String; Index: Integer): String;
var
  StartPos, Current, I: Integer;
begin
  Result := '';
  StartPos := 1;
  Current := 0;
  for I := 1 to Length(S) + 1 do
  begin
    if (I > Length(S)) or (S[I] = #9) then
    begin
      if Current = Index then
      begin
        Result := Copy(S, StartPos, I - StartPos);
        Exit;
      end;
      Current := Current + 1;
      StartPos := I + 1;
    end;
  end;
end;

procedure ApplyEngineProgressUI;
var
  Primary, Secondary: String;
  Pct: Integer;
begin
  if (not EngineShowProgress) or (ProgressPage = nil) then
    Exit;
  Primary := EnginePhaseLabel;
  if Primary = '' then
    Primary := CustomMessage('ProgressRunning');
  if (EnginePhaseTotal > 0) and (EnginePhaseIndex > 0) then
    Primary := Primary + ' (' + IntToStr(EnginePhaseIndex) + '/' + IntToStr(EnginePhaseTotal) + ')';
  Secondary := '';
  if (EngineProgressTotal > 1) and (EngineProgressLabel <> '') then
    Secondary := EngineProgressLabel + ' - ' +
      FormatBytes(EngineProgressDone) + ' / ' + FormatBytes(EngineProgressTotal)
  else if EngineProgressLabel <> '' then
    Secondary := EngineProgressLabel;
  ProgressPage.SetText(Primary, Secondary);
  if EngineProgressTotal > 1 then
  begin
    if EngineProgressTotal <= 0 then
      Pct := 0
    else
      Pct := Integer((EngineProgressDone * Int64(1000)) div EngineProgressTotal);
    if Pct < 0 then Pct := 0;
    if Pct > 1000 then Pct := 1000;
    ProgressPage.SetProgress(Pct, 1000);
  end
  else if EnginePhaseTotal > 0 then
  begin
    if EnginePhaseIndex < 0 then
      ProgressPage.SetProgress(0, EnginePhaseTotal)
    else if EnginePhaseIndex > EnginePhaseTotal then
      ProgressPage.SetProgress(EnginePhaseTotal, EnginePhaseTotal)
    else
      ProgressPage.SetProgress(EnginePhaseIndex, EnginePhaseTotal);
  end
  else
    ProgressPage.SetProgress(0, 0);
end;

procedure OnEngineOutput(const S: String; const Error, FirstLine: Boolean);
var
  Kind, DoneText, TotalText, LabelText: String;
  DoneValue, TotalValue: Int64;
begin
  if FirstLine and (EngineLogFile <> '') then
    DeleteFile(EngineLogFile);
  if EngineLogFile <> '' then
    SaveStringToFile(EngineLogFile, S + #13#10, True);
  if Error then
  begin
    Log('Install engine output error: ' + S);
    Exit;
  end;
  Kind := TabField(S, 0);
  if Kind = 'STATUS' then
  begin
    LabelText := TabField(S, 1);
    if LabelText <> '' then
      EnginePhaseLabel := LabelText;
    ApplyEngineProgressUI;
    Exit;
  end;
  if Kind = 'TASK' then
  begin
    DoneText := TabField(S, 1);
    TotalText := TabField(S, 2);
    LabelText := TabField(S, 3);
    EnginePhaseIndex := StrToIntDef(DoneText, EnginePhaseIndex);
    EnginePhaseTotal := StrToIntDef(TotalText, EnginePhaseTotal);
    if LabelText <> '' then
      EnginePhaseLabel := LabelText;
    EngineProgressDone := 0;
    EngineProgressTotal := 0;
    EngineProgressLabel := '';
    ApplyEngineProgressUI;
    Exit;
  end;
  if Kind = 'PROGRESS' then
  begin
    DoneText := TabField(S, 1);
    TotalText := TabField(S, 2);
    LabelText := TabField(S, 3);
    try
      DoneValue := StrToInt64(DoneText);
    except
      DoneValue := 0;
    end;
    try
      TotalValue := StrToInt64(TotalText);
    except
      TotalValue := 0;
    end;
    EngineProgressDone := DoneValue;
    EngineProgressTotal := TotalValue;
    if LabelText <> '' then
      EngineProgressLabel := LabelText;
    ApplyEngineProgressUI;
    Exit;
  end;
end;

function EnvTruthy(const Name: String): Boolean;
var
  Value: String;
begin
  Value := LowerCase(GetEnv(Name));
  Result := (Value = '1') or (Value = 'true') or (Value = 'yes') or (Value = 'on');
end;

function DetectNvidiaGpu: Boolean;
var
  ResultCode: Integer;
  Candidate: String;
begin
  { Match srxy.application.gpu_availability force switches. }
  if EnvTruthy('SRXY_FORCE_NO_GPU') or EnvTruthy('SRXY_INSTALLER_FORCE_NO_GPU') then
  begin
    Result := False;
    Exit;
  end;
  if EnvTruthy('SRXY_FORCE_GPU') or EnvTruthy('SRXY_INSTALLER_FORCE_GPU') then
  begin
    Result := True;
    Exit;
  end;
  { 32-bit Setup cannot see System32 nvidia-smi.exe via WOW64 (missing from SysWOW64).
    Prefer sysnative (real System32), then sys, then PATH. }
  Candidate := ExpandConstant('{sysnative}\nvidia-smi.exe');
  if (Candidate <> '') and FileExists(Candidate) then
  begin
    if Exec(Candidate, '-L', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) and (ResultCode = 0) then
    begin
      Log('GPU detection: nvidia-smi ok via sysnative');
      Result := True;
      Exit;
    end;
  end;
  Candidate := ExpandConstant('{sys}\nvidia-smi.exe');
  if (Candidate <> '') and FileExists(Candidate) then
  begin
    if Exec(Candidate, '-L', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) and (ResultCode = 0) then
    begin
      Log('GPU detection: nvidia-smi ok via sys');
      Result := True;
      Exit;
    end;
  end;
  if Exec('nvidia-smi.exe', '-L', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) and (ResultCode = 0) then
  begin
    Log('GPU detection: nvidia-smi ok via PATH nvidia-smi.exe');
    Result := True;
    Exit;
  end;
  if Exec('nvidia-smi', '-L', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) and (ResultCode = 0) then
  begin
    Log('GPU detection: nvidia-smi ok via PATH nvidia-smi');
    Result := True;
    Exit;
  end;
  Result := False;
end;

function InitializeSetup(): Boolean;
begin
  DetectedGpu := DetectNvidiaGpu;
  DefaultTypeApplied := False;
  if DetectedGpu then
    Log('GPU detection: NVIDIA GPU present (recommendedgpu default)')
  else
    Log('GPU detection: no NVIDIA GPU (recommendedcpu default)');
  Result := True;
end;

procedure SelectSetupTypeByDescription(const Description: String);
var
  I: Integer;
begin
  if WizardForm.TypesCombo = nil then
    Exit;
  for I := 0 to WizardForm.TypesCombo.Items.Count - 1 do
  begin
    if WizardForm.TypesCombo.Items[I] = Description then
    begin
      WizardForm.TypesCombo.ItemIndex := I;
      { Assigned() is not valid on this event type in Inno Pascal Script. }
      WizardForm.TypesCombo.OnChange(WizardForm.TypesCombo);
      Exit;
    end;
  end;
end;

procedure ApplyRecommendedSetupType;
begin
  if DetectedGpu then
    SelectSetupTypeByDescription(CustomMessage('TypeRecommendedGpu'))
  else
    SelectSetupTypeByDescription(CustomMessage('TypeRecommendedCpu'));
end;

function BootstrapPython: String;
begin
  Result := ExpandConstant('{tmp}\srxy-boot\python\python.exe');
end;

function BootstrapRoot: String;
begin
  Result := ExpandConstant('{tmp}\srxy-boot');
end;

function PrivacyAckVersionValue: String;
begin
  Result := '{#PrivacyAckVersion}';
end;

function PrivacyFileForLanguage: String;
begin
  if ActiveLanguage = 'spanish' then
    Result := 'privacy-es.txt'
  else
    Result := 'privacy-en.txt';
end;

procedure LoadPrivacyMemo;
var
  PrivacyPath: String;
  Lines: TArrayOfString;
  I: Integer;
begin
  PrivacyMemo.Lines.Clear;
  PrivacyPath := ExpandConstant('{tmp}\' + PrivacyFileForLanguage);
  if not FileExists(PrivacyPath) then
  begin
    ExtractTemporaryFile(PrivacyFileForLanguage);
    PrivacyPath := ExpandConstant('{tmp}\' + PrivacyFileForLanguage);
  end;
  if LoadStringsFromFile(PrivacyPath, Lines) then
  begin
    for I := 0 to GetArrayLength(Lines) - 1 do
      PrivacyMemo.Lines.Add(Lines[I]);
  end
  else
    PrivacyMemo.Lines.Text := CustomMessage('PrivacyMissing');
end;

procedure RemoveUserPathEntry(const BinDir: String);
var
  Current: String;
  Remaining: String;
  Entry: String;
  P: Integer;
  Target: String;
  Kept: String;
begin
  if not RegQueryStringValue(HKCU, 'Environment', 'Path', Current) then
    Exit;
  Target := LowerCase(RemoveBackslash(BinDir));
  Remaining := Current;
  Kept := '';
  while Remaining <> '' do
  begin
    P := Pos(';', Remaining);
    if P > 0 then
    begin
      Entry := Copy(Remaining, 1, P - 1);
      Remaining := Copy(Remaining, P + 1, MaxInt);
    end
    else
    begin
      Entry := Remaining;
      Remaining := '';
    end;
    Entry := Trim(Entry);
    if Entry = '' then
      Continue;
    if LowerCase(RemoveBackslash(Entry)) = Target then
      Continue;
    if Kept <> '' then
      Kept := Kept + ';';
    Kept := Kept + Entry;
  end;
  if Kept <> Current then
    RegWriteExpandStringValue(HKCU, 'Environment', 'Path', Kept);
end;

function EngineLanguageCode: String;
begin
  { Map Inno [Languages] Name values to srxy i18n codes. }
  if CompareText(ActiveLanguage, 'spanish') = 0 then
    Result := 'es'
  else
    Result := 'en';
end;

function TessdataLangsArg: String;
var
  I: Integer;
  Codes: String;
begin
  Codes := '';
  if (TessLangList <> nil) and (TessLangCodes <> nil) then
  begin
    for I := 0 to TessLangList.Items.Count - 1 do
    begin
      if TessLangList.Checked[I] and (I < TessLangCodes.Count) then
      begin
        if Codes <> '' then
          Codes := Codes + ',';
        Codes := Codes + TessLangCodes[I];
      end;
    end;
  end;
  if Codes = '' then
  begin
    if CompareText(ActiveLanguage, 'spanish') = 0 then
      Codes := 'eng,osd,spa'
    else
      Codes := 'eng,osd';
  end;
  Result := Codes;
end;

function BuildEngineArgs(const Action: String): String;
var
  Args: String;
begin
  Args := '-m srxy.adapters.inbound.installer ' + Action +
    ' --prefix "' + WizardDirValue + '"' +
    ' --confirm-unsafe' +
    ' --language ' + EngineLanguageCode;
  if Action <> '--uninstall' then
  begin
    Args := Args + ' --privacy-ack ' + PrivacyAckVersionValue;
    if WizardIsComponentSelected('tesseract') then
    begin
      Args := Args + ' --tesseract';
      Args := Args + ' --tessdata-langs ' + TessdataLangsArg;
    end;
    if WizardIsComponentSelected('ffmpeg') then
      Args := Args + ' --ffmpeg';
    if WizardIsComponentSelected('semantic') then
      Args := Args + ' --semantic';
    if WizardIsComponentSelected('models') and WizardIsComponentSelected('semantic') then
      Args := Args + ' --prefetch-models';
    if WizardIsTaskSelected('addpath') then
      Args := Args + ' --add-path'
    else
      Args := Args + ' --no-add-path';
  end;
  Result := Args;
end;

function ProgressRunningMessage(const Action: String): String;
begin
  if Action = '--uninstall' then
    Result := CustomMessage('ProgressUninstallRunning')
  else if Action = '--reinstall' then
    Result := CustomMessage('ProgressReinstallRunning')
  else
    Result := CustomMessage('ProgressRunning');
end;

function RunEngine(const Action: String): Boolean;
var
  Python: String;
  Args: String;
  ResultCode: Integer;
begin
  Python := BootstrapPython;
  if (Action = '--uninstall') and not FileExists(Python) then
  begin
    { ARP / wizard uninstall without bootstrap: PATH cleanup + let UninstallDelete remove files. }
    RemoveUserPathEntry(ExpandConstant('{app}\bin'));
    Result := True;
    Exit;
  end;
  if not FileExists(Python) then
  begin
    Log('Bootstrap Python missing: ' + Python);
    if not WizardSilent then
      MsgBox(CustomMessage('ErrBootstrapMissing'), mbError, MB_OK);
    Result := False;
    Exit;
  end;
  Args := BuildEngineArgs(Action);
  ForceDirectories(ExpandConstant('{app}\logs'));
  EngineLogFile := ExpandConstant('{app}\logs\installer-engine.log');
  DeleteFile(EngineLogFile);
  EnginePhaseLabel := ProgressRunningMessage(Action);
  EnginePhaseIndex := 0;
  EnginePhaseTotal := 0;
  EngineProgressLabel := '';
  EngineProgressDone := 0;
  EngineProgressTotal := 0;
  EngineShowProgress := not WizardSilent;
  if not SetEnvironmentVariable('SRXY_INSTALLER_PAYLOAD', BootstrapRoot) then
    Log('Warning: failed to set SRXY_INSTALLER_PAYLOAD');
  if not SetEnvironmentVariable('PYTHONUNBUFFERED', '1') then
    Log('Warning: failed to set PYTHONUNBUFFERED');
  { Force UTF-8 stdio so the log file is valid Unicode.  The progress-bar
    wire protocol (_emit) already strips accents to ASCII, so the Inno ANSI
    pipe remains unaffected. }
  if not SetEnvironmentVariable('PYTHONUTF8', '1') then
    Log('Warning: failed to set PYTHONUTF8');
  if not SetEnvironmentVariable('PYTHONIOENCODING', 'utf-8') then
    Log('Warning: failed to set PYTHONIOENCODING');
  Log('Running: ' + Python + ' ' + Args);
  try
    if not ExecAndLogOutput(Python, Args, '', SW_SHOWNORMAL, ewWaitUntilTerminated,
      ResultCode, @OnEngineOutput) then
    begin
      Log('ExecAndLogOutput failed to start install engine');
      if not WizardSilent then
        MsgBox(CustomMessage('ErrEngineStart'), mbError, MB_OK);
      Result := False;
      Exit;
    end;
  except
    Log('ExecAndLogOutput exception: ' + GetExceptionMessage);
    if not WizardSilent then
      MsgBox(CustomMessage('ErrEngineStart'), mbError, MB_OK);
    Result := False;
    Exit;
  end;
  Log('Install engine exit code: ' + IntToStr(ResultCode));
  if ResultCode <> 0 then
  begin
    if not WizardSilent then
      MsgBox(FmtMessage(CustomMessage('ErrEngineFailed'), [IntToStr(ResultCode), EngineLogFile]),
        mbError, MB_OK);
    Result := False;
    Exit;
  end;
  Result := True;
end;

procedure LoadTessLangList;
var
  Lines: TArrayOfString;
  I, P1, P2: Integer;
  Line, Code, Req, LabelText: String;
  Required, Checked, EnabledFlag: Boolean;
begin
  if TessLangCodes = nil then
    TessLangCodes := TStringList.Create;
  TessLangCodes.Clear;
  ExtractTemporaryFile('tessdata-langs.txt');
  if not LoadStringsFromFile(ExpandConstant('{tmp}\tessdata-langs.txt'), Lines) then
    Exit;
  for I := 0 to GetArrayLength(Lines) - 1 do
  begin
    Line := Trim(Lines[I]);
    if Line = '' then
      Continue;
    P1 := Pos('|', Line);
    if P1 = 0 then
      Continue;
    Code := Copy(Line, 1, P1 - 1);
    Line := Copy(Line, P1 + 1, MaxInt);
    P2 := Pos('|', Line);
    if P2 = 0 then
      Continue;
    Req := Copy(Line, 1, P2 - 1);
    LabelText := Copy(Line, P2 + 1, MaxInt);
    Required := Req = '1';
    EnabledFlag := not Required;
    Checked := Required;
    if (not Required) and (CompareText(ActiveLanguage, 'spanish') = 0) and (CompareText(Code, 'spa') = 0) then
      Checked := True;
    TessLangList.AddCheckBox(LabelText + ' (' + Code + ')', '', 0, Checked, EnabledFlag, False, True, nil);
    TessLangCodes.Add(Code);
  end;
end;

procedure InitializeWizard;
begin
  SelectedMode := 0;
  ModePage := CreateInputOptionPage(
    wpWelcome,
    CustomMessage('ModePageCaption'),
    CustomMessage('ModePageDescription'),
    CustomMessage('ModePageSubCaption'),
    True, False);
  ModePage.Add(CustomMessage('ModeInstall'));
  ModePage.Add(CustomMessage('ModeReinstall'));
  ModePage.Add(CustomMessage('ModeUninstall'));
  ModePage.Values[0] := True;

  PrivacyPage := CreateCustomPage(
    wpSelectDir,
    CustomMessage('PrivacyPageCaption'),
    CustomMessage('PrivacyPageDescription'));
  PrivacyMemo := TNewMemo.Create(PrivacyPage);
  PrivacyMemo.Parent := PrivacyPage.Surface;
  PrivacyMemo.Left := 0;
  PrivacyMemo.Top := 0;
  PrivacyMemo.Width := PrivacyPage.SurfaceWidth;
  PrivacyMemo.Height := PrivacyPage.SurfaceHeight - ScaleY(40);
  PrivacyMemo.ScrollBars := ssVertical;
  PrivacyMemo.ReadOnly := True;
  PrivacyMemo.WordWrap := True;
  ExtractTemporaryFile('privacy-en.txt');
  ExtractTemporaryFile('privacy-es.txt');
  LoadPrivacyMemo;

  PrivacyCheck := TNewCheckBox.Create(PrivacyPage);
  PrivacyCheck.Parent := PrivacyPage.Surface;
  PrivacyCheck.Caption := CustomMessage('PrivacyAck');
  PrivacyCheck.Left := 0;
  PrivacyCheck.Top := PrivacyMemo.Top + PrivacyMemo.Height + ScaleY(8);
  PrivacyCheck.Width := PrivacyPage.SurfaceWidth;
  { Silent/CI installs acknowledge via --privacy-ack on the engine CLI. }
  PrivacyCheck.Checked := WizardSilent;

  TessLangPage := CreateCustomPage(
    wpSelectComponents,
    CustomMessage('TessLangPageCaption'),
    CustomMessage('TessLangPageDescription'));
  TessLangList := TNewCheckListBox.Create(TessLangPage);
  TessLangList.Parent := TessLangPage.Surface;
  TessLangList.Left := 0;
  TessLangList.Top := 0;
  TessLangList.Width := TessLangPage.SurfaceWidth;
  TessLangList.Height := TessLangPage.SurfaceHeight;
  LoadTessLangList;

  ProgressPage := CreateOutputProgressPage(
    CustomMessage('ProgressCaption'),
    CustomMessage('ProgressDescription'));
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if (CurPageID = wpSelectComponents) and (not DefaultTypeApplied) and (not IsUninstallMode) then
  begin
    DefaultTypeApplied := True;
    ApplyRecommendedSetupType;
  end;

  { Ready / Installing pages still say Install by default; retarget for uninstall/reinstall. }
  if CurPageID = wpReady then
  begin
    case SelectedMode of
      2:
        begin
          WizardForm.PageNameLabel.Caption := CustomMessage('ReadyUninstallCaption');
          WizardForm.PageDescriptionLabel.Caption := CustomMessage('ReadyUninstallDescription');
          WizardForm.NextButton.Caption := CustomMessage('ButtonUninstall');
        end;
      1:
        begin
          WizardForm.PageNameLabel.Caption := CustomMessage('ReadyReinstallCaption');
          WizardForm.PageDescriptionLabel.Caption := CustomMessage('ReadyReinstallDescription');
          WizardForm.NextButton.Caption := CustomMessage('ButtonReinstall');
        end;
    else
      begin
        WizardForm.PageNameLabel.Caption := SetupMessage(msgWizardReady);
        WizardForm.PageDescriptionLabel.Caption := SetupMessage(msgReadyLabel1);
        WizardForm.NextButton.Caption := SetupMessage(msgButtonInstall);
      end;
    end;
  end
  else if CurPageID = wpInstalling then
  begin
    case SelectedMode of
      2:
        begin
          WizardForm.PageNameLabel.Caption := CustomMessage('WizardUninstalling');
          WizardForm.PageDescriptionLabel.Caption := CustomMessage('WizardUninstallingLabel');
        end;
      1:
        begin
          WizardForm.PageNameLabel.Caption := CustomMessage('WizardReinstalling');
          WizardForm.PageDescriptionLabel.Caption := CustomMessage('WizardReinstallingLabel');
        end;
    end;
  end
  else if CurPageID = wpFinished then
    WizardForm.NextButton.Caption := SetupMessage(msgButtonFinish)
  else
    WizardForm.NextButton.Caption := SetupMessage(msgButtonNext);
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID = ModePage.ID then
  begin
    if ModePage.Values[0] then SelectedMode := 0
    else if ModePage.Values[1] then SelectedMode := 1
    else SelectedMode := 2;
  end;
  if CurPageID = PrivacyPage.ID then
  begin
    if WizardSilent then
      PrivacyCheck.Checked := True;
    if not PrivacyCheck.Checked then
    begin
      MsgBox(CustomMessage('PrivacyNeedAck'), mbInformation, MB_OK);
      Result := False;
    end;
  end;
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := False;
  if SelectedMode = 2 then
  begin
    if (PageID = wpSelectComponents) or (PageID = wpSelectTasks) then
      Result := True;
    if PageID = PrivacyPage.ID then
      Result := True;
    if (TessLangPage <> nil) and (PageID = TessLangPage.ID) then
      Result := True;
  end;
  { Silent installs skip the interactive privacy page; engine still gets --privacy-ack. }
  if WizardSilent and (PageID = PrivacyPage.ID) then
    Result := True;
  if (TessLangPage <> nil) and (PageID = TessLangPage.ID) then
  begin
    if WizardSilent or (not WizardIsComponentSelected('tesseract')) then
      Result := True;
  end;
end;

function UpdateReadyMemo(Space, NewLine, MemoUserInfoInfo, MemoDirInfo, MemoTypeInfo,
  MemoComponentsInfo, MemoGroupInfo, MemoTasksInfo: String): String;
var
  ModeText: String;
begin
  case SelectedMode of
    1: ModeText := CustomMessage('ModeReinstall');
    2: ModeText := CustomMessage('ModeUninstall');
  else
    ModeText := CustomMessage('ModeInstall');
  end;
  Result := CustomMessage('ReadyModeLabel') + NewLine + Space + ModeText + NewLine + NewLine +
    MemoDirInfo + NewLine + NewLine;
  if SelectedMode <> 2 then
    Result := Result + MemoComponentsInfo + NewLine + NewLine + MemoTasksInfo;
end;

procedure PrepareProgressPage(const Action: String);
begin
  if Action = '--uninstall' then
  begin
    ProgressPage.Caption := CustomMessage('ProgressUninstallCaption');
    ProgressPage.Description := CustomMessage('ProgressUninstallDescription');
  end
  else if Action = '--reinstall' then
  begin
    ProgressPage.Caption := CustomMessage('ProgressReinstallCaption');
    ProgressPage.Description := CustomMessage('ProgressReinstallDescription');
  end
  else
  begin
    ProgressPage.Caption := CustomMessage('ProgressCaption');
    ProgressPage.Description := CustomMessage('ProgressDescription');
  end;
  ProgressPage.SetText(ProgressRunningMessage(Action), Action);
  ProgressPage.SetProgress(0, 0);
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Action: String;
  Ok: Boolean;
  ShowProgress: Boolean;
begin
  if CurStep <> ssPostInstall then
    Exit;
  case SelectedMode of
    1: Action := '--reinstall';
    2: Action := '--uninstall';
  else
    Action := '--install';
  end;
  ShowProgress := not WizardSilent;
  EngineShowProgress := ShowProgress;
  if ShowProgress then
  begin
    PrepareProgressPage(Action);
    ProgressPage.Show;
  end;
  try
    Ok := RunEngine(Action);
  finally
    EngineShowProgress := False;
    if ShowProgress then
      ProgressPage.Hide;
  end;
  if not Ok then
  begin
    Log('Install engine reported failure for action ' + Action);
    RaiseException(CustomMessage('ErrEngineException'));
  end;
  if SelectedMode = 2 then
  begin
    { Wizard uninstall: remove PATH and schedule directory deletion via UninstallDelete-equivalent. }
    RemoveUserPathEntry(ExpandConstant('{app}\bin'));
    DelTree(ExpandConstant('{app}'), True, True, True);
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
    RemoveUserPathEntry(ExpandConstant('{app}\bin'));
end;
